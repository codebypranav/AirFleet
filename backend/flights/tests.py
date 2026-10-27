import io
import json
import struct
from datetime import date, datetime, timedelta, timezone as dt_timezone
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from . import airports, ask, external, flight_plans, insights, patterns, plan_review, quick_log, views
from .models import Aircraft, Block, CrewSeat, Flight, Follow, Like, Notification

FLIGHT = {
    'departure_airport': 'KJFK',
    'arrival_airport': 'KLAX',
    'departure_time': '2026-01-01T10:00:00Z',
    'arrival_time': '2026-01-01T15:30:00Z',
    'total_time': '05:30:00',
    'registration_number': 'N12345',
    'aircraft_condition': 'GOOD',
    'distance': 2145,
}
PASSWORD = 'Sup3r-secret-pw'


class ApiTestCase(APITestCase):
    def setUp(self):
        cache.clear()  # throttle counters live in the cache

    def register(self, username='pilot', **extra):
        return self.client.post('/api/register/', {
            'username': username,
            'email': f'{username}@example.com',
            'password': PASSWORD,
            'password2': PASSWORD,
            **extra,
        }, format='json')

    def authenticate(self, username='pilot'):
        self.register(username)
        res = self.client.post('/api/login/', {'username': username, 'password': PASSWORD}, format='json')
        self.assertEqual(res.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        return res.data

    def add_flight(self, **overrides):
        res = self.client.post('/api/flights/', {**FLIGHT, **overrides}, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        return res.data


class AirportTests(SimpleTestCase):
    def test_lookup_is_case_insensitive(self):
        self.assertEqual(airports.get('kjfk').name, 'John F. Kennedy International Airport')
        self.assertIsNone(airports.get('ZZZZ'))

    def test_distance(self):
        self.assertAlmostEqual(airports.distance_nm(airports.get('KJFK'), airports.get('KLAX')), 2145, delta=10)
        self.assertAlmostEqual(airports.distance_nm(airports.get('EGLL'), airports.get('KJFK')), 2999, delta=10)

    def test_search_prefers_exact_codes_and_big_airports(self):
        self.assertEqual(airports.search('KSFO')[0].code, 'KSFO')
        self.assertEqual(airports.search('heathrow')[0].code, 'EGLL')
        self.assertEqual(airports.search(''), [])


class ApiFlowTests(ApiTestCase):
    def test_register_returns_tokens(self):
        res = self.register()
        self.assertEqual(res.status_code, 201)
        self.assertIn('access', res.data)
        self.assertIn('refresh', res.data)

    def test_register_rejects_duplicate_username(self):
        self.register()
        res = self.register(email='other@example.com')
        self.assertEqual(res.status_code, 400)
        self.assertIn('username', res.data)

    def test_login_rejects_bad_password(self):
        self.register()
        res = self.client.post('/api/login/', {'username': 'pilot', 'password': 'nope'}, format='json')
        self.assertEqual(res.status_code, 401)

    def test_token_refresh(self):
        tokens = self.authenticate()
        res = self.client.post('/api/token/refresh/', {'refresh': tokens['refresh']}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertIn('access', res.data)

    def test_flights_require_auth(self):
        self.assertEqual(self.client.get('/api/flights/').status_code, 401)

    def test_flight_crud(self):
        self.authenticate()
        flight_id = self.add_flight()['id']

        self.assertEqual(self.client.get('/api/flights/').data['count'], 1)

        updated = {**FLIGHT, 'notes': 'Smooth ride'}
        res = self.client.put(f'/api/flights/{flight_id}/', updated, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['notes'], 'Smooth ride')

        res = self.client.patch(f'/api/flights/{flight_id}/', {'night_time': '01:00:00'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['night_time'], '01:00:00')
        self.assertEqual(res.data['notes'], 'Smooth ride')

        self.assertEqual(self.client.delete(f'/api/flights/{flight_id}/').status_code, 204)
        self.assertFalse(Flight.objects.exists())

    def test_flight_validation(self):
        self.authenticate()
        res = self.client.post('/api/flights/', {**FLIGHT, 'total_time': '01:00:00'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_unknown_airport_rejected(self):
        self.authenticate()
        res = self.client.post('/api/flights/', {**FLIGHT, 'arrival_airport': 'ZZZZ'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('arrival_airport', res.data['errors'])

    def test_time_column_cannot_exceed_total(self):
        self.authenticate()
        res = self.client.post('/api/flights/', {**FLIGHT, 'night_time': '06:00:00'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('night_time', res.data['errors'])

    def test_total_time_and_distance_are_computed(self):
        self.authenticate()
        data = {k: v for k, v in FLIGHT.items() if k not in ('total_time', 'distance')}
        res = self.client.post('/api/flights/', {**data, 'arrival_airport': 'kbos'}, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['total_time'], '05:30:00')
        self.assertEqual(res.data['arrival_airport'], 'KBOS')
        self.assertAlmostEqual(res.data['distance'], 162, delta=5)
        self.assertEqual(res.data['arrival_info']['city'], 'Boston')

    def test_changing_airports_recomputes_distance(self):
        self.authenticate()
        flight = self.add_flight(distance=0)
        res = self.client.patch(f"/api/flights/{flight['id']}/", {'arrival_airport': 'KBOS'}, format='json')
        self.assertAlmostEqual(res.data['distance'], 162, delta=5)

    def test_users_only_see_their_own_flights(self):
        self.authenticate('alice')
        flight_id = self.add_flight()['id']
        self.authenticate('bob')
        self.assertEqual(self.client.get('/api/flights/').data['results'], [])
        self.assertEqual(self.client.get(f'/api/flights/{flight_id}/').status_code, 404)
        self.assertEqual(self.client.delete(f'/api/flights/{flight_id}/').status_code, 404)

    def test_pagination_and_filters(self):
        self.authenticate()
        for day in range(1, 26):
            self.add_flight(
                departure_time=f'2026-01-{day:02d}T10:00:00Z', arrival_time=f'2026-01-{day:02d}T16:00:00Z',
                total_time='06:00:00', arrival_airport='KBOS' if day % 5 == 0 else 'KLAX',
                registration_number='N1' if day <= 10 else 'N2', notes='crosswind' if day == 3 else '',
            )
        page = self.client.get('/api/flights/').data
        self.assertEqual((page['count'], len(page['results'])), (25, 20))
        self.assertEqual(page['results'][0]['departure_time'][:10], '2026-01-25')
        self.assertEqual(len(self.client.get('/api/flights/?page=2').data['results']), 5)
        self.assertEqual(self.client.get('/api/flights/?airport=kbos').data['count'], 5)
        self.assertEqual(self.client.get('/api/flights/?aircraft=n1').data['count'], 10)
        self.assertEqual(self.client.get('/api/flights/?from=2026-01-10&to=2026-01-12').data['count'], 3)
        self.assertEqual(self.client.get('/api/flights/?q=crosswind').data['count'], 1)

    def test_rankings(self):
        self.authenticate()
        self.add_flight()
        self.client.credentials()
        res = self.client.get('/api/rankings/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['flights'][0], {'username': 'pilot', 'is_public': False, 'total_flights': 1, 'followers': None})
        self.assertEqual(res.data['distance'][0]['total_distance'], 2145)
        self.assertEqual(res.data['longest'][0]['longest_flight'], '5:30:00')
        self.assertEqual(res.data['airports'][0]['airports_visited'], 2)

    def test_rankings_period(self):
        self.authenticate()
        self.add_flight(departure_time='2020-01-01T10:00:00Z', arrival_time='2020-01-01T15:30:00Z')
        self.client.credentials()
        self.assertEqual(len(self.client.get('/api/rankings/').data['flights']), 1)
        res = self.client.get('/api/rankings/?period=year')
        self.assertEqual((res.data['period'], res.data['flights'], res.data['airports']), ('year', [], []))



class AircraftTests(ApiTestCase):
    def test_flights_create_and_link_aircraft(self):
        self.authenticate()
        self.add_flight(registration_number='n172sp')
        self.add_flight(registration_number='N172SP ', departure_time='2026-02-01T10:00:00Z', arrival_time='2026-02-01T15:30:00Z')
        aircraft = self.client.get('/api/aircraft/').data
        self.assertEqual(len(aircraft), 1)
        self.assertEqual(aircraft[0]['registration'], 'N172SP')
        self.assertEqual(aircraft[0]['total_flights'], 2)
        self.assertEqual(aircraft[0]['hours_since_maintenance'], 11.0)

    def test_create_and_edit_aircraft(self):
        self.authenticate()
        res = self.client.post('/api/aircraft/', {'registration': 'c-gabc', 'type_code': 'c172', 'make_model': 'Cessna 172'}, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual((res.data['registration'], res.data['type_code']), ('C-GABC', 'C172'))
        self.assertEqual(self.client.post('/api/aircraft/', {'registration': 'C-GABC'}, format='json').status_code, 400)

        self.add_flight(registration_number='C-GABC')
        res = self.client.patch(f"/api/aircraft/{res.data['id']}/", {'registration': 'C-GXYZ'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(Flight.objects.get().registration_number, 'C-GXYZ')

    def test_grounded_aircraft_blocks_new_flights_until_maintenance(self):
        self.authenticate()
        self.add_flight(aircraft_condition='GROUNDED')
        plane = Aircraft.objects.get()
        self.assertTrue(plane.grounded)

        res = self.client.post('/api/flights/', {**FLIGHT, 'departure_time': '2026-01-02T10:00:00Z', 'arrival_time': '2026-01-02T15:30:00Z'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('grounded', str(res.data['errors']['registration_number']))

        res = self.client.post(f'/api/aircraft/{plane.id}/maintenance/', {'annual_due': '2027-01-01'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['grounded'])
        self.assertEqual(res.data['hours_since_maintenance'], 0)
        self.assertEqual(res.data['annual_due'], '2027-01-01')
        self.add_flight(departure_time='2026-01-03T10:00:00Z', arrival_time='2026-01-03T15:30:00Z')

    def test_maintenance_due(self):
        self.authenticate()
        res = self.client.post('/api/aircraft/', {'registration': 'N1', 'maintenance_interval_hours': 5}, format='json')
        self.assertFalse(res.data['maintenance_due'])
        self.add_flight(registration_number='N1')
        self.assertTrue(self.client.get(f"/api/aircraft/{res.data['id']}/").data['maintenance_due'])

    def test_maintenance_forecast(self):
        self.authenticate()
        plane = self.client.post('/api/aircraft/', {'registration': 'N1', 'annual_due': '2099-01-01'}, format='json').data
        self.assertIsNone(plane['maintenance_forecast']['inspection_due_on'])  # no recent flying
        self.assertEqual(plane['maintenance_forecast']['next_due'], {'kind': 'annual', 'date': '2099-01-01'})

        # 9 h in the last 90 days is 0.7 h a week; 91 h left takes 910 days.
        start = datetime.now(dt_timezone.utc).replace(microsecond=0) - timedelta(days=10)
        self.add_flight(registration_number='N1', departure_time=start.isoformat(), arrival_time=(start + timedelta(hours=9)).isoformat(), total_time='09:00:00')
        forecast = self.client.get(f"/api/aircraft/{plane['id']}/").data['maintenance_forecast']
        self.assertEqual(forecast['hours_per_week'], 0.7)
        self.assertEqual(forecast['hours_remaining'], 91)
        expected = (start.date() + timedelta(days=10 + 910)).isoformat()
        self.assertEqual(forecast['inspection_due_on'], expected)
        self.assertEqual(forecast['next_due'], {'kind': 'inspection', 'date': expected})
        self.assertEqual(self.client.get('/api/aircraft/').data[0]['maintenance_forecast'], forecast)

    def test_aircraft_are_private(self):
        self.authenticate('alice')
        plane = self.client.post('/api/aircraft/', {'registration': 'N1'}, format='json').data
        self.authenticate('bob')
        self.assertEqual(self.client.get('/api/aircraft/').data, [])
        self.assertEqual(self.client.get(f"/api/aircraft/{plane['id']}/").status_code, 404)
        self.assertEqual(self.client.post(f"/api/aircraft/{plane['id']}/maintenance/").status_code, 404)


class InsightTests(ApiTestCase):
    def test_stats(self):
        self.authenticate()
        self.add_flight(night_time='01:00:00', day_landings=1, night_landings=2, approaches=1, cross_country=True)
        self.add_flight(departure_airport='EGLL', arrival_airport='KJFK', registration_number='G-ABCD',
                        departure_time='2026-03-01T10:00:00Z', arrival_time='2026-03-01T18:00:00Z', total_time='08:00:00', distance=0)
        data = self.client.get('/api/stats/').data
        totals = data['totals']
        self.assertEqual(totals['flights'], 2)
        self.assertEqual(totals['hours'], 13.5)
        self.assertEqual(totals['landings'], 3)
        self.assertEqual(totals['airports'], 3)
        self.assertEqual(totals['countries'], 2)
        self.assertEqual(totals['airframes'], 2)
        self.assertEqual(len(data['by_month']), 12)
        self.assertEqual(data['top_aircraft'][0]['registration'], 'G-ABCD')

    def test_routes(self):
        self.authenticate()
        self.add_flight()
        self.add_flight(departure_time='2026-02-01T10:00:00Z', arrival_time='2026-02-01T15:30:00Z')
        data = self.client.get('/api/stats/routes/').data
        self.assertEqual(data['routes'], [{'from': 'KJFK', 'to': 'KLAX', 'flights': 2, 'hours': 11.0}])
        self.assertEqual({a['code'] for a in data['airports']}, {'KJFK', 'KLAX'})

    def test_currency(self):
        self.authenticate()
        user = get_user_model().objects.get(username='pilot')
        today = date(2026, 6, 1)

        def flight(day, **extra):
            dep = datetime.combine(day, datetime.min.time(), dt_timezone.utc) + timedelta(hours=12)
            return Flight.objects.create(
                user=user, departure_airport='KJFK', arrival_airport='KBOS', departure_time=dep,
                arrival_time=dep + timedelta(hours=1), total_time=timedelta(hours=1), registration_number='N1', **extra,
            )

        flight(date(2026, 5, 1), day_landings=2)
        flight(date(2026, 5, 20), day_landings=1, night_landings=1, approaches=6, is_simulator=True)
        flight(date(2026, 5, 25), night_landings=2)
        result = {c['key']: c for c in insights.currency(Flight.objects.filter(user=user), today=today)}

        self.assertEqual(result['passenger_day']['status'], 'current')
        self.assertEqual(result['passenger_day']['expires_on'], '2026-07-30')  # 3rd landing on May 1st
        self.assertEqual(result['passenger_night']['status'], 'lapsed')  # sim landings don't count
        self.assertEqual(result['instrument']['status'], 'current')
        self.assertEqual(result['instrument']['expires_on'], '2026-11-30')
        self.assertEqual(self.client.get('/api/currency/').status_code, 200)

    def test_achievements(self):
        self.authenticate()
        self.add_flight()
        self.add_flight(departure_airport='EGLL', arrival_airport='LFPG', departure_time='2026-02-01T10:00:00Z',
                        arrival_time='2026-02-01T11:00:00Z', total_time='01:00:00', distance=0, night_time='00:30:00')
        earned = {a['key']: a for a in self.client.get('/api/achievements/').data if a['earned']}
        self.assertEqual(set(earned), {'first_flight', 'long_haul', 'first_night', 'countries_3'})
        self.assertTrue(earned['first_flight']['earned_at'].startswith('2026-01-01'))


class Faa8710Tests(ApiTestCase):
    """The grid a student copies into IACRA. Capacity splits per class, simulator time apart, empty rows left off."""

    def grid(self):
        data = self.client.get('/api/stats/').data['faa_8710']
        return data, {row['key']: row for row in data['rows']}

    def test_splits_dual_from_solo_and_keeps_the_simulator_out_of_flight_time(self):
        self.authenticate()
        self.add_flight(dual_received_time='05:30:00', night_time='01:00:00', night_landings=2,
                        day_landings=1, cross_country=True)
        self.add_flight(departure_time='2026-01-02T10:00:00Z', arrival_time='2026-01-02T15:30:00Z',
                        pic_time='05:30:00', night_landings=1, approaches=2, cross_country=True)
        self.add_flight(departure_time='2026-01-03T10:00:00Z', arrival_time='2026-01-03T11:30:00Z',
                        total_time='01:30:00', distance=0, is_simulator=True,
                        dual_received_time='01:30:00', simulated_instrument_time='01:00:00')
        data, rows = self.grid()

        self.assertEqual([c['key'] for c in data['columns']], ['SEL'])
        self.assertEqual(rows['flights']['values']['SEL'], 2)
        self.assertEqual(rows['total']['values']['SEL'], 11.0)
        self.assertEqual(rows['dual']['values']['SEL'], 5.5)
        self.assertEqual(rows['solo']['values']['SEL'], 5.5)
        self.assertEqual(rows['xc_dual']['values']['SEL'], 5.5)
        self.assertEqual(rows['xc_solo']['values']['SEL'], 5.5)
        self.assertEqual(rows['night']['values']['SEL'], 1.0)
        self.assertEqual(rows['night_dual']['values']['SEL'], 1.0)
        self.assertEqual(rows['night_landings_dual']['values']['SEL'], 2)
        self.assertEqual(rows['night_landings_solo']['values']['SEL'], 1)
        self.assertEqual(rows['approaches']['values']['SEL'], 2)
        self.assertEqual(rows['trainer_flights']['values']['SEL'], 1)
        self.assertEqual(rows['trainer_hours']['values']['SEL'], 1.5)
        self.assertEqual(rows['instrument_trainer']['values']['SEL'], 1.0)
        self.assertNotIn('sic', rows)

    def test_one_column_per_class_flown(self):
        self.authenticate()
        self.add_flight(pic_time='05:30:00')
        self.add_flight(registration_number='N99999', departure_time='2026-01-02T10:00:00Z',
                        arrival_time='2026-01-02T15:30:00Z', pic_time='05:30:00')
        Aircraft.objects.filter(registration='N99999').update(aircraft_class='MEL')
        orphan = self.add_flight(departure_time='2026-01-03T10:00:00Z', arrival_time='2026-01-03T15:30:00Z',
                                 pic_time='05:30:00')
        Flight.objects.filter(pk=orphan['id']).update(aircraft=None)
        data, rows = self.grid()

        self.assertEqual([c['key'] for c in data['columns']], ['SEL', 'MEL', 'UNSPECIFIED', 'total'])
        self.assertEqual(rows['pic']['values'], {'SEL': 5.5, 'MEL': 5.5, 'UNSPECIFIED': 5.5, 'total': 16.5})


class MaintenanceForecastTests(SimpleTestCase):
    today = date(2026, 10, 1)

    def test_projects_from_recent_rate(self):
        # 30 h over 90 days, 20 h left: 60 days.
        forecast = insights.maintenance_forecast(80, 100, 30, None, self.today)
        self.assertEqual(forecast['hours_per_week'], 2.3)
        self.assertEqual(forecast['inspection_due_on'], '2026-11-30')
        self.assertEqual(forecast['next_due'], {'kind': 'inspection', 'date': '2026-11-30'})

    def test_annual_first(self):
        forecast = insights.maintenance_forecast(80, 100, 30, date(2026, 11, 1), self.today)
        self.assertEqual(forecast['next_due'], {'kind': 'annual', 'date': '2026-11-01'})

    def test_overdue_is_due_today(self):
        forecast = insights.maintenance_forecast(120, 100, 0, None, self.today)
        self.assertEqual((forecast['hours_remaining'], forecast['inspection_due_on']), (0, '2026-10-01'))

    def test_idle_aircraft_has_no_date(self):
        forecast = insights.maintenance_forecast(10, 100, 0, None, self.today)
        self.assertIsNone(forecast['inspection_due_on'])
        self.assertIsNone(forecast['next_due'])


class ImportExportTests(ApiTestCase):
    def upload(self, text, name='logbook.csv'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        data = text if isinstance(text, bytes) else text.encode()
        return self.client.post('/api/flights/import/', {'file': SimpleUploadedFile(name, data, content_type='text/csv')}, format='multipart')

    def test_export_then_import_round_trip(self):
        self.authenticate('alice')
        self.add_flight(notes='Hello, "world"', night_time='01:00:00', approaches=2)
        csv_text = self.client.get('/api/flights/export/').content.decode()
        self.assertIn('departure_airport', csv_text.splitlines()[0])

        self.authenticate('bob')
        res = self.upload(csv_text)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual((res.data['source'], res.data['created']), ('airfleet', 1))
        flight = Flight.objects.get(user__username='bob')
        self.assertEqual((flight.notes, flight.night_time, flight.approaches), ('Hello, "world"', timedelta(hours=1), 2))

        res = self.upload(csv_text)
        self.assertEqual((res.data['created'], res.data['duplicates']), (0, 1))

    def test_import_reports_bad_rows(self):
        self.authenticate()
        text = (
            'departure_airport,arrival_airport,departure_time,arrival_time,registration_number\n'
            'KJFK,KBOS,2026-01-01T10:00:00Z,2026-01-01T11:00:00Z,N1\n'
            'KJFK,XXXX,2026-01-02T10:00:00Z,2026-01-02T11:00:00Z,N1\n'
        )
        res = self.upload(text)
        self.assertEqual((res.data['created'], res.data['skipped']), (1, 1))
        self.assertEqual(res.data['errors'][0]['row'], 2)

    def test_import_rejects_unknown_format(self):
        self.authenticate()
        res = self.upload('foo,bar\n1,2\n')
        self.assertEqual(res.status_code, 400)
        self.assertIn('MyFlightbook', res.data['error'])
        res = self.upload('departure_airport,arrival_airport\nKJFK,KBOS\n')
        self.assertIn('Missing columns', res.data['error'])

    def test_foreflight_import(self):
        self.authenticate()
        text = (
            'ForeFlight Logbook Import,This row is required for importing into ForeFlight. Do not delete or modify.\n'
            '\n'
            'Aircraft Table,,,,,,,\n'
            'AircraftID,TypeCode,Year,Make,Model,Category,Class,GearType\n'
            'N172SP,C172,2005,Cessna,172S,airplane,airplane_single_engine_land,fixed_tricycle\n'
            '\n'
            'Flights Table,,,,,,,,,,,,,,,,\n'
            'Date,AircraftID,From,To,Route,TimeOut,TimeOff,TimeOn,TimeIn,TotalTime,PIC,Night,CrossCountry,DayLandingsFullStop,NightLandingsFullStop,AllLandings,ActualInstrument,Approach1,Approach2,SimulatedFlight,PilotComments\n'
            '2026-01-05,N172SP,KJFK,KBOS,DCT,1400,1410,,,1.5,1.5,0.5,1.5,1,1,2,0.2,1;ILS;4R;KBOS;;,,0,Gusty\n'
            '2026-01-06,N172SP,KBOS,1B9,,,,,,1.0,1.0,0,0,1,0,1,0,,,0,\n'
            '03/04/2026,N172SP,KJFK,KBOS,,,,,,1.0,1.0,0,0,1,0,1,0,,,0,\n'
            '9999-12-31,N172SP,KJFK,KBOS,,,,,,1.0,1.0,0,0,1,0,1,0,,,0,\n'
        )
        res = self.upload(text)
        self.assertEqual(res.data['source'], 'foreflight')
        self.assertEqual((res.data['created'], res.data['skipped']), (1, 3), res.data)
        self.assertEqual(res.data['errors'][1], {'row': 3, 'errors': "Unrecognised date '03/04/2026'"})
        self.assertEqual(res.data['errors'][2], {'row': 4, 'errors': "Unrecognised date '9999-12-31'"})
        flight = Flight.objects.get()
        self.assertEqual(flight.departure_time, datetime(2026, 1, 5, 14, 10, tzinfo=dt_timezone.utc))
        self.assertEqual((flight.total_time, flight.night_time, flight.approaches), (timedelta(hours=1.5), timedelta(hours=0.5), 1))
        self.assertEqual((flight.day_landings, flight.night_landings, flight.cross_country), (1, 1, True))
        self.assertEqual(flight.notes, 'Gusty')
        self.assertEqual((flight.aircraft.type_code, flight.aircraft.make_model), ('C172', 'Cessna 172S'))

    def test_logten_import(self):
        self.authenticate()
        text = (
            'flight_flightDate\taircraft_aircraftID\taircraftType_type\taircraftType_make\taircraftType_model\tflight_from\tflight_to\t'
            'flight_takeoffTime\tflight_totalTime\tflight_pic\tflight_night\tflight_dayLandings\tflight_nightLandings\tflight_totalApproaches\tflight_remarks\tflight_distance\n'
            '1/5/2026\tN172SP\tC172\tCessna\t172S\tPAE\tAWO\t14:10\t1:30\t1:30\t0:30\t1\t1\t2\tPattern work\t556\n'
            '1/6/2026\tN172SP\tC172\tCessna\t172S\tPAE\t\t\t\t\t\t\t\t\t\t\n'
        )
        res = self.upload(text, name='logten.txt')
        self.assertEqual(res.data['source'], 'logten', res.data)
        self.assertEqual((res.data['created'], res.data['skipped']), (1, 1), res.data)
        flight = Flight.objects.get()
        self.assertEqual((flight.departure_airport, flight.arrival_airport), ('KPAE', 'KAWO'))
        self.assertEqual(flight.departure_time, datetime(2026, 1, 5, 14, 10, tzinfo=dt_timezone.utc))
        self.assertEqual((flight.total_time, flight.pic_time, flight.night_time), (timedelta(hours=1.5), timedelta(hours=1.5), timedelta(minutes=30)))
        self.assertEqual((flight.day_landings, flight.night_landings, flight.approaches, flight.notes), (1, 1, 2, 'Pattern work'))
        self.assertAlmostEqual(flight.distance, 16, delta=2)
        self.assertEqual((flight.aircraft.type_code, flight.aircraft.make_model), ('C172', 'Cessna 172S'))

        self.assertEqual(self.upload(text, name='logten.txt').data['duplicates'], 1)

    def test_myflightbook_import(self):
        self.authenticate()
        text = (
            'Date,Flight ID,Model,ICAO Model,Tail Number,Display Tail,Aircraft ID,Category/Class,Approaches,Hold,Landings,FS Night Landings,'
            'FS Day Landings,X-Country,Night,IMC,Simulated Instrument,Ground Simulator,Dual Received,CFI,SIC,PIC,Total Flight Time,Route,'
            'Comments,Engine Start,Engine End,Flight Start,Flight End\n'
            '2026-01-05,1234,C-172 S,C172,N172SP,N172SP,99,AMEL,1,,3,1,1,1.4,0.5,0.2,0.3,0,1.6,0,0,0,1.6,KPAE KBVS KAWO,'
            'First solo XC,2026-01-05 14:00:00Z,2026-01-05 15:45:00Z,2026-01-05 14:10:00Z,2026-01-05 15:40:00Z\n'
        )
        res = self.upload(text)
        self.assertEqual((res.data['source'], res.data['created']), ('myflightbook', 1), res.data)
        flight = Flight.objects.get()
        self.assertEqual((flight.departure_airport, flight.arrival_airport, flight.flight_plan), ('KPAE', 'KAWO', 'KPAE KBVS KAWO'))
        self.assertEqual(flight.departure_time, datetime(2026, 1, 5, 14, 10, tzinfo=dt_timezone.utc))
        self.assertEqual((flight.total_time, flight.dual_received_time, flight.instrument_time), (timedelta(hours=1.6), timedelta(hours=1.6), timedelta(hours=0.2)))
        self.assertEqual((flight.day_landings, flight.night_landings, flight.approaches, flight.cross_country), (2, 1, 1, True))
        self.assertEqual(flight.notes, 'First solo XC')
        self.assertEqual((flight.aircraft.type_code, flight.aircraft.make_model, flight.aircraft.aircraft_class), ('C172', 'C-172 S', 'MEL'))

    def test_template_xlsx_round_trip(self):
        import openpyxl
        res = self.client.get('/api/flights/import/template/')
        self.assertEqual(res.status_code, 200)
        book = openpyxl.load_workbook(io.BytesIO(res.content))
        sheet = book.active
        header = [cell.value for cell in sheet[1]]
        self.assertEqual(header, [
            'Date', 'From', 'To', 'Route', 'Aircraft', 'Type', 'Time Off', 'Total', 'PIC', 'SIC', 'Dual Received',
            'Night', 'Actual Instrument', 'Simulated Instrument', 'Cross Country', 'Day Landings', 'Night Landings',
            'Approaches', 'Simulator', 'Remarks',
        ])
        values = {'Date': datetime(2026, 1, 5), 'From': 'KPAE', 'To': 'AWO', 'Aircraft': 'N172SP', 'Type': 'C172',
                  'Time Off': '14:10', 'Total': 1.5, 'PIC': 1.5, 'Day Landings': 2, 'Remarks': 'Template'}
        sheet.append([values.get(column) for column in header])
        out = io.BytesIO()
        book.save(out)

        self.authenticate()
        res = self.upload(out.getvalue(), name='logbook.xlsx')
        self.assertEqual((res.data['source'], res.data['created']), ('template', 1), res.data)
        flight = Flight.objects.get()
        self.assertEqual((flight.departure_airport, flight.arrival_airport), ('KPAE', 'KAWO'))
        self.assertEqual(flight.departure_time, datetime(2026, 1, 5, 14, 10, tzinfo=dt_timezone.utc))
        self.assertEqual((flight.total_time, flight.day_landings, flight.notes), (timedelta(hours=1.5), 2, 'Template'))
        self.assertEqual(flight.aircraft.type_code, 'C172')

    def test_template_csv(self):
        self.authenticate()
        res = self.upload('Date,From,To,Aircraft,Total,Night\n2026-01-05,KJFK,KBOS,N1,1:15,0:45\n')
        self.assertEqual((res.data['source'], res.data['created']), ('template', 1), res.data)
        flight = Flight.objects.get()
        self.assertEqual((flight.total_time, flight.night_time), (timedelta(minutes=75), timedelta(minutes=45)))
        self.assertEqual(flight.departure_time, datetime(2026, 1, 5, 12, 0, tzinfo=dt_timezone.utc))

    def test_import_reads_three_letter_codes(self):
        self.authenticate()
        res = self.upload(
            'Date,From,To,Aircraft,Total\n'
            '2026-01-05,LHR,CDG,G-ABCD,1.5\n'
            '2026-01-06,PAE,BVS,N1,1.0\n'
            '2026-01-07,KBOS,1B9,N1,1.0\n'
        )
        self.assertEqual((res.data['created'], res.data['skipped']), (1, 2), res.data)
        self.assertEqual(Flight.objects.values_list('departure_airport', 'arrival_airport').get(), ('EGLL', 'LFPG'))
        self.assertEqual(res.data['errors'][0], {'row': 2, 'errors': 'BVS could be KBVS or SNVS. Use the 4-letter ICAO code.'})
        self.assertEqual(res.data['errors'][1]['row'], 3)

    def test_import_rejects_unreadable_spreadsheet(self):
        self.authenticate()
        crafted_eocd = b'PK\x05\x06' + struct.pack('<HHHHIIH', 0, 0, 1, 1, 100, 0xFFFFFF00, 0)
        for payload in (b'PK\x03\x04 not really a workbook', crafted_eocd):
            res = self.upload(payload, name='logbook.xlsx')
            self.assertEqual(res.status_code, 400, payload)
            self.assertIn("Couldn't read this spreadsheet", res.data['error'])

    def test_import_reports_absurd_numbers_per_row(self):
        self.authenticate()
        res = self.upload(
            'Date,From,To,Aircraft,Total,Day Landings\n'
            '2026-01-05,KJFK,KBOS,N1,100000000,1\n'
            '2026-01-06,KJFK,KBOS,N1,1.0,1e400\n'
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual((res.data['created'], res.data['skipped']), (1, 1))
        self.assertEqual(res.data['errors'][0]['row'], 1)
        self.assertEqual(Flight.objects.values_list('departure_time', 'day_landings').get(),
                         (datetime(2026, 1, 6, 12, 0, tzinfo=dt_timezone.utc), 0))

    def test_import_reads_iso_datetime_takeoff(self):
        self.authenticate()
        res = self.upload('Date,From,To,Aircraft,Total,Time Off\n2026-01-05,KJFK,KBOS,N1,1.0,2026-01-06T14:10:00Z\n')
        self.assertEqual(res.data['created'], 1, res.data)
        self.assertEqual(Flight.objects.get().departure_time, datetime(2026, 1, 6, 14, 10, tzinfo=dt_timezone.utc))

    def test_import_rejects_unreadable_text(self):
        self.authenticate()
        res = self.upload(b'"' + b'x' * 200_000 + b'",Total\n', name='logbook.txt')
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn("Couldn't read this file", res.data['error'])


class LookupTests(ApiTestCase):
    def test_airport_endpoints(self):
        self.assertEqual(self.client.get('/api/airports/egll/').data['city'], 'London')
        self.assertEqual(self.client.get('/api/airports/ZZZZ/').status_code, 404)
        self.assertEqual(self.client.get('/api/airports/?q=KLA').data[0]['code'], 'KLAS')  # ties go to the lower code
        self.assertEqual(self.client.get('/api/airports/?q=los angeles intl').data, [])
        self.assertEqual(self.client.get('/api/airports/?q=los angeles international').data[0]['code'], 'KLAX')

    def test_weather(self):
        self.authenticate()
        reports = [
            {'obsTime': 1767261060, 'rawOb': 'METAR KJFK 010951Z 27010KT', 'fltCat': 'VFR'},
            {'obsTime': 1767257460, 'rawOb': 'METAR KJFK 010851Z 27008KT', 'fltCat': 'VFR'},
        ]
        with mock.patch('flights.external.requests.get') as get:
            get.return_value = mock.Mock(content=b'[]', json=mock.Mock(return_value=reports), raise_for_status=mock.Mock())
            res = self.client.get('/api/weather/?airport=KJFK&time=2026-01-01T10:00:00Z')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['raw'], 'METAR KJFK 010951Z 27010KT')
        self.assertEqual(get.call_args.kwargs['params']['date'], '2026-01-01T11:30:00Z')

    def test_weather_not_found(self):
        self.authenticate()
        with mock.patch('flights.external.requests.get') as get:
            get.return_value = mock.Mock(content=b'', raise_for_status=mock.Mock())
            res = self.client.get('/api/weather/?airport=KJFK&time=2020-01-01T10:00:00Z')
        self.assertEqual(res.status_code, 404)

    def test_weather_service_down(self):
        self.authenticate()
        with mock.patch('flights.external.requests.get', side_effect=external.requests.ConnectionError):
            self.assertEqual(self.client.get('/api/weather/?airport=KJFK').status_code, 502)

    def test_simbrief(self):
        self.authenticate()
        ofp = {
            'fetch': {'status': 'Success'},
            'origin': {'icao_code': 'LFBO'}, 'destination': {'icao_code': 'CYUL'},
            'times': {'sched_out': '1791046500', 'sched_in': '1791077100'},
            'aircraft': {'reg': 'C-GXLR', 'icaocode': 'A21N'},
            'general': {'route': 'GAUD7A GAUDE DCT', 'route_distance': '3312'},
            'weather': {'orig_metar': 'LFBO 031600Z\n14009KT'},
        }
        with mock.patch('flights.external.requests.get') as get:
            get.return_value = mock.Mock(json=mock.Mock(return_value=ofp))
            res = self.client.get('/api/simbrief/?username=pilot')
        self.assertEqual(res.status_code, 200)
        self.assertEqual((res.data['departure_airport'], res.data['distance'], res.data['weather_conditions']), ('LFBO', 3312, 'LFBO 031600Z 14009KT'))
        self.assertTrue(res.data['departure_time'].startswith('2026-10-03'))

        with mock.patch('flights.external.requests.get') as get:
            get.return_value = mock.Mock(json=mock.Mock(return_value={'fetch': {'status': 'Error: Unknown UserID'}}))
            self.assertEqual(self.client.get('/api/simbrief/?username=nobody').status_code, 404)


class AccountTests(ApiTestCase):
    def test_profile(self):
        self.authenticate()
        self.assertEqual(self.client.get('/api/me/').data['email'], 'pilot@example.com')
        res = self.client.patch('/api/me/', {'bio': 'Weekend flyer', 'home_airport': 'kbos', 'is_public': True}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data['home_airport'], res.data['is_public']), ('KBOS', True))
        self.assertEqual(self.client.patch('/api/me/', {'home_airport': 'ZZZZ'}, format='json').status_code, 400)

    def test_profile_email_must_be_unique(self):
        self.register('alice')
        self.authenticate('bob')
        self.assertEqual(self.client.patch('/api/me/', {'email': 'ALICE@example.com'}, format='json').status_code, 400)

    def test_change_password(self):
        self.authenticate()
        res = self.client.post('/api/me/password/', {'current_password': 'wrong', 'new_password': 'An0ther-secret'}, format='json')
        self.assertEqual(res.status_code, 400)
        res = self.client.post('/api/me/password/', {'current_password': PASSWORD, 'new_password': 'An0ther-secret'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.client.credentials()
        self.assertEqual(self.client.post('/api/login/', {'username': 'pilot', 'password': 'An0ther-secret'}, format='json').status_code, 200)

    @override_settings(FRONTEND_URL='https://airfleet.example')
    def test_password_reset(self):
        self.register()
        res = self.client.post('/api/password-reset/', {'email': 'nobody@example.com'}, format='json')
        self.assertEqual((res.status_code, len(mail.outbox)), (200, 0))

        res = self.client.post('/api/password-reset/', {'email': 'PILOT@example.com'}, format='json')
        self.assertEqual((res.status_code, len(mail.outbox)), (200, 1))
        link = next(line for line in mail.outbox[0].body.splitlines() if line.startswith('https://airfleet.example/reset-password'))
        from urllib.parse import parse_qs, urlparse
        params = {k: v[0] for k, v in parse_qs(urlparse(link).query).items()}

        bad = self.client.post('/api/password-reset/confirm/', {**params, 'token': 'nope', 'password': 'Brand-new-pw1'}, format='json')
        self.assertEqual(bad.status_code, 400)
        weak = self.client.post('/api/password-reset/confirm/', {**params, 'password': '123'}, format='json')
        self.assertEqual(weak.status_code, 400)
        res = self.client.post('/api/password-reset/confirm/', {**params, 'password': 'Brand-new-pw1'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.client.post('/api/login/', {'username': 'pilot', 'password': 'Brand-new-pw1'}, format='json').status_code, 200)
        reused = self.client.post('/api/password-reset/confirm/', {**params, 'password': 'Brand-new-pw2'}, format='json')
        self.assertEqual(reused.status_code, 400)

    @override_settings(GOOGLE_CLIENT_ID='client-id')
    def test_google_login_creates_and_reuses_accounts(self):
        claims = {'email': 'jane.doe@gmail.com', 'email_verified': True, 'given_name': 'Jane'}
        with mock.patch('google.oauth2.id_token.verify_oauth2_token', return_value=claims) as verify:
            res = self.client.post('/api/auth/google/', {'id_token': 'tok'}, format='json')
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.data['username'], 'jane.doe')
            self.assertEqual(verify.call_args.args[2], 'client-id')
            again = self.client.post('/api/auth/google/', {'id_token': 'tok'}, format='json')
        self.assertEqual(again.data['username'], 'jane.doe')
        self.assertEqual(get_user_model().objects.filter(email__iexact='jane.doe@gmail.com').count(), 1)

    @override_settings(GOOGLE_CLIENT_ID='client-id')
    def test_google_login_rejects_bad_tokens(self):
        with mock.patch('google.oauth2.id_token.verify_oauth2_token', side_effect=ValueError):
            self.assertEqual(self.client.post('/api/auth/google/', {'id_token': 'x'}, format='json').status_code, 401)
        with mock.patch('google.oauth2.id_token.verify_oauth2_token', return_value={'email': 'a@b.c', 'email_verified': False}):
            self.assertEqual(self.client.post('/api/auth/google/', {'id_token': 'x'}, format='json').status_code, 401)

    @override_settings(GOOGLE_CLIENT_ID='')
    def test_google_login_unconfigured(self):
        self.assertEqual(self.client.post('/api/auth/google/', {'id_token': 'x'}, format='json').status_code, 503)

    def test_delete_account(self):
        self.authenticate('bob')
        self.add_flight()
        self.client.credentials()
        self.authenticate()
        self.add_flight()
        self.client.post('/api/aircraft/', {'registration': 'N999AF'}, format='json')

        wrong_name = self.client.delete('/api/me/', {'confirm': 'someone', 'password': PASSWORD}, format='json')
        wrong_password = self.client.delete('/api/me/', {'confirm': 'pilot', 'password': 'nope'}, format='json')
        self.assertEqual((wrong_name.status_code, wrong_password.status_code), (400, 400))

        res = self.client.delete('/api/me/', {'confirm': 'pilot', 'password': PASSWORD}, format='json')
        self.assertEqual(res.status_code, 204)
        self.assertFalse(get_user_model().objects.filter(username='pilot').exists())
        self.assertEqual(Flight.objects.filter(user__username='pilot').count(), 0)
        self.assertEqual(Aircraft.objects.filter(user__username='pilot').count(), 0)
        self.assertEqual(Flight.objects.filter(user__username='bob').count(), 1)
        self.assertEqual(self.client.get('/api/me/').status_code, 401)
        self.client.credentials()
        self.assertEqual(self.client.post('/api/login/', {'username': 'pilot', 'password': PASSWORD}, format='json').status_code, 401)

    @override_settings(GOOGLE_CLIENT_ID='client-id')
    def test_delete_google_account_needs_no_password(self):
        claims = {'email': 'jane@gmail.com', 'email_verified': True}
        with mock.patch('google.oauth2.id_token.verify_oauth2_token', return_value=claims):
            tokens = self.client.post('/api/auth/google/', {'id_token': 'tok'}, format='json').data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(self.client.delete('/api/me/', {'confirm': 'jane'}, format='json').status_code, 204)
        self.assertFalse(get_user_model().objects.filter(email='jane@gmail.com').exists())


class PublicProfileTests(ApiTestCase):
    def test_private_by_default(self):
        self.authenticate()
        flight = self.add_flight()
        self.client.credentials()
        self.assertEqual(self.client.get('/api/pilots/pilot/').status_code, 404)
        self.assertEqual(self.client.get(f"/api/public/flights/{flight['id']}/").status_code, 404)

    def test_public_pilot(self):
        self.authenticate()
        flight = self.add_flight(notes='private note')
        self.client.patch('/api/me/', {'is_public': True, 'bio': 'Hi'}, format='json')
        self.client.credentials()
        profile = self.client.get('/api/pilots/pilot/').data
        self.assertEqual((profile['bio'], profile['stats']['flights']), ('Hi', 1))
        self.assertEqual(profile['recent_flights'][0]['id'], flight['id'])
        shared = self.client.get(f"/api/public/flights/{flight['id']}/").data
        self.assertEqual(shared['pilot'], 'pilot')
        self.assertNotIn('notes', shared)


class CorsTests(APITestCase):
    def preflight(self, origin):
        res = self.client.options('/api/login/', HTTP_ORIGIN=origin, HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST')
        return res.headers.get('Access-Control-Allow-Origin')

    def test_allowed_origins(self):
        for origin in [
            'http://localhost:3000',
            'https://airfleet.vercel.app',
            'https://airfleet-git-main-codebypranav.vercel.app',
            'https://airfleet-project-a1b2c3d4-codebypranav.vercel.app',
        ]:
            self.assertEqual(self.preflight(origin), origin, origin)

    def test_rejected_origins(self):
        for origin in [
            'https://evil.vercel.app',
            'https://airfleet.vercel.app.evil.com',
            'http://airfleet-git-main-x.vercel.app',
        ]:
            self.assertIsNone(self.preflight(origin), origin)


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class PhotoUploadTests(ApiTestCase):
    def image(self, name='runway.png', fmt='PNG', size=(4, 4)):
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        buf = io.BytesIO()
        Image.new('RGB', size, 'blue').save(buf, fmt)
        return SimpleUploadedFile(name, buf.getvalue(), content_type=f'image/{fmt.lower()}')

    def test_flight_with_photo(self):
        self.authenticate()
        res = self.client.post('/api/flights/', {**FLIGHT, 'photo': self.image()}, format='multipart')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertIn('flight_photos/runway', res.data['photo'])
        self.assertTrue(Flight.objects.get().photo.storage.exists(Flight.objects.get().photo.name))

    def test_deleting_account_removes_photos(self):
        self.authenticate()
        self.client.post('/api/flights/', {**FLIGHT, 'photo': self.image()}, format='multipart')
        photo = Flight.objects.get().photo
        res = self.client.delete('/api/me/', {'confirm': 'pilot', 'password': PASSWORD}, format='json')
        self.assertEqual(res.status_code, 204)
        self.assertFalse(photo.storage.exists(photo.name))

    def test_rejects_non_images_and_odd_formats(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.authenticate()
        res = self.client.post('/api/flights/', {**FLIGHT, 'photo': SimpleUploadedFile('x.png', b'not an image')}, format='multipart')
        self.assertEqual(res.status_code, 400)
        res = self.client.post('/api/flights/', {**FLIGHT, 'photo': self.image('x.tiff', 'TIFF')}, format='multipart')
        self.assertEqual(res.status_code, 400)

    def test_rejects_large_photos(self):
        self.authenticate()
        with mock.patch('flights.serializers.MAX_PHOTO_BYTES', 10):
            res = self.client.post('/api/flights/', {**FLIGHT, 'photo': self.image()}, format='multipart')
        self.assertEqual(res.status_code, 400)
        self.assertIn('10 MB', str(res.data['errors']['photo']))


# Trimmed from the text of a real SimBrief OFP (LIDO layout).
SIMBRIEF_OFP = """
                            C-GXLR/03 OCT/TLS-YUL                               Page 1
 [ OFP ]
 C-GXLR    03OCT2026    LFBO-CYUL   A21N CGXLR   RELEASE 1629 03OCT26
   ATC C/S   CGXLR        LFBO/TLS   CYUL/YUL      CRZ SYS      CI 17
 03OCT2026   CGXLR        1655/1715  0113/0121     GND DIST      3312
                                 TIMES
                ESTIMATED        SKED              ACTUAL
 OUT            1655Z/1855L      1655Z/1855L       ......Z
 OFF            1715Z/1915L      1715Z/1915L       ......Z
 ON             0113Z/2113L      0117Z/2117L       ......Z
 IN             0121Z/2121L      0125Z/2125L       ......Z
 BLOCK TIME     0826             0830              ......
                                  - Not for real world navigation -                    1
 (FPL-CGXLR-IS
 -A21N/M-SDE3FGHIJ1J4J5M1P2RWXYZ/LB1D1G1
 -LFBO1655
 -N0454F310 GAUDE7A GAUDE DCT LATEK DCT PPN DCT MIRPO DCT DGO N725
  RATAS/N0452F320 DCT NEDUS DCT NUBLO
 -CYUL0748 CYOW
 -PBN/A1B1C1D1L1O2S2T1 NAV/RNP2 DAT/1PDC SUR/260B RSP180 CANMANDATE
  DOF/261003 REG/CGXLR EET/LECM0021 LPPO0134 43N020W0215
  PER/C RALT/LPPR LPLA CYQX RMK/NRP TCAS)
"""

# Synthetic: an airline's ICAO flight plan with no times table.
ICAO_FPL = """
 (FPL-ABC1234-IS
 -B739/M-SDE2E3FGHIJ2J3J4J5M1RWXY/LB1D1
 -KATL2340
 -N0455F360 JCOXX4 SMKEY Q34 IZAAC J52 ABQ
 -KLAX0420 KONT
 -PBN/A1B1C1D1O1S2 DOF/260214 REG/N801DZ RMK/TCAS)
"""


def make_pdf(text):
    """A one-page PDF with the text in Courier, as an OFP prints."""
    escape = lambda line: line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    stream = 'BT /F1 8 Tf 10 TL 20 800 Td ' + ' '.join(f'({escape(line)}) Tj T*' for line in text.splitlines()) + ' ET'
    objects = [
        '<< /Type /Catalog /Pages 2 0 R >>',
        '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
        f'<< /Length {len(stream)} >>\nstream\n{stream}\nendstream',
        '<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>',
    ]
    out, offsets = '%PDF-1.4\n', []
    for i, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f'{i} 0 obj\n{body}\nendobj\n'
    xref = len(out)
    out += f'xref\n0 {len(objects) + 1}\n0000000000 65535 f \n' + ''.join(f'{o:010d} 00000 n \n' for o in offsets)
    out += f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'
    return out.encode('latin-1')


class FlightPlanParserTests(SimpleTestCase):
    def test_simbrief(self):
        result = flight_plans.parse(SIMBRIEF_OFP)
        self.assertEqual((result['source'], result['callsign'], result['warnings']), ('simbrief', 'CGXLR', []))
        flight = result['flight']
        self.assertEqual((flight['departure_airport'], flight['arrival_airport']), ('LFBO', 'CYUL'))
        # The scheduled column, with IN rolling over midnight.
        self.assertEqual((flight['departure_time'], flight['arrival_time']), ('2026-10-03T16:55:00+00:00', '2026-10-04T01:25:00+00:00'))
        self.assertEqual((flight['registration_number'], flight['aircraft_type'], flight['distance']), ('C-GXLR', 'A21N', 3312))
        self.assertEqual(flight['flight_plan'], 'GAUDE7A GAUDE DCT LATEK DCT PPN DCT MIRPO DCT DGO N725 RATAS DCT NEDUS DCT NUBLO')
        self.assertTrue(flight['is_simulator'])
        self.assertIn('Alternate: CYOW', flight['notes'])

    def test_icao_plan_without_times_table(self):
        result = flight_plans.parse(ICAO_FPL)
        flight = result['flight']
        self.assertEqual((result['source'], result['callsign']), ('icao', 'ABC1234'))
        self.assertEqual((flight['departure_airport'], flight['arrival_airport'], flight['registration_number']), ('KATL', 'KLAX', 'N801DZ'))
        self.assertEqual(flight['aircraft_type'], 'B739')
        self.assertFalse(flight['is_simulator'])
        # Off-block plus EET, across midnight UTC.
        self.assertEqual((flight['departure_time'], flight['arrival_time']), ('2026-02-14T23:40:00+00:00', '2026-02-15T04:00:00+00:00'))
        self.assertEqual(flight['distance'], 0)
        self.assertTrue(any('taxi' in w for w in result['warnings']))

    def test_no_flight_plan(self):
        with self.assertRaisesMessage(flight_plans.FlightPlanError, 'ATC flight plan'):
            flight_plans.parse('A dinner menu')

    def test_pdf_text(self):
        self.assertEqual(flight_plans.read(make_pdf(SIMBRIEF_OFP))['flight']['arrival_time'], '2026-10-04T01:25:00+00:00')
        with self.assertRaises(flight_plans.FlightPlanError):
            flight_plans.read(b'%PDF-1.4 not really')


class DraftFlightTests(ApiTestCase):
    def upload(self, data, name='ofp.pdf'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return self.client.post('/api/flights/from-plan/', {'file': SimpleUploadedFile(name, data, content_type='application/pdf')}, format='multipart')

    def test_upload_returns_a_draft_without_saving(self):
        self.authenticate()
        res = self.upload(make_pdf(ICAO_FPL))
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['flight']['arrival_airport'], 'KLAX')
        self.assertFalse(Flight.objects.exists())

        self.assertEqual(self.upload(b'name,date\n', 'plan.csv').status_code, 400)
        self.assertEqual(self.upload(make_pdf('Nothing here')).status_code, 422)
        self.client.credentials()
        self.assertEqual(self.upload(make_pdf(ICAO_FPL)).status_code, 401)

    def test_drafts_stay_out_of_totals_until_finalised(self):
        self.authenticate()
        self.client.patch('/api/me/', {'is_public': True}, format='json')
        self.add_flight()
        draft = self.add_flight(is_draft=True, departure_time='2026-02-01T10:00:00Z', arrival_time='2026-02-01T12:00:00Z', total_time='02:00:00')

        self.assertEqual(self.client.get('/api/stats/').data['totals']['flights'], 1)
        self.assertEqual(self.client.get('/api/aircraft/').data[0]['total_flights'], 1)
        self.assertEqual(self.client.get('/api/flights/').data['count'], 2)
        self.assertEqual([f['id'] for f in self.client.get('/api/flights/?draft=true').data['results']], [draft['id']])
        self.assertEqual(self.client.get('/api/flights/export/').content.decode().count('KJFK'), 1)
        self.assertEqual(self.client.get(f"/api/public/flights/{draft['id']}/").status_code, 404)
        self.assertEqual(self.client.get('/api/rankings/').data['flights'][0]['total_flights'], 1)

        res = self.client.patch(f"/api/flights/{draft['id']}/", {'is_draft': False}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(self.client.get('/api/stats/').data['totals']['flights'], 2)

    def test_grounding_applies_when_a_flight_enters_the_logbook(self):
        self.authenticate()
        draft = self.add_flight(is_draft=True, aircraft_condition='GROUNDED')
        self.assertFalse(Aircraft.objects.get().grounded)

        self.add_flight(departure_time='2026-01-02T10:00:00Z', arrival_time='2026-01-02T15:30:00Z', aircraft_condition='GROUNDED')
        # Planning in a grounded aircraft is fine; logging it isn't.
        planned = self.add_flight(is_draft=True, departure_time='2026-01-03T10:00:00Z', arrival_time='2026-01-03T15:30:00Z')
        res = self.client.patch(f"/api/flights/{planned['id']}/", {'is_draft': False}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('grounded', str(res.data))
        self.assertTrue(Flight.objects.get(pk=draft['id']).is_draft)


class RealismTests(ApiTestCase):
    """Flights that couldn't have happened stay out of the logbook; fast ones still get in."""

    def post(self, **overrides):
        return self.client.post('/api/flights/', {**FLIGHT, **overrides}, format='json')

    def errors(self, res):
        """The field errors of a rejected flight; the create view wraps them."""
        self.assertEqual(res.status_code, 400, res.data)
        return res.data.get('errors', res.data)

    def test_rejects_an_impossible_ground_speed(self):
        self.authenticate()
        res = self.post(arrival_time='2026-01-01T10:20:00Z', total_time='00:20:00')
        self.assertIn('kt', str(self.errors(res)['distance']))
        self.assertFalse(Flight.objects.exists())

    def test_allows_a_supersonic_airliner(self):
        self.authenticate()
        # EGLL-KJFK in 2h55m, the Concorde's schedule: about 1,030 kt over the ground.
        res = self.post(
            departure_airport='EGLL', arrival_airport='KJFK', distance=2999,
            departure_time='2026-01-01T10:00:00Z', arrival_time='2026-01-01T12:55:00Z', total_time='02:55:00',
        )
        self.assertEqual(res.status_code, 201, res.data)

    def test_a_simulator_session_may_reposition(self):
        self.authenticate()
        res = self.post(arrival_time='2026-01-01T10:20:00Z', total_time='00:20:00', is_simulator=True)
        self.assertEqual(res.status_code, 201, res.data)

    def test_rejects_a_flight_that_hasnt_happened(self):
        self.authenticate()
        start = datetime.now(dt_timezone.utc) + timedelta(days=3)
        times = {'departure_time': start.isoformat(), 'arrival_time': (start + timedelta(hours=5, minutes=30)).isoformat()}
        res = self.post(**times)
        self.assertIn('arrival_time', self.errors(res))
        # Planning that same flight is what drafts are for.
        self.assertEqual(self.post(**times, is_draft=True).status_code, 201)

    def test_rejects_dates_outside_the_age_of_flight(self):
        self.authenticate()
        res = self.post(departure_time='1899-01-01T10:00:00Z', arrival_time='1899-01-01T15:30:00Z')
        self.assertIn('1903', str(self.errors(res)['departure_time']))

        res = self.post(departure_time='2062-01-01T10:00:00Z', arrival_time='2062-01-01T15:30:00Z', is_draft=True)
        self.assertIn('departure_time', self.errors(res))

    def test_rejects_a_flight_that_lasts_days(self):
        self.authenticate()
        res = self.post(arrival_time='2026-01-04T10:00:00Z', total_time='3 00:00:00')
        self.assertIn('total_time', self.errors(res))

    def test_rejects_more_landings_and_approaches_than_there_was_time_for(self):
        self.authenticate()
        circuits = {
            'arrival_airport': 'KJFK', 'distance': 0,
            'arrival_time': '2026-01-01T11:00:00Z', 'total_time': '01:00:00',
        }
        self.assertEqual(self.post(**circuits, day_landings=12, night_landings=4).status_code, 201)

        res = self.post(**circuits, day_landings=10, night_landings=30)
        self.assertIn('circuits', str(self.errors(res)['night_landings']))

        res = self.post(**circuits, approaches=20)
        self.assertIn('approaches', self.errors(res))

    def test_rejects_a_distance_shorter_than_the_airports_allow(self):
        self.authenticate()
        res = self.post(distance=214)
        self.assertIn('nm apart', str(self.errors(res)['distance']))
        # A route that wanders is fine; only an impossibly short one isn't.
        self.assertEqual(self.post(distance=2400).status_code, 201)

    def test_rejects_negative_hours(self):
        self.authenticate()
        res = self.post(pic_time='-01:00:00')
        self.assertIn('negative', str(self.errors(res)['pic_time']))

    def test_an_edit_cant_make_a_flight_unrealistic(self):
        self.authenticate()
        flight = self.add_flight()
        res = self.client.patch(f"/api/flights/{flight['id']}/", {'approaches': 99}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Flight.objects.get().approaches, 0)

    def test_import_skips_unrealistic_rows(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.authenticate()
        text = (
            'departure_airport,arrival_airport,departure_time,arrival_time,registration_number\n'
            'KJFK,KBOS,2026-01-01T10:00:00Z,2026-01-01T11:00:00Z,N1\n'
            'KJFK,EGLL,2026-01-02T10:00:00Z,2026-01-02T10:20:00Z,N1\n'
        )
        res = self.client.post(
            '/api/flights/import/',
            {'file': SimpleUploadedFile('logbook.csv', text.encode(), content_type='text/csv')},
            format='multipart',
        )
        self.assertEqual((res.data['created'], res.data['skipped']), (1, 1), res.data)
        self.assertIn('distance', res.data['errors'][0]['errors'])


GEMINI = {'name': 'gemini', 'base_url': 'https://gemini.test/', 'api_key': 'g-key', 'model': 'gemini-test'}
GROQ = {'name': 'groq', 'base_url': 'https://groq.test/', 'api_key': 'q-key', 'model': 'groq-test'}
NOW = datetime(2026, 10, 6, 14, 0)


def completion(content):
    return mock.Mock(choices=[mock.Mock(message=mock.Mock(content=content))])


class QuickLogCleanTests(SimpleTestCase):
    def clean(self, fleet=(), **data):
        return quick_log.clean(data, list(fleet))

    def test_fills_checked_fields(self):
        result = self.clean(
            fleet=[('N12345', 'C172')],
            departure_airport='kpao', arrival_airport='KSQL',
            departure_time='2026-10-06T09:00', arrival_time='2026-10-06T10:24', total_hours=1.4,
            registration_number='n12345', pic_hours=1.4, simulated_instrument_hours=0.3,
            day_landings=3, night_landings=0.0, approaches=None, cross_country=False, notes=' Gusty. ',
        )
        self.assertEqual(result['flight'], {
            'departure_airport': 'KPAO', 'arrival_airport': 'KSQL',
            'departure_time': '2026-10-06T09:00', 'arrival_time': '2026-10-06T10:24',
            'registration_number': 'N12345', 'pic_time': '1:24', 'simulated_instrument_time': '0:18',
            'day_landings': 3, 'night_landings': 0, 'cross_country': False, 'notes': 'Gusty.',
        })
        self.assertEqual(result['warnings'], [])

    def test_unknown_airport_and_bad_values_are_dropped(self):
        result = self.clean(departure_airport='ZZZZ', pic_hours=30, day_landings='lots', is_simulator='yes', registration_number='N 1@')
        self.assertEqual(result['flight'], {})
        self.assertEqual(len(result['warnings']), 2)
        self.assertIn('ZZZZ', result['warnings'][0])

    def test_arrival_from_total_and_after_midnight(self):
        flight = self.clean(departure_time='2026-10-05T23:00', total_hours=1.5)['flight']
        self.assertEqual(flight['arrival_time'], '2026-10-06T00:30')
        flight = self.clean(departure_time='2026-10-05T23:00', arrival_time='2026-10-05T00:30')['flight']
        self.assertEqual(flight['arrival_time'], '2026-10-06T00:30')

    def test_warns_when_times_disagree_or_are_missing(self):
        result = self.clean(departure_time='2026-10-06T09:00', arrival_time='2026-10-06T11:00', total_hours=1.2)
        self.assertIn('Check them', result['warnings'][0])
        result = self.clean(total_hours=1.2)
        self.assertNotIn('departure_time', result['flight'])
        self.assertIn('Add the departure and arrival times.', result['warnings'])

    def test_warns_about_aircraft_outside_the_fleet(self):
        result = self.clean(fleet=[('N12345', 'C172')], registration_number='N999AB')
        self.assertEqual(result['flight']['registration_number'], 'N999AB')
        self.assertIn('isn’t in your fleet', result['warnings'][0])

    def test_prompt_has_local_time_fleet_and_text(self):
        user = quick_log.build_messages('KPAO pattern work', NOW, [('N12345', 'C172'), ('N54321', '')])[1]['content']
        self.assertIn('Tuesday 2026-10-06 14:00', user)
        self.assertIn('- N12345 (C172)', user)
        self.assertIn('- N54321\n', user)
        self.assertIn('KPAO pattern work', user)


class QuickLogApiTests(ApiTestCase):
    url = '/api/flights/quick-log/'

    def post(self, text='KPAO to KSQL, 1.4 hours', **extra):
        return self.client.post(self.url, {'text': text, 'now': '2026-10-06T14:00', **extra}, format='json')

    @override_settings(QUICK_LOG_PROVIDERS=[GEMINI])
    def test_reads_description_into_form_fields(self):
        self.authenticate()
        self.client.post('/api/aircraft/', {'registration': 'N12345', 'type_code': 'C172'}, format='json')
        answer = '```json\n{"departure_airport": "KPAO", "arrival_airport": "KSQL", "registration_number": "N12345"}\n```'
        with mock.patch('flights.quick_log.OpenAI') as client_cls:
            create = client_cls.return_value.chat.completions.create
            create.return_value = completion(answer)
            res = self.post()
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['flight'], {'departure_airport': 'KPAO', 'arrival_airport': 'KSQL', 'registration_number': 'N12345'})
        self.assertEqual(client_cls.call_args.kwargs['base_url'], 'https://gemini.test/')
        self.assertEqual(create.call_args.kwargs['model'], 'gemini-test')
        prompt = create.call_args.kwargs['messages'][1]['content']
        self.assertIn('N12345 (C172)', prompt)
        self.assertIn('2026-10-06 14:00', prompt)
        self.assertFalse(Flight.objects.exists())

    @override_settings(QUICK_LOG_PROVIDERS=[GEMINI, GROQ])
    def test_falls_back_to_the_next_provider(self):
        from openai import RateLimitError
        self.authenticate()
        limited = RateLimitError('quota', response=mock.Mock(status_code=429), body=None)
        with mock.patch('flights.quick_log.OpenAI') as client_cls:
            client_cls.return_value.chat.completions.create.side_effect = [limited, completion('{"departure_airport": "KPAO"}')]
            res = self.post()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['flight'], {'departure_airport': 'KPAO'})
        self.assertEqual([c.kwargs['api_key'] for c in client_cls.call_args_list], ['g-key', 'q-key'])

    @override_settings(QUICK_LOG_PROVIDERS=[GEMINI])
    def test_unavailable_when_every_provider_fails(self):
        self.authenticate()
        with mock.patch('flights.quick_log.OpenAI') as client_cls:
            client_cls.return_value.chat.completions.create.return_value = completion('not json')
            res = self.post()
        self.assertEqual(res.status_code, 503)
        self.assertNotIn('json', res.data['error'].lower())

    @override_settings(QUICK_LOG_PROVIDERS=[])
    def test_disabled_without_a_provider(self):
        self.authenticate()
        self.assertEqual(self.client.get(self.url).data, {'enabled': False})
        self.assertEqual(self.post().status_code, 503)
        with override_settings(QUICK_LOG_PROVIDERS=[GEMINI]):
            self.assertEqual(self.client.get(self.url).data, {'enabled': True})

    @override_settings(QUICK_LOG_PROVIDERS=[GEMINI])
    def test_rejects_empty_long_and_useless_text(self):
        self.authenticate()
        with mock.patch('flights.quick_log.OpenAI') as client_cls:
            client_cls.return_value.chat.completions.create.return_value = completion('{"departure_airport": null}')
            self.assertEqual(self.post('  ').status_code, 422)
            self.assertEqual(self.post('x' * 1001).status_code, 422)
            self.assertEqual(client_cls.call_count, 0)
            res = self.post('nice day')
        self.assertEqual(res.status_code, 422)
        self.assertIn('Couldn’t find any flight details', res.data['error'])

    def test_requires_sign_in(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(self.post().status_code, 401)

    @override_settings(QUICK_LOG_PROVIDERS=[GEMINI])
    def test_is_throttled(self):
        from rest_framework.settings import api_settings
        self.authenticate()
        rates = {**api_settings.DEFAULT_THROTTLE_RATES, 'quick_log': '2/hour'}
        with mock.patch('flights.views.QuickLogThrottle.THROTTLE_RATES', rates), mock.patch('flights.quick_log.OpenAI') as client_cls:
            client_cls.return_value.chat.completions.create.return_value = completion('{"departure_airport": "KPAO"}')
            codes = [self.post().status_code for _ in range(3)]
            self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(codes, [200, 200, 429])


def log(user, when, dep='KPAO', arr='KSQL', hours=1.0, distance=100, **extra):
    """A flight straight into the database, skipping validation so tests can place it anywhere in time."""
    if not isinstance(when, datetime):
        when = datetime.combine(when, datetime.min.time(), dt_timezone.utc) + timedelta(hours=17)
    return Flight.objects.create(
        user=user, departure_airport=dep, arrival_airport=arr, departure_time=when,
        arrival_time=when + timedelta(hours=hours), total_time=timedelta(hours=hours),
        registration_number=extra.pop('registration_number', 'N123'), distance=distance, **extra,
    )


class PatternTests(ApiTestCase):
    today = date(2026, 6, 1)

    def setUp(self):
        super().setUp()
        self.authenticate()
        self.user = get_user_model().objects.get(username='pilot')

    def findings(self):
        from .views import fleet
        found = patterns.findings(Flight.objects.logged().filter(user=self.user), fleet(self.user), self.today)
        return {f['key']: f for f in found}

    def test_recency(self):
        log(self.user, self.today - timedelta(days=45))
        self.assertEqual(self.findings()['recency']['tone'], 'notice')
        log(self.user, self.today - timedelta(days=70))
        log(self.user, self.today - timedelta(days=5), is_draft=True)  # planned, not flown
        Flight.objects.filter(departure_time__date=self.today - timedelta(days=45)).delete()
        self.assertEqual(self.findings()['recency']['title'], '70 days since you last flew')
        log(self.user, self.today - timedelta(days=5))
        self.assertNotIn('recency', self.findings())

    def test_trend(self):
        for days in (10, 20):
            log(self.user, self.today - timedelta(days=days))
        for days in (100, 120, 150):
            log(self.user, self.today - timedelta(days=days), hours=2)
        trend = self.findings()['trend']
        self.assertEqual((trend['tone'], trend['title']), ('notice', 'You’re flying 67% less'))
        self.assertIn('2.0 h in the last 90 days, down from 6.0 h', trend['detail'])

    def test_route_concentration_and_new_airports(self):
        log(self.user, self.today - timedelta(days=400))
        for i in range(6):
            log(self.user, self.today - timedelta(days=10 + i), *(('KSQL', 'KPAO') if i % 2 else ('KPAO', 'KSQL')))
        for i, dest in enumerate(('KSFO', 'KOAK', 'KSJC')):
            log(self.user, self.today - timedelta(days=30 + i), arr=dest)
        found = self.findings()
        self.assertEqual(found['concentration']['title'], 'Most of your flying is KPAO–KSQL')
        self.assertIn('6 of your 9 flights', found['concentration']['detail'])
        self.assertEqual(found['new_airports']['detail'], 'KOAK, KSFO, KSJC')

    def test_unused_skills(self):
        log(self.user, self.today - timedelta(days=400), night_landings=3, approaches=2)
        log(self.user, self.today - timedelta(days=20))
        found = self.findings()
        self.assertIn('night_unused', found)
        self.assertIn('instrument_unused', found)
        log(self.user, self.today - timedelta(days=30), approaches=1, is_simulator=True)
        found = self.findings()
        self.assertNotIn('instrument_unused', found)
        self.assertIn('night_unused', found)  # simulator landings aren't night flying

    def test_maintenance(self):
        grounded = Aircraft.objects.create(user=self.user, registration='N1', grounded=True)
        annual = Aircraft.objects.create(user=self.user, registration='N2', annual_due=self.today + timedelta(days=10))
        Aircraft.objects.create(user=self.user, registration='N3', annual_due=self.today + timedelta(days=200))
        found = self.findings()
        self.assertEqual(found[f'maintenance_{grounded.pk}']['tone'], 'warning')
        self.assertEqual(found[f'maintenance_{annual.pk}']['title'], 'N2’s annual is due in about 10 days')
        self.assertEqual(len([k for k in found if k.startswith('maintenance_')]), 2)

    def test_api(self):
        res = self.client.get('/api/insights/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['findings'], [])
        self.assertIn('themes_enabled', res.data)
        self.client.credentials()
        self.assertEqual(self.client.get('/api/insights/').status_code, 401)


class NoteThemeTests(ApiTestCase):
    url = '/api/insights/themes/'

    def setUp(self):
        super().setUp()
        self.authenticate()
        self.user = get_user_model().objects.get(username='pilot')

    def noted(self, *notes):
        return [log(self.user, date(2026, 5, 1) + timedelta(days=i), notes=n) for i, n in enumerate(notes)]

    def test_clean_keeps_only_themes_backed_by_two_flights(self):
        a, b, c = self.noted('Floated the landing', 'Floated again', 'Nice day')
        data = {'themes': [
            {'title': ' Floating landings ', 'kind': 'struggle', 'summary': 'You float.', 'flights': [a.id, f'#{b.id}', b.id, 99999]},
            {'title': 'One-off', 'kind': 'struggle', 'summary': 'Once.', 'flights': [c.id, 99999]},
            {'title': 'No summary', 'kind': 'strength', 'summary': '', 'flights': [a.id, b.id]},
            {'title': 'Odd kind', 'kind': 'advice', 'summary': 'Hmm.', 'flights': [a.id, c.id]},
            'not a theme',
        ]}
        themes = patterns.clean_themes(data, [a, b, c])
        self.assertEqual([t['title'] for t in themes], ['Floating landings', 'Odd kind'])
        self.assertEqual([f['id'] for f in themes[0]['flights']], [a.id, b.id])
        self.assertEqual(themes[0]['flights'][0]['route'], 'KPAO → KSQL')
        self.assertEqual(themes[1]['kind'], 'observation')
        self.assertEqual(patterns.clean_themes({'themes': 'nope'}, [a]), [])
        self.assertEqual(patterns.clean_themes([], [a]), [])

    @override_settings(QUICK_LOG_PROVIDERS=[GEMINI])
    def test_reads_notes_of_logged_flights(self):
        a, b, c = self.noted('Crosswind was rough', 'Crosswind again, side-slipped', 'Smooth')
        log(self.user, date(2026, 5, 10), notes='Planned: practise crosswinds', is_draft=True)
        answer = {'themes': [{'title': 'Crosswind landings', 'kind': 'struggle', 'summary': 'Crosswinds keep coming up.', 'flights': [a.id, b.id]}]}
        with mock.patch('flights.quick_log.OpenAI') as client_cls:
            create = client_cls.return_value.chat.completions.create
            create.return_value = completion(json.dumps(answer))
            res = self.client.post(self.url)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['notes_read'], 3)
        self.assertEqual(res.data['themes'][0]['title'], 'Crosswind landings')
        prompt = create.call_args.kwargs['messages'][1]['content']
        self.assertIn(f'#{b.id} 2026-05-02 KPAO-KSQL: Crosswind again, side-slipped', prompt)
        self.assertNotIn('Planned', prompt)

    @override_settings(QUICK_LOG_PROVIDERS=[GEMINI])
    def test_needs_enough_notes(self):
        self.noted('Only one note')
        with mock.patch('flights.quick_log.OpenAI') as client_cls:
            res = self.client.post(self.url)
        self.assertEqual(res.status_code, 422)
        self.assertEqual(client_cls.call_count, 0)

    @override_settings(QUICK_LOG_PROVIDERS=[])
    def test_unavailable_without_a_provider(self):
        self.noted('a', 'b', 'c')
        self.assertEqual(self.client.post(self.url).status_code, 503)
        self.assertFalse(self.client.get('/api/insights/').data['themes_enabled'])


class AskCleanTests(SimpleTestCase):
    fleet = [('N172SP', 'C172'), ('N738CK', 'C172'), ('N44PA', 'PA28')]

    def test_metric_keys_come_from_summary(self):
        self.assertLessEqual(set(ask.METRICS), set(insights.summary(Flight.objects.none())['totals']))
        self.assertEqual(set(ask.CURRENCY), {c['key'] for c in insights.currency(Flight.objects.none())})

    def test_keeps_valid_filters(self):
        asked = ask.clean({'metric': 'night_hours', 'from': '2026-03-01', 'to': '2026-10-17', 'aircraft': 'c172',
                           'airport': 'ksql', 'simulator': False}, self.fleet)
        self.assertEqual(asked['metric'], 'night_hours')
        self.assertEqual(asked['filters'], {'from': '2026-03-01', 'to': '2026-10-17', 'aircraft': 'C172', 'airport': 'KSQL', 'simulator': False})
        self.assertEqual(asked['registrations'], ['N172SP', 'N738CK'])
        self.assertEqual(asked['warnings'], [])

    def test_drops_what_it_cannot_check(self):
        asked = ask.clean({'metric': 'hours', 'from': '2026-02-30', 'to': 'soon', 'aircraft': 'N999ZZ', 'airport': 'ZZZZ', 'simulator': 'yes'}, self.fleet)
        self.assertEqual(asked['filters'], {})
        self.assertEqual(len(asked['warnings']), 3)
        reversed_range = ask.clean({'metric': 'hours', 'from': '2026-05-01', 'to': '2026-04-01'}, self.fleet)
        self.assertEqual(reversed_range['filters'], {})
        self.assertEqual(len(reversed_range['warnings']), 1)

    def test_bounds_model_text_in_warnings(self):
        asked = ask.clean({'metric': 'hours', 'aircraft': 'Z' * 400, 'airport': 'Z' * 400}, self.fleet)
        self.assertEqual(asked['filters'], {})
        self.assertEqual(len(asked['warnings']), 2)
        for warning in asked['warnings']:
            self.assertIn('Z' * 12, warning)
            self.assertNotIn('Z' * 13, warning)

    def test_currency_question(self):
        asked = ask.clean({'currency': 'passenger_night', 'metric': 'night_landings', 'from': '2026-01-01'}, self.fleet)
        self.assertEqual(asked['currency'], 'passenger_night')
        self.assertNotIn('metric', asked)
        self.assertEqual(len(asked['warnings']), 1)
        self.assertEqual(ask.clean({'currency': 'instrument'}, self.fleet)['warnings'], [])

    def test_refuses_anything_else(self):
        for data in ({}, {'metric': 'longest_flight'}, {'currency': 'medical'}, [], {'metric': None, 'currency': None}, {'metric': ['night_hours']}):
            with self.assertRaises(ask.AskError):
                ask.clean(data, self.fleet)


class AskApiTests(ApiTestCase):
    url = '/api/stats/ask/'

    def setUp(self):
        super().setUp()
        self.authenticate()
        self.user = get_user_model().objects.get(username='pilot')
        Aircraft.objects.create(user=self.user, registration='N172SP', type_code='C172')
        Aircraft.objects.create(user=self.user, registration='N44PA', type_code='PA28')

    def ask(self, answer, question='How much night time in the C172 since March?'):
        with mock.patch('flights.quick_log.OpenAI') as client_cls:
            create = client_cls.return_value.chat.completions.create
            create.return_value = completion(json.dumps(answer))
            res = self.client.post(self.url, {'question': question, 'now': '2026-10-17T09:00'}, format='json')
        return res, create

    @override_settings(QUICK_LOG_PROVIDERS=[GEMINI])
    def test_totals_come_from_the_logbook(self):
        log(self.user, date(2026, 4, 1), registration_number='N172SP', night_time=timedelta(hours=1.5))
        log(self.user, date(2026, 5, 1), registration_number='N172SP', night_time=timedelta(hours=0.5))
        log(self.user, date(2026, 2, 1), registration_number='N172SP', night_time=timedelta(hours=4))
        log(self.user, date(2026, 5, 2), registration_number='N44PA', night_time=timedelta(hours=4))
        log(self.user, date(2026, 6, 1), registration_number='N172SP', night_time=timedelta(hours=4), is_draft=True)
        res, create = self.ask({'metric': 'night_hours', 'from': '2026-03-01', 'aircraft': 'C172', 'value': 99})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['kind'], 'total')
        self.assertEqual(res.data['value'], 2.0)
        self.assertEqual(res.data['label'], 'Night hours')
        self.assertEqual(res.data['filters'], {'from': '2026-03-01', 'aircraft': 'C172'})
        prompt = create.call_args.kwargs['messages'][1]['content']
        self.assertIn('2026-10-17', prompt)
        self.assertIn('N172SP (C172)', prompt)

    @override_settings(QUICK_LOG_PROVIDERS=[GEMINI])
    def test_currency_comes_from_insights(self):
        today = timezone.now().date()
        log(self.user, today - timedelta(days=10), night_landings=3)
        res, _ = self.ask({'currency': 'passenger_night'}, 'Am I current for passengers at night?')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['kind'], 'currency')
        self.assertEqual(res.data['currency']['key'], 'passenger_night')
        self.assertEqual(res.data['currency']['status'], 'current')

    @override_settings(QUICK_LOG_PROVIDERS=[GEMINI])
    def test_unsupported_and_empty_questions(self):
        res, _ = self.ask({'metric': None, 'currency': None}, 'What was my longest flight?')
        self.assertEqual(res.status_code, 422)
        res, create = self.ask({'metric': 'hours'}, '  ')
        self.assertEqual(res.status_code, 422)
        self.assertEqual(create.call_count, 0)

    @override_settings(QUICK_LOG_PROVIDERS=[])
    def test_unavailable_without_a_provider(self):
        res, _ = self.ask({'metric': 'hours'})
        self.assertEqual(res.status_code, 503)


class PlanReviewTests(ApiTestCase):
    now = datetime(2026, 11, 20, 12, 0, tzinfo=dt_timezone.utc)

    def setUp(self):
        super().setUp()
        self.authenticate()
        self.user = get_user_model().objects.get(username='pilot')

    def plan(self, when, dep='KPAO', arr='KSQL', hours=1.0, distance=100, **extra):
        return log(self.user, when, dep, arr, hours, distance, is_draft=True, **extra)

    def review(self, flight, aircraft=None):
        history = Flight.objects.logged().filter(user=self.user)
        return {c['key']: c for c in plan_review.review(flight, history, aircraft, now=self.now)['checks']}

    def test_sun_elevation(self):
        jfk = airports.get('KJFK')
        self.assertAlmostEqual(plan_review.sun_elevation(jfk.lat, jfk.lon, datetime(2026, 6, 21, 17, 0, tzinfo=dt_timezone.utc)), 72.5, delta=1.5)
        self.assertTrue(plan_review.is_dark(jfk, datetime(2026, 6, 21, 4, 0, tzinfo=dt_timezone.utc)))
        self.assertFalse(plan_review.is_dark(jfk, datetime(2026, 6, 21, 12, 0, tzinfo=dt_timezone.utc)))

    def test_block_time_long_leg_and_new_airport(self):
        for day in range(1, 4):
            log(self.user, date(2026, 11, day), night_landings=1, day_landings=2, approaches=2)
        checks = self.review(self.plan(date(2026, 11, 25), arr='KLAX', hours=2, distance=300))
        self.assertIn('assumes 150 kt block to block; your 3 flights in N123 average 100 kt', checks['block_speed']['detail'])
        self.assertIn('Budget about 3:00 block time, landing around 20:00Z', checks['block_speed']['suggestion'])
        self.assertIn('300 nm, against 100 nm', checks['long_leg']['detail'])
        self.assertEqual(checks['new_airport']['detail'], 'Los Angeles International Airport')
        self.assertNotIn('passenger_currency', checks)

        checks = self.review(self.plan(date(2026, 11, 25), hours=1, distance=110))
        self.assertEqual(set(checks), set())  # a plan like the ones they fly

    def test_speed_falls_back_to_type(self):
        aircraft = Aircraft.objects.create(user=self.user, registration='N456', type_code='C172')
        sister = Aircraft.objects.create(user=self.user, registration='N123', type_code='C172')
        for day in range(1, 4):
            log(self.user, date(2026, 11, day), aircraft=sister, day_landings=1)
        checks = self.review(self.plan(date(2026, 11, 25), hours=1, distance=200, registration_number='N456'), aircraft)
        self.assertIn('your 3 flights in the C172 average 100 kt', checks['block_speed']['detail'])

    def test_night_arrival_without_currency(self):
        log(self.user, date(2026, 11, 1), day_landings=3)
        # Boston in December: civil twilight ends around 21:45Z.
        draft = self.plan(datetime(2026, 12, 1, 22, 30, tzinfo=dt_timezone.utc), 'KJFK', 'KBOS', distance=160)
        checks = self.review(draft)
        night = checks['night_currency']
        self.assertEqual(night['tone'], 'warning')
        self.assertRegex(night['detail'], r'Civil twilight ends at 21:[34]\dZ at KBOS')
        self.assertRegex(night['suggestion'], r'^Leave by 20:[34]\dZ to land before dark')
        self.assertEqual(list(checks)[0], 'night_currency')  # warnings first

        log(self.user, date(2026, 11, 10), night_landings=3)
        checks = self.review(draft)
        self.assertNotIn('night_currency', checks)
        self.assertEqual(checks['night']['tone'], 'info')

    def test_currency_on_the_day_of_the_flight(self):
        # Six approaches in April keep them instrument current to the end of October only.
        log(self.user, date(2026, 4, 1), day_landings=3, approaches=6)
        checks = self.review(self.plan(date(2026, 11, 25)))
        self.assertIn('you’ll have 0', checks['passenger_currency']['detail'])
        self.assertIn('2026-11-25', checks['instrument_currency']['title'])

    def test_aircraft(self):
        aircraft = Aircraft.objects.create(user=self.user, registration='N123', maintenance_interval_hours=2, annual_due=date(2026, 11, 22))
        log(self.user, date(2026, 11, 1), aircraft=aircraft, day_landings=3)
        checks = self.review(self.plan(date(2026, 11, 25), hours=1.5, distance=150), aircraft)
        self.assertIn('1.0 h left on the inspection; this flight is 1.5 h', checks['inspection']['detail'])
        self.assertEqual(checks['annual']['tone'], 'warning')
        aircraft.grounded = True
        checks = self.review(self.plan(date(2026, 11, 25)), aircraft)
        self.assertEqual(checks['grounded']['tone'], 'warning')
        self.assertNotIn('inspection', checks)

    def test_weather_close_to_departure(self):
        log(self.user, date(2026, 11, 1), day_landings=3)
        reports = {'KPAO': {'flight_category': 'IFR', 'raw': 'KPAO 201153Z 00000KT 1/2SM FG OVC002'}, 'KSQL': {'flight_category': 'VFR', 'raw': ''}}
        soon = self.plan(self.now + timedelta(hours=1))
        with mock.patch('flights.plan_review.external.metar', side_effect=lambda code: reports[code]) as metar:
            checks = self.review(soon)
            self.review(self.plan(self.now + timedelta(days=2)))
        self.assertEqual(metar.call_count, 2)  # only for the flight leaving soon
        self.assertEqual(checks['weather_KPAO']['title'], 'KPAO is IFR right now')
        self.assertNotIn('weather_KSQL', checks)
        with mock.patch('flights.plan_review.external.metar', side_effect=external.ExternalLookupError('down')):
            self.assertNotIn('weather_KPAO', self.review(soon))

    def test_api(self):
        draft = self.add_flight(is_draft=True, departure_time='2026-12-01T15:00:00Z', arrival_time='2026-12-01T20:30:00Z', total_time='05:30:00')
        logged = self.add_flight()
        with mock.patch('flights.plan_review.external.metar') as metar:
            res = self.client.get(f"/api/flights/{draft['id']}/review/")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertFalse(res.data['simulator'])
        self.assertIn('passenger_currency', [c['key'] for c in res.data['checks']])
        metar.assert_not_called()
        self.assertEqual(self.client.get(f"/api/flights/{logged['id']}/review/").status_code, 400)

        sim = self.plan(date(2026, 12, 2), is_simulator=True)
        self.assertEqual(self.client.get(f'/api/flights/{sim.id}/review/').data, {'checks': [], 'simulator': True})

        self.authenticate('other')
        self.assertEqual(self.client.get(f"/api/flights/{draft['id']}/review/").status_code, 404)


class CrewTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.register('maria')
        self.register('sam')
        self.authenticate()
        self.flight = self.add_flight(notes='mine', day_landings=1, pic_time='05:30:00')

    def invite(self, username='maria', role='SIC', flight=None):
        return self.client.post(f"/api/flights/{(flight or self.flight)['id']}/crew/", {'username': username, 'role': role}, format='json')

    def crew(self, flight_id):
        return {(m['username'], m['role'], m['status']) for m in self.client.get(f'/api/flights/{flight_id}/crew/').data}

    def accept_as(self, username='maria'):
        self.authenticate(username)
        invite = self.client.get('/api/crew/invites/').data[0]
        return self.client.post(f"/api/crew/{invite['id']}/accept/")

    def test_accepting_adds_the_flight_to_the_crewmates_logbook(self):
        self.assertEqual(self.invite().status_code, 201)
        self.authenticate('maria')
        invites = self.client.get('/api/crew/invites/').data
        self.assertEqual((invites[0]['invited_by'], invites[0]['role'], invites[0]['flight']['id']), ('pilot', 'SIC', self.flight['id']))
        self.assertNotIn('notes', invites[0]['flight'])

        res = self.client.post(f"/api/crew/{invites[0]['id']}/accept/")
        self.assertEqual(res.status_code, 201, res.data)
        copy = res.data
        self.assertEqual((copy['departure_airport'], copy['registration_number'], copy['total_time']), ('KJFK', 'N12345', '05:30:00'))
        self.assertEqual((copy['sic_time'], copy['pic_time'], copy['notes'], copy['day_landings']), ('05:30:00', '00:00:00', '', 0))
        self.assertEqual(self.client.get('/api/flights/').data['count'], 1)
        self.assertEqual(self.client.get('/api/crew/invites/').data, [])
        self.assertEqual(self.crew(copy['id']), {('pilot', 'PIC', 'LOGGER'), ('maria', 'SIC', 'ACCEPTED')})

        self.authenticate()
        self.assertEqual(self.crew(self.flight['id']), {('pilot', 'PIC', 'LOGGER'), ('maria', 'SIC', 'ACCEPTED')})

    def test_rejected_invites(self):
        self.assertEqual(self.invite('nobody').status_code, 400)
        self.assertEqual(self.invite('pilot').status_code, 400)
        self.assertEqual(self.invite().status_code, 201)
        self.assertEqual(self.invite().status_code, 400)
        draft = self.add_flight(is_draft=True, departure_time='2027-06-01T10:00:00Z', arrival_time='2027-06-01T15:30:00Z')
        self.assertEqual(self.invite(flight=draft).status_code, 400)

        self.authenticate('maria')
        self.assertEqual(self.invite('sam').status_code, 404)

    def test_only_the_logger_invites_and_sees_pending(self):
        self.invite()
        copy = self.accept_as('maria').data
        self.assertEqual(self.invite('sam', flight=copy).status_code, 400)

        self.authenticate()
        self.invite('sam', role='PIC')
        self.assertIn(('sam', 'PIC', 'PENDING'), self.crew(self.flight['id']))
        self.authenticate('maria')
        self.assertEqual(self.crew(copy['id']), {('pilot', 'PIC', 'LOGGER'), ('maria', 'SIC', 'ACCEPTED')})

    def test_decline_cancel_and_reinvite(self):
        self.invite()
        self.authenticate('maria')
        invite_id = self.client.get('/api/crew/invites/').data[0]['id']
        self.assertEqual(self.client.delete(f'/api/crew/{invite_id}/').status_code, 204)
        self.assertEqual(self.client.get('/api/flights/').data['count'], 0)

        self.authenticate()
        self.assertIn(('maria', 'SIC', 'DECLINED'), self.crew(self.flight['id']))
        self.assertEqual(self.invite().status_code, 201)
        pending = next(m for m in self.client.get(f"/api/flights/{self.flight['id']}/crew/").data if m['status'] == 'PENDING')
        self.assertEqual(self.client.delete(f"/api/crew/{pending['id']}/").status_code, 204)
        self.authenticate('maria')
        self.assertEqual(self.client.get('/api/crew/invites/').data, [])

    def test_decline_or_cancel_after_accept_leaves_the_seat(self):
        self.invite()
        stale = CrewSeat.objects.get(status=CrewSeat.PENDING)
        copy = self.accept_as('maria').data
        for user in ('maria', 'pilot'):
            self.authenticate(user)
            with mock.patch('flights.views.get_object_or_404', return_value=stale):
                self.assertEqual(self.client.delete(f'/api/crew/{stale.pk}/').status_code, 404)
        self.assertEqual(self.crew(self.flight['id']), {('pilot', 'PIC', 'LOGGER'), ('maria', 'SIC', 'ACCEPTED')})
        self.assertEqual(CrewSeat.objects.get(pk=stale.pk).flight_id, copy['id'])

    def test_my_role_is_a_label(self):
        res = self.client.patch(f"/api/flights/{self.flight['id']}/crew/", {'role': 'SIC'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(self.crew(self.flight['id']), {('pilot', 'SIC', 'LOGGER')})
        self.assertEqual(self.client.get(f"/api/flights/{self.flight['id']}/").data['pic_time'], '05:30:00')

    def test_deleting_the_original_keeps_copies_and_drops_pending(self):
        self.invite()
        self.invite('sam')
        copy = self.accept_as('maria').data
        self.authenticate()
        self.client.delete(f"/api/flights/{self.flight['id']}/")

        self.authenticate('maria')
        self.assertEqual(self.client.get(f"/api/flights/{copy['id']}/").status_code, 200)
        self.assertEqual(self.crew(copy['id']), {('maria', 'SIC', 'ACCEPTED')})
        self.authenticate('sam')
        self.assertEqual(self.client.get('/api/crew/invites/').data, [])

    def test_avatar_hidden_until_accepted(self):
        get_user_model().objects.filter(username='maria').update(avatar='avatars/maria.png')
        self.invite()
        self.assertIsNone(self.client.get(f"/api/flights/{self.flight['id']}/crew/").data[1]['avatar'])
        self.accept_as('maria')
        self.authenticate()
        self.assertIn('avatars/maria.png', self.client.get(f"/api/flights/{self.flight['id']}/crew/").data[1]['avatar'])

    def test_cannot_accept_once_the_original_is_a_draft_again(self):
        self.invite()
        Flight.objects.filter(pk=self.flight['id']).update(is_draft=True)
        self.assertEqual(self.accept_as('maria').status_code, 400)
        self.assertFalse(Flight.objects.filter(user__username='maria').exists())

    def test_deleting_a_copy_leaves_the_crew(self):
        self.invite()
        copy = self.accept_as('maria').data
        self.client.delete(f"/api/flights/{copy['id']}/")
        self.authenticate()
        self.assertEqual(self.crew(self.flight['id']), {('pilot', 'PIC', 'LOGGER')})

    def test_accepting_runs_the_crewmates_checks_once(self):
        self.invite()
        self.authenticate('maria')
        Aircraft.objects.create(user=get_user_model().objects.get(username='maria'), registration='N12345', grounded=True)
        invite_id = self.client.get('/api/crew/invites/').data[0]['id']
        res = self.client.post(f'/api/crew/{invite_id}/accept/')
        self.assertEqual(res.status_code, 400)
        self.assertIn('grounded', str(res.data))

        Aircraft.objects.filter(registration='N12345', user__username='maria').update(grounded=False)
        self.assertEqual(self.client.post(f'/api/crew/{invite_id}/accept/').status_code, 201)
        self.assertEqual(self.client.post(f'/api/crew/{invite_id}/accept/').status_code, 404)
        self.assertEqual(Flight.objects.filter(user__username='maria').count(), 1)
        self.assertEqual(Flight.objects.get(user__username='maria').aircraft.registration, 'N12345')


class AvatarTests(ApiTestCase):
    image = PhotoUploadTests.image

    def test_upload_replace_and_remove(self):
        self.authenticate()
        res = self.client.patch('/api/me/', {'avatar': self.image('me.png')}, format='multipart')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIn('avatars/me', res.data['avatar'])
        first = get_user_model().objects.get(username='pilot').avatar
        self.client.patch('/api/me/', {'avatar': self.image('me2.png')}, format='multipart')
        self.assertFalse(first.storage.exists(first.name))

        second = get_user_model().objects.get(username='pilot').avatar
        res = self.client.patch('/api/me/', {'avatar': None}, format='json')
        self.assertIsNone(res.data['avatar'])
        self.assertFalse(second.storage.exists(second.name))

    def test_rejects_non_images(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.authenticate()
        res = self.client.patch('/api/me/', {'avatar': SimpleUploadedFile('x.png', b'not an image')}, format='multipart')
        self.assertEqual(res.status_code, 400)

    def test_public_page_and_account_deletion(self):
        self.authenticate()
        self.client.patch('/api/me/', {'avatar': self.image(), 'is_public': True}, format='multipart')
        avatar = get_user_model().objects.get(username='pilot').avatar
        self.assertIn('avatars/', self.client.get('/api/pilots/pilot/').data['avatar'])
        self.client.delete('/api/me/', {'confirm': 'pilot', 'password': PASSWORD}, format='json')
        self.assertFalse(avatar.storage.exists(avatar.name))


class LiveFlightTests(ApiTestCase):
    START = {'departure_airport': 'KPAO', 'arrival_airport': 'KSQL', 'registration_number': 'N123AB', 'ete_minutes': 45}

    def setUp(self):
        super().setUp()
        self.register('maria')
        self.register('sam')
        self.authenticate()

    def start(self, **overrides):
        return self.client.post('/api/live/', {**self.START, 'crew': [{'username': 'maria', 'role': 'SIC'}], **overrides}, format='json')

    def shift(self, flight_id, **delta):
        flight = Flight.objects.get(pk=flight_id)
        Flight.objects.filter(pk=flight_id).update(
            departure_time=flight.departure_time - timedelta(**delta), arrival_time=flight.arrival_time - timedelta(**delta),
        )

    def live_as(self, username):
        self.authenticate(username)
        return self.client.get('/api/live/').data

    def test_crew_see_a_started_flight_and_strangers_dont(self):
        res = self.start(role='SIC', crew=[{'username': 'maria', 'role': 'PIC'}, {'username': 'sam', 'role': 'PIC'}])
        self.assertEqual(res.status_code, 201, res.data)
        flight = Flight.objects.get(pk=res.data['id'])
        self.assertTrue(flight.is_draft and flight.in_flight)
        self.assertEqual(flight.arrival_time - flight.departure_time, timedelta(minutes=45))
        self.assertEqual(self.client.get('/api/stats/').data['totals']['flights'], 0)
        self.assertEqual(
            {(m['username'], m['role']) for m in self.client.get(f"/api/flights/{flight.pk}/crew/").data},
            {('pilot', 'SIC'), ('maria', 'PIC'), ('sam', 'PIC')},
        )

        [seen] = self.live_as('maria')
        self.assertEqual(
            (seen['pilot'], seen['departure_airport'], seen['arrival_airport'], seen['is_mine'], seen['unconfirmed']),
            ('pilot', 'KPAO', 'KSQL', False, False),
        )
        [invite] = self.client.get('/api/crew/invites/').data
        self.assertEqual(self.client.post(f"/api/crew/{invite['id']}/accept/").status_code, 400)

        self.authenticate('sam')
        [invite] = self.client.get('/api/crew/invites/').data
        self.assertEqual(self.client.delete(f"/api/crew/{invite['id']}/").status_code, 204)
        self.assertEqual(self.client.get('/api/live/').data, [])
        self.assertEqual(self.live_as('dana'), [])

    def test_landing_early_on_a_long_route(self):
        flight_id = self.start(arrival_airport='KJFK', ete_minutes=330).data['id']
        self.shift(flight_id, minutes=10)
        res = self.client.post(f'/api/live/{flight_id}/land/')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertFalse(res.data['in_flight'])
        next_id = self.start().data['id']
        future = (timezone.now() + timedelta(hours=3)).isoformat()
        res = self.client.post(f'/api/live/{next_id}/land/', {'arrival_time': future}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_one_live_flight_at_a_time_and_not_in_a_grounded_aircraft(self):
        self.assertEqual(self.start().status_code, 201)
        self.assertEqual(self.start(registration_number='N999ZZ').status_code, 400)

        self.authenticate('sam')
        Aircraft.objects.create(user=get_user_model().objects.get(username='sam'), registration='N123AB', grounded=True)
        res = self.client.post('/api/live/', self.START, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('grounded', str(res.data))

    def test_check_in_after_the_eta_and_still_flying(self):
        flight_id = self.start().data['id']
        self.shift(flight_id, minutes=80)
        self.assertTrue(self.client.get('/api/live/').data[0]['unconfirmed'])
        self.assertTrue(self.live_as('maria')[0]['unconfirmed'])

        self.authenticate()
        res = self.client.post(f'/api/live/{flight_id}/still-flying/')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertFalse(res.data['unconfirmed'])
        flight = Flight.objects.get(pk=flight_id)
        self.assertEqual(flight.total_time, flight.arrival_time - flight.departure_time)
        self.assertLess(abs((flight.arrival_time - flight.updated_at).total_seconds()), 5)

    def test_unanswered_check_in_lands_at_the_last_deadline(self):
        flight_id = self.start().data['id']
        self.shift(flight_id, hours=3)
        eta = Flight.objects.get(pk=flight_id).arrival_time

        self.assertEqual(self.client.get('/api/live/').data, [])
        flight = Flight.objects.get(pk=flight_id)
        self.assertEqual((flight.in_flight, flight.is_draft, flight.arrival_time), (False, True, eta))
        self.assertEqual(self.client.post(f'/api/live/{flight_id}/land/').status_code, 404)
        self.assertEqual(self.start().status_code, 201)

    def test_land_log_and_crew_accept(self):
        flight_id = self.start().data['id']
        self.assertEqual(self.client.patch(f'/api/flights/{flight_id}/', {'is_draft': False}, format='json').status_code, 400)
        self.assertEqual(self.live_as('sam'), [])
        self.assertEqual(self.client.post(f'/api/live/{flight_id}/land/').status_code, 404)

        self.authenticate()
        self.shift(flight_id, minutes=50)
        landed_at = Flight.objects.get(pk=flight_id).departure_time + timedelta(minutes=40)
        res = self.client.post(f'/api/live/{flight_id}/land/', {'arrival_time': landed_at.isoformat()}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data['in_flight'], res.data['is_draft'], res.data['total_time']), (False, True, '00:40:00'))
        self.assertEqual(self.client.get('/api/live/').data, [])

        res = self.client.patch(f'/api/flights/{flight_id}/', {'is_draft': False, 'pic_time': '00:40:00'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.authenticate('maria')
        [invite] = self.client.get('/api/crew/invites/').data
        self.assertEqual(self.client.post(f"/api/crew/{invite['id']}/accept/").status_code, 201)

    def test_discarding_ends_it_for_the_crew(self):
        flight_id = self.start().data['id']
        self.assertEqual(self.client.delete(f'/api/flights/{flight_id}/').status_code, 204)
        self.assertEqual(self.live_as('maria'), [])


class FollowTests(ApiTestCase):
    START = LiveFlightTests.START

    def setUp(self):
        super().setUp()
        self.authenticate('amy')
        self.client.patch('/api/me/', {'is_public': True}, format='json')
        self.register('sam')
        self.authenticate()

    def as_(self, username):
        self.authenticate(username)
        return self

    def follow(self, username):
        return self.client.post(f'/api/pilots/{username}/follow/')

    def live(self):
        return [(f['pilot'], f['is_mine'], f['unconfirmed']) for f in self.client.get('/api/live/').data]

    def feed(self):
        return [(f['pilot'], f['departure_airport'], f['notes']) for f in self.client.get('/api/feed/').data['results']]

    def test_following_a_public_pilot_shows_their_live_and_logged_flights(self):
        self.as_('amy')
        self.add_flight(notes='Smooth')
        self.add_flight(departure_airport='KBOS', is_draft=True)
        self.assertEqual(self.client.post('/api/live/', self.START, format='json').status_code, 201)

        self.as_('pilot')
        self.assertEqual((self.live(), self.feed()), ([], []))
        res = self.follow('amy')
        self.assertEqual((res.status_code, res.data['status']), (200, 'APPROVED'))
        self.assertEqual(self.follow('amy').data['status'], 'APPROVED')
        self.assertEqual(self.live(), [('amy', False, False)])
        self.assertEqual(self.feed(), [('amy', 'KJFK', None)])

        self.client.credentials()
        self.assertEqual(self.client.get('/api/pilots/amy/').data['followers'], 1)
        [amy] = self.client.get('/api/rankings/').data['flights']
        self.assertEqual(amy['followers'], 1)

        self.as_('pilot')
        self.assertEqual(self.client.delete('/api/pilots/amy/follow/').status_code, 204)
        self.assertEqual((self.live(), self.feed()), ([], []))

    def test_a_private_pilot_approves_requests(self):
        self.as_('sam')
        self.add_flight()
        self.as_('pilot')
        self.assertEqual(self.follow('sam').data['status'], 'PENDING')
        self.assertEqual(self.feed(), [])
        self.assertEqual(self.client.get('/api/follows/').data['following'][0]['status'], 'PENDING')

        self.as_('sam')
        self.assertEqual([r['username'] for r in self.client.get('/api/follows/').data['requests']], ['pilot'])
        self.assertEqual(self.client.post('/api/pilots/amy/follower/').status_code, 404)
        self.assertEqual(self.client.post('/api/pilots/pilot/follower/').status_code, 204)
        self.assertEqual([r['username'] for r in self.client.get('/api/follows/').data['followers']], ['pilot'])

        self.as_('pilot')
        self.assertEqual(len(self.feed()), 1)

        self.as_('sam')
        self.assertEqual(self.client.delete('/api/pilots/pilot/follower/').status_code, 204)
        self.as_('pilot')
        self.assertEqual(self.feed(), [])
        self.assertEqual(self.follow('sam').data['status'], 'PENDING')

    def test_going_public_approves_waiting_requests_and_going_private_keeps_followers(self):
        self.follow('sam')
        self.as_('sam')
        self.client.patch('/api/me/', {'is_public': True}, format='json')
        self.client.patch('/api/me/', {'is_public': False}, format='json')
        self.assertEqual([r['username'] for r in self.client.get('/api/follows/').data['followers']], ['pilot'])

    def test_hidden_flights_and_notes(self):
        self.follow('amy')
        self.as_('amy')
        self.add_flight(notes='Shared', hide_notes=False)
        self.add_flight(departure_airport='KBOS', hidden_from_followers=True)
        res = self.client.post('/api/live/', {**self.START, 'hidden_from_followers': True, 'crew': [{'username': 'pilot', 'role': 'SIC'}]}, format='json')
        self.assertEqual(res.status_code, 201, res.data)

        self.as_('pilot')
        self.assertEqual(self.feed(), [('amy', 'KJFK', 'Shared')])
        self.assertEqual(self.live(), [('amy', False, False)])
        self.as_('sam')
        self.client.patch('/api/me/', {'is_public': True}, format='json')
        self.follow('amy')
        self.assertEqual(self.live(), [])

    def test_crew_who_also_follow_see_a_live_flight_once(self):
        self.follow('amy')
        self.as_('amy')
        self.client.post('/api/live/', {**self.START, 'crew': [{'username': 'pilot', 'role': 'SIC'}]}, format='json')
        self.as_('pilot')
        self.assertEqual(self.live(), [('amy', False, False)])

    def test_blocking(self):
        self.as_('amy')
        self.add_flight()
        self.as_('pilot')
        self.follow('amy')
        self.as_('amy')
        self.follow('pilot')
        self.assertEqual(self.client.post('/api/pilots/pilot/block/').status_code, 204)
        self.assertEqual(self.client.post('/api/pilots/pilot/block/').status_code, 204)
        follows = self.client.get('/api/follows/').data
        self.assertEqual((follows['following'], follows['followers'], [b['username'] for b in follows['blocked']]), ([], [], ['pilot']))

        self.as_('pilot')
        self.assertEqual(self.feed(), [])
        nobody = "No AirFleet pilot is called {}."
        for name in ('amy', 'pilot', 'nobody'):
            res = self.follow(name)
            self.assertEqual((res.status_code, res.data['username']), (400, [nobody.format(name)]))
        self.assertEqual(self.client.post('/api/pilots/amy/block/').status_code, 204)
        self.assertEqual(self.client.delete('/api/pilots/amy/block/').status_code, 204)

        Follow.objects.create(follower=get_user_model().objects.get(username='pilot'), pilot=get_user_model().objects.get(username='amy'), status=Follow.APPROVED)
        self.assertEqual(self.feed(), [])

        self.as_('amy')
        self.assertEqual(self.client.delete('/api/pilots/pilot/block/').status_code, 204)
        self.as_('pilot')
        self.assertEqual(len(self.feed()), 1)

    def test_deleting_an_account_removes_its_follows(self):
        self.follow('amy')
        self.as_('amy')
        self.client.post('/api/pilots/pilot/block/')
        self.client.delete('/api/me/', {'confirm': 'amy', 'password': PASSWORD}, format='json')
        self.assertEqual((Follow.objects.count(), Block.objects.count()), (0, 0))


class SocialTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.authenticate('amy')
        self.client.patch('/api/me/', {'is_public': True}, format='json')
        self.flight = self.add_flight()['id']
        self.register('sam')
        self.authenticate()
        self.client.post('/api/pilots/amy/follow/')

    def as_(self, username):
        self.authenticate(username)
        return self

    def comment(self, body='Nice landing', parent=None, flight=None):
        return self.client.post(f'/api/flights/{flight or self.flight}/comments/', {'body': body, 'parent': parent}, format='json')

    def thread(self, flight=None):
        res = self.client.get(f'/api/flights/{flight or self.flight}/comments/')
        if res.status_code != 200:
            return res.status_code
        return [(c['author'], c['body'], [(r['author'], r['body']) for r in c['replies']]) for c in res.data]

    def notifications(self):
        return [(n['kind'], n['actor']) for n in self.client.get('/api/notifications/').data]

    def unread(self):
        return self.client.get('/api/notifications/unread/').data['count']

    def test_followers_and_the_owner_comment_with_one_level_of_replies(self):
        top = self.comment().data['id']
        self.as_('amy')
        reply = self.comment('Thanks', parent=top).data['id']
        self.as_('pilot')
        res = self.comment('Any time', parent=reply)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(self.thread(), [('pilot', 'Nice landing', [('amy', 'Thanks'), ('pilot', 'Any time')])])
        self.assertEqual(self.comment('x' * 501).status_code, 400)
        self.assertEqual(self.comment('   ').status_code, 400)
        self.assertEqual(self.comment(['x']).status_code, 400)
        self.assertEqual(self.comment(parent='abc').status_code, 400)

        draft = Flight.objects.create(**{**Flight.objects.filter(pk=self.flight).values()[0], 'id': None, 'is_draft': True})
        self.assertEqual((self.thread(draft.pk), self.comment(flight=draft.pk).status_code), (404, 404))
        self.as_('sam')
        self.assertEqual((self.thread(), self.comment().status_code), (404, 404))

    def test_editing_and_deleting(self):
        top = self.comment().data['id']
        alone = self.comment('Second').data['id']
        res = self.client.patch(f'/api/comments/{top}/', {'body': 'Very nice landing'}, format='json')
        self.assertEqual((res.status_code, res.data['edited']), (200, True))
        self.as_('amy')
        reply = self.comment('Thanks', parent=top).data['id']
        self.client.post(f'/api/comments/{top}/like/')
        self.assertEqual(self.client.patch(f'/api/comments/{top}/', {'body': 'Hacked'}, format='json').status_code, 404)
        self.assertEqual(self.client.delete(f'/api/comments/{top}/').status_code, 204)
        self.assertEqual(self.client.delete(f'/api/comments/{alone}/').status_code, 204)
        self.assertEqual(self.thread(), [(None, '', [('amy', 'Thanks')])])
        self.assertEqual(Like.objects.count(), 0)
        self.assertEqual(self.client.delete(f'/api/comments/{reply}/').status_code, 204)
        self.assertEqual(self.thread(), [])

        mine = self.comment().data['id']
        self.as_('sam')
        self.assertEqual(self.client.delete(f'/api/comments/{mine}/').status_code, 404)

    def test_losing_access_keeps_what_you_wrote(self):
        top = self.comment().data['id']
        self.client.delete('/api/pilots/amy/follow/')
        self.assertEqual(self.thread(), 404)
        self.assertEqual(self.client.patch(f'/api/comments/{top}/', {'body': 'Edit'}, format='json').status_code, 404)
        self.assertEqual(self.client.delete(f'/api/comments/{top}/').status_code, 404)
        self.as_('amy')
        self.assertEqual(self.thread(), [('pilot', 'Nice landing', [])])
        self.client.patch(f'/api/flights/{self.flight}/', {'hidden_from_followers': True}, format='json')
        self.as_('pilot')
        self.client.post('/api/pilots/amy/follow/')
        self.assertEqual((self.thread(), self.client.post(f'/api/flights/{self.flight}/like/').status_code), (404, 404))
        self.as_('amy')
        self.assertEqual(self.client.delete(f'/api/comments/{top}/').status_code, 204)

    def test_likes_toggle_and_show_in_the_feed(self):
        self.comment()
        self.as_('amy')
        self.comment('Own comment')
        self.as_('pilot')
        for _ in range(2):
            self.assertEqual(self.client.post(f'/api/flights/{self.flight}/like/').data, {'liked': True, 'like_count': 1})
        [entry] = self.client.get('/api/feed/').data['results']
        self.assertEqual((entry['like_count'], entry['liked'], entry['comment_count']), (1, True, 2))
        self.assertEqual(self.client.get(f'/api/feed/{self.flight}/').data['id'], self.flight)
        self.assertEqual(self.client.delete(f'/api/flights/{self.flight}/like/').data, {'liked': False, 'like_count': 0})

        comment = self.client.get(f'/api/flights/{self.flight}/comments/').data[1]
        res = self.client.post(f'/api/comments/{comment["id"]}/like/')
        self.assertEqual(res.data, {'liked': True, 'like_count': 1})
        self.assertEqual(self.client.get(f'/api/flights/{self.flight}/comments/').data[1]['liked'], True)
        self.as_('sam')
        self.assertEqual(self.client.get(f'/api/feed/{self.flight}/').status_code, 404)

    def test_notifications(self):
        self.as_('sam')
        self.client.post('/api/pilots/pilot/follow/')
        self.as_('pilot')
        self.assertEqual(self.notifications(), [('follow_request', 'sam')])
        self.as_('sam')
        self.client.delete('/api/pilots/pilot/follow/')
        self.client.post('/api/pilots/pilot/follow/')
        self.as_('pilot')
        self.assertEqual(self.unread(), 1)
        self.client.post('/api/pilots/sam/follower/')
        self.assertEqual((self.notifications(), self.unread()), ([('follow', 'sam')], 0))

        self.as_('sam')
        self.assertEqual(self.notifications(), [('approved', 'pilot')])
        self.as_('amy')
        self.assertEqual(self.notifications(), [('follow', 'pilot')])

        self.as_('pilot')
        top = self.comment().data['id']
        self.client.post(f'/api/flights/{self.flight}/like/')
        self.comment('Own reply', parent=top)
        self.as_('amy')
        self.assertEqual(self.notifications()[:3], [('comment', 'pilot'), ('flight_like', 'pilot'), ('comment', 'pilot')])
        self.client.post(f'/api/comments/{top}/like/')
        self.comment('Thanks', parent=top)
        self.client.post(f'/api/flights/{self.flight}/like/')
        self.client.post('/api/pilots/pilot/follow/')
        self.as_('pilot')
        self.assertEqual(self.unread(), 3)
        self.assertEqual(self.notifications()[:3], [('follow_request', 'amy'), ('reply', 'amy'), ('comment_like', 'amy')])
        self.assertEqual(self.unread(), 0)

        self.client.delete(f'/api/flights/{self.flight}/like/')
        self.as_('amy')
        self.assertNotIn(('flight_like', 'pilot'), self.notifications())
        self.client.post('/api/pilots/pilot/block/')
        self.assertEqual(self.notifications(), [])

        Notification.objects.update(created_at=timezone.now() - timedelta(days=91))
        self.as_('sam')
        self.assertEqual(self.notifications(), [])
        self.assertFalse(Notification.objects.filter(recipient__username='sam').exists())

    def test_unread_count_clears_however_many_there_are(self):
        for n in range(60):
            self.comment(f'Note {n}')
        self.as_('amy')
        self.assertEqual(self.unread(), 61)
        self.assertEqual(len(self.notifications()), 61)
        self.assertEqual(self.unread(), 0)

    def test_reply_notifies_the_parent_author_and_the_owner_once(self):
        self.as_('sam')
        self.client.patch('/api/me/', {'is_public': True}, format='json')
        self.client.post('/api/pilots/amy/follow/')
        self.as_('pilot')
        top = self.comment().data['id']
        self.as_('sam')
        self.comment('Agreed', parent=top)
        self.as_('pilot')
        self.assertEqual(self.notifications()[0], ('reply', 'sam'))
        self.as_('amy')
        self.assertEqual(self.notifications()[:2], [('comment', 'sam'), ('comment', 'pilot')])
        self.as_('pilot')
        self.client.delete(f'/api/comments/{top}/')
        self.assertEqual(self.notifications(), [])

    def test_notifications_inside_a_hidden_thread_are_hidden(self):
        top = self.comment().data['id']
        self.as_('sam')
        self.client.patch('/api/me/', {'is_public': True}, format='json')
        self.client.post('/api/pilots/amy/follow/')
        reply = self.comment('Agreed', parent=top).data['id']
        self.as_('amy')
        self.client.post(f'/api/comments/{reply}/like/')
        self.assertIn(('comment', 'sam'), self.notifications())
        self.client.post('/api/pilots/pilot/block/')
        self.assertEqual((self.notifications(), self.unread()), ([('follow', 'sam')], 0))
        self.as_('sam')
        self.assertIn(('comment_like', 'amy'), self.notifications())
        self.client.post('/api/pilots/pilot/block/')
        self.assertNotIn(('comment_like', 'amy'), self.notifications())
        self.assertEqual(self.unread(), 0)

    def test_blocked_pilots_comments_are_hidden(self):
        self.comment()
        self.as_('sam')
        self.client.patch('/api/me/', {'is_public': True}, format='json')
        self.client.post('/api/pilots/amy/follow/')
        self.comment('Sam here')
        self.client.post('/api/pilots/pilot/block/')
        self.assertEqual(self.thread(), [('sam', 'Sam here', [])])
        self.as_('pilot')
        self.assertEqual(self.thread(), [('pilot', 'Nice landing', [])])
        self.assertEqual(self.client.get('/api/feed/').data['results'][0]['comment_count'], 1)

    def test_deleting_an_account_runs_its_comments_through_the_delete_rule(self):
        top = self.comment().data['id']
        self.comment('Gone')
        self.client.post(f'/api/flights/{self.flight}/like/')
        self.as_('amy')
        self.comment('Thanks', parent=top)
        self.as_('pilot')
        self.assertEqual(self.client.delete('/api/me/', {'confirm': 'pilot', 'password': PASSWORD}, format='json').status_code, 204)
        self.client.credentials()
        self.as_('amy')
        self.assertEqual(self.thread(), [(None, '', [('amy', 'Thanks')])])
        self.assertEqual((Like.objects.count(), Notification.objects.count()), (0, 0))

        self.as_('sam')
        self.client.patch('/api/me/', {'is_public': True}, format='json')
        self.client.post('/api/pilots/amy/follow/')
        self.comment('From sam', parent=top)
        get_user_model().objects.filter(username='sam').delete()
        self.client.credentials()
        self.as_('amy')
        self.assertEqual(self.thread(), [(None, '', [('amy', 'Thanks')])])

    def test_comments_and_edits_are_throttled_but_reading_is_not(self):
        with mock.patch.dict(views.CommentThrottle.THROTTLE_RATES, {'comment': '2/hour'}):
            top = self.comment().data['id']
            self.client.patch(f'/api/comments/{top}/', {'body': 'Edited'}, format='json')
            self.assertEqual(self.comment().status_code, 429)
            self.assertEqual(len(self.thread()), 1)
