import io
from datetime import date, datetime, timedelta, timezone as dt_timezone
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase

from . import airports, external, flight_plans, insights
from .models import Aircraft, Flight

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
                departure_time=f'2026-01-{day:02d}T10:00:00Z', arrival_time=f'2026-01-{day:02d}T11:00:00Z',
                total_time='01:00:00', arrival_airport='KBOS' if day % 5 == 0 else 'KLAX',
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
        self.assertEqual(res.data['flights'][0], {'username': 'pilot', 'is_public': False, 'total_flights': 1})
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

    @override_settings(OPENAI_API_KEY='sk-test')
    def test_generate_narrative_is_saved(self):
        self.authenticate()
        flight = self.add_flight(weather_conditions='KJFK 011000Z 27010KT 10SM CLR')
        completion = mock.Mock()
        completion.choices = [mock.Mock(message=mock.Mock(content='  A smooth flight.  '))]
        with mock.patch('flights.views.OpenAI') as client_cls:
            create = client_cls.return_value.chat.completions.create
            create.return_value = completion
            res = self.client.post('/api/generate-narrative/', {'flight_id': flight['id']}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['narrative'], 'A smooth flight.')
        self.assertEqual(Flight.objects.get().narrative, 'A smooth flight.')
        prompt = create.call_args.kwargs['messages'][1]['content']
        self.assertIn('27010KT', prompt)
        self.assertIn('John F. Kennedy', prompt)

    @override_settings(OPENAI_API_KEY='sk-test')
    def test_generate_narrative_for_someone_elses_flight(self):
        self.authenticate('alice')
        flight = self.add_flight()
        self.authenticate('bob')
        res = self.client.post('/api/generate-narrative/', {'flight_id': flight['id']}, format='json')
        self.assertEqual(res.status_code, 404)

    @override_settings(OPENAI_API_KEY='')
    def test_generate_narrative_without_key(self):
        self.authenticate()
        flight = self.add_flight()
        res = self.client.post('/api/generate-narrative/', {'flight_id': flight['id']}, format='json')
        self.assertEqual(res.status_code, 503)

    @override_settings(OPENAI_API_KEY='sk-test')
    def test_generate_narrative_is_throttled(self):
        from rest_framework.settings import api_settings
        self.authenticate()
        flight = self.add_flight()
        rates = {**api_settings.DEFAULT_THROTTLE_RATES, 'narrative': '2/hour'}
        completion = mock.Mock(choices=[mock.Mock(message=mock.Mock(content='Story'))])
        with mock.patch('flights.views.NarrativeThrottle.THROTTLE_RATES', rates), mock.patch('flights.views.OpenAI') as client_cls:
            client_cls.return_value.chat.completions.create.return_value = completion
            codes = [self.client.post('/api/generate-narrative/', {'flight_id': flight['id']}, format='json').status_code for _ in range(3)]
        self.assertEqual(codes[2], 429)

    def test_errors_do_not_leak_exceptions(self):
        self.authenticate()
        res = self.client.post('/api/generate-narrative/', {}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data, {'error': 'flight_id is required'})


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
        self.add_flight(departure_time='2030-01-02T10:00:00Z', arrival_time='2030-01-02T15:30:00Z')

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
        return self.client.post('/api/flights/import/', {'file': SimpleUploadedFile(name, text.encode(), content_type='text/csv')}, format='multipart')

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
        )
        res = self.upload(text)
        self.assertEqual(res.data['source'], 'foreflight')
        self.assertEqual((res.data['created'], res.data['skipped']), (1, 1), res.data)
        flight = Flight.objects.get()
        self.assertEqual(flight.departure_time, datetime(2026, 1, 5, 14, 10, tzinfo=dt_timezone.utc))
        self.assertEqual((flight.total_time, flight.night_time, flight.approaches), (timedelta(hours=1.5), timedelta(hours=0.5), 1))
        self.assertEqual((flight.day_landings, flight.night_landings, flight.cross_country), (1, 1, True))
        self.assertEqual(flight.notes, 'Gusty')
        self.assertEqual((flight.aircraft.type_code, flight.aircraft.make_model), ('C172', 'Cessna 172S'))


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

# Synthetic: an ICAO flight plan as filed for a Delta flight, with no times table.
DELTA_FPL = """
 DELTA AIR LINES  DL1234  KATL-KLAX
 (FPL-DAL1234-IS
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

    def test_delta_without_times_table(self):
        result = flight_plans.parse(DELTA_FPL)
        flight = result['flight']
        self.assertEqual((result['source'], result['callsign']), ('delta', 'DAL1234'))
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
        res = self.upload(make_pdf(DELTA_FPL))
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['flight']['arrival_airport'], 'KLAX')
        self.assertFalse(Flight.objects.exists())

        self.assertEqual(self.upload(b'name,date\n', 'plan.csv').status_code, 400)
        self.assertEqual(self.upload(make_pdf('Nothing here')).status_code, 422)
        self.client.credentials()
        self.assertEqual(self.upload(make_pdf(DELTA_FPL)).status_code, 401)

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
