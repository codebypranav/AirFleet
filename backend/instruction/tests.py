import csv
import io
from datetime import date

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from flights.models import Flight
from flights.tests import FLIGHT, PASSWORD, ApiTestCase
from .endorsements import add_calendar_months
from .models import InstructorLink, Signature

LESSON = {**FLIGHT, 'dual_received_time': '01:30:00', 'notes': 'Steep turns'}
# An hour on the student's own, on a short route so that hour is a believable speed.
SOLO = {'arrival_airport': 'KBOS', 'distance': 0, 'departure_time': '2026-01-02T10:00:00Z',
        'arrival_time': '2026-01-02T11:00:00Z', 'total_time': '01:00:00'}


class InstructionTestCase(ApiTestCase):
    def login(self, username):
        """Switch the client to `username`, registering them the first time."""
        self.client.credentials()
        self.register(username)
        res = self.client.post('/api/login/', {'username': username, 'password': PASSWORD}, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def make_instructor(self, username='cfi', **profile):
        self.login(username)
        self.client.patch('/api/me/', {
            'first_name': 'Carol', 'last_name': 'Fly', 'instructor_certificate_number': ' 1234567cfi ', **profile,
        }, format='json')

    def link(self):
        """student invites cfi, cfi accepts. Leaves the client signed in as cfi."""
        self.make_instructor()
        self.login('student')
        res = self.client.post('/api/instruction/links/', {'invitee': 'cfi', 'invitee_role': 'instructor'}, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.login('cfi')
        self.assertEqual(self.client.post(f"/api/instruction/links/{res.data['id']}/accept/").status_code, 200)
        return res.data['id']

    def sign(self, flight_id, **data):
        return self.client.post(
            f'/api/instruction/flights/{flight_id}/sign/', {'agree': True, 'password': PASSWORD, **data}, format='json',
        )


class LinkTests(InstructionTestCase):
    def test_invite_accept_and_list(self):
        self.make_instructor()
        self.login('student')
        res = self.client.post('/api/instruction/links/', {'invitee': 'CFI@example.com', 'invitee_role': 'instructor'}, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual((res.data['role'], res.data['status'], res.data['awaiting_my_response']), ('student', 'PENDING', False))
        self.assertEqual(res.data['other']['certificate_number'], '1234567CFI')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('as their instructor', mail.outbox[0].body)

        # The inviter can't accept their own invitation.
        self.assertEqual(self.client.post(f"/api/instruction/links/{res.data['id']}/accept/").status_code, 400)
        self.login('cfi')
        [mine] = self.client.get('/api/instruction/links/').data
        self.assertEqual((mine['role'], mine['awaiting_my_response'], mine['other']['username']), ('instructor', True, 'student'))
        accepted = self.client.post(f"/api/instruction/links/{mine['id']}/accept/").data
        self.assertEqual(accepted['status'], 'ACTIVE')

    def test_instructor_can_invite_a_student(self):
        self.make_instructor()
        self.register('student')
        res = self.client.post('/api/instruction/links/', {'invitee': 'student', 'invitee_role': 'student'}, format='json')
        self.assertEqual((res.status_code, res.data['role']), (201, 'instructor'))

    def test_invite_rules(self):
        self.login('student')
        invite = lambda who, role='instructor': self.client.post(
            '/api/instruction/links/', {'invitee': who, 'invitee_role': role}, format='json',
        )
        self.assertEqual(invite('nobody').status_code, 400)
        self.assertEqual(invite('student').status_code, 400)
        self.register('friend')
        # Instructing is a capability: only pilots with a certificate on file can be invited as one.
        self.assertIn('certificate', str(invite('friend').data))
        self.assertIn('your instructor certificate', str(invite('friend', 'student').data))
        self.make_instructor()
        self.login('student')
        self.assertEqual(invite('cfi').status_code, 201)
        self.assertEqual(invite('cfi').status_code, 400)  # already invited

    def test_either_side_can_end_a_link(self):
        link = self.link()
        self.login('student')
        self.assertEqual(self.client.delete(f'/api/instruction/links/{link}/').status_code, 204)
        self.assertEqual(self.client.get('/api/instruction/links/').data, [])
        self.assertEqual(InstructorLink.objects.get(pk=link).status, 'ENDED')
        # Ended, so the pair can be linked again.
        res = self.client.post('/api/instruction/links/', {'invitee': 'cfi', 'invitee_role': 'instructor'}, format='json')
        self.assertEqual(res.status_code, 201)

    def test_outsiders_cannot_touch_a_link(self):
        link = self.link()
        self.login('mallory')
        self.assertEqual(self.client.delete(f'/api/instruction/links/{link}/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/instruction/links/{link}/flights/').status_code, 404)


class SignatureTests(InstructionTestCase):
    def setUp(self):
        super().setUp()
        self.link_id = self.link()
        self.login('student')
        self.lesson = self.add_flight(**LESSON)
        self.solo = self.add_flight(**SOLO)
        self.login('cfi')

    def test_instructor_sees_only_dual_flights_and_signed_fields(self):
        res = self.client.get(f'/api/instruction/links/{self.link_id}/flights/')
        self.assertEqual(res.status_code, 200)
        [flight] = res.data['results']
        self.assertEqual(flight['id'], self.lesson['id'])
        self.assertEqual((flight['total_time'], flight['dual_received_time']), ('05:30:00', '01:30:00'))
        self.assertNotIn('notes', flight)
        self.assertIn('gave student 1:30 of flight instruction on 2026-01-01 in N12345, KJFK to KLAX', flight['statement'])
        [link] = self.client.get('/api/instruction/links/').data
        self.assertEqual(link['unsigned_flights'], 1)

    def test_sign_and_student_sees_it(self):
        res = self.sign(self.lesson['id'], remarks='Good lesson')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual((res.data['status'], res.data['certificate_number']), ('valid', '1234567CFI'))
        self.assertEqual(res.data['instructor_name'], 'Carol Fly')
        self.assertEqual(self.sign(self.lesson['id']).status_code, 409)
        self.assertEqual(self.client.get(f'/api/instruction/links/{self.link_id}/flights/?unsigned=true').data['count'], 0)

        self.login('student')
        signature = self.client.get(f"/api/flights/{self.lesson['id']}/").data['signature']
        self.assertEqual((signature['status'], signature['remarks'], signature['changed_fields']), ('valid', 'Good lesson', []))
        self.assertIsNone(self.client.get(f"/api/flights/{self.solo['id']}/").data['signature'])

    def test_editing_a_signed_field_invalidates_the_signature(self):
        self.sign(self.lesson['id'])
        self.login('student')
        url = f"/api/flights/{self.lesson['id']}/"
        # Notes aren't part of what's signed.
        self.assertEqual(self.client.patch(url, {'notes': 'Also stalls'}, format='json').data['signature']['status'], 'valid')
        res = self.client.patch(url, {'dual_received_time': '02:00:00', 'day_landings': 3}, format='json')
        self.assertEqual(res.data['signature']['status'], 'invalidated')
        self.assertEqual(res.data['signature']['changed_fields'], ['day_landings', 'dual_received_time'])
        self.assertEqual(self.client.get('/api/flights/').data['results'][-1]['signature']['status'], 'invalidated')

        # Putting the values back restores it; the snapshot is what was signed.
        res = self.client.patch(url, {'dual_received_time': '01:30:00', 'day_landings': 0}, format='json')
        self.assertEqual(res.data['signature']['status'], 'valid')

        # Once invalidated, the instructor can sign the new version.
        self.client.patch(url, {'arrival_time': '2026-01-01T16:00:00Z', 'total_time': '06:00:00'}, format='json')
        self.login('cfi')
        self.assertEqual(self.sign(self.lesson['id']).status_code, 201)
        self.assertEqual(Signature.objects.filter(flight_id=self.lesson['id']).count(), 2)

    def test_signing_rules(self):
        self.assertEqual(self.sign(self.solo['id']).status_code, 400)  # no dual time
        self.assertEqual(self.sign(self.lesson['id'], agree=False).status_code, 400)
        self.assertEqual(self.sign(self.lesson['id'], password='wrong').status_code, 400)

        self.client.patch('/api/me/', {'instructor_certificate_expires': '2025-12-31'}, format='json')
        res = self.sign(self.lesson['id'])
        self.assertEqual(res.status_code, 400)
        self.assertIn('expired on 2025-12-31', res.data['error'])

        self.client.patch('/api/me/', {'instructor_certificate_expires': '2099-01-31'}, format='json')
        self.assertEqual(self.sign(self.lesson['id']).data['certificate_expires'], '2099-01-31')

    def test_only_a_linked_instructor_can_sign(self):
        self.make_instructor('other_cfi')
        self.assertEqual(self.sign(self.lesson['id']).status_code, 404)
        self.login('student')  # students can't sign their own flights
        self.assertEqual(self.sign(self.lesson['id']).status_code, 404)

        self.login('cfi')
        self.client.delete(f'/api/instruction/links/{self.link_id}/')
        self.assertEqual(self.sign(self.lesson['id']).status_code, 404)
        self.assertEqual(self.client.get(f'/api/instruction/links/{self.link_id}/flights/').status_code, 404)

    def test_signature_survives_the_instructor_deleting_their_account(self):
        self.sign(self.lesson['id'])
        self.client.delete('/api/me/', {'confirm': 'cfi', 'password': PASSWORD}, format='json')
        self.login('student')
        signature = self.client.get(f"/api/flights/{self.lesson['id']}/").data['signature']
        self.assertEqual((signature['instructor_name'], signature['status']), ('Carol Fly', 'valid'))

    def test_signature_cannot_be_moved_to_another_flight(self):
        self.sign(self.lesson['id'])
        signature = Signature.objects.get()
        other = Flight.objects.get(pk=self.solo['id'])
        self.assertFalse(signature.is_valid(other))
        self.assertTrue(signature.is_valid())

    def test_students_cannot_write_signatures_through_the_flight(self):
        self.login('student')
        res = self.client.patch(f"/api/flights/{self.lesson['id']}/", {'signature': {'status': 'valid'}}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.data['signature'])
        self.assertEqual(Signature.objects.count(), 0)

    def test_certificate_on_profile(self):
        profile = self.client.get('/api/me/').data
        self.assertEqual(profile['instructor_certificate_number'], '1234567CFI')
        self.assertIsNone(profile['instructor_certificate_expires'])


class WithdrawalTests(InstructionTestCase):
    def setUp(self):
        super().setUp()
        self.link_id = self.link()
        self.login('student')
        self.lesson = self.add_flight(**LESSON)
        self.login('cfi')
        self.signature = self.sign(self.lesson['id']).data

    def withdraw(self, signature_id=None, **data):
        return self.client.post(
            f"/api/instruction/signatures/{signature_id or self.signature['id']}/withdraw/",
            {'password': PASSWORD, **data}, format='json',
        )

    def test_instructor_withdraws_and_student_sees_why(self):
        self.assertTrue(self.signature['withdrawable'])
        self.assertEqual(self.withdraw(password='wrong').status_code, 400)
        res = self.withdraw(reason='Logged the wrong aircraft')
        self.assertEqual((res.status_code, res.data['status'], res.data['withdrawable']), (200, 'withdrawn', False))
        self.assertEqual(self.withdraw().status_code, 409)

        [link] = self.client.get('/api/instruction/links/').data
        self.assertEqual(link['unsigned_flights'], 1)

        self.login('student')
        signature = self.client.get(f"/api/flights/{self.lesson['id']}/").data['signature']
        self.assertEqual((signature['status'], signature['withdrawal_reason']), ('withdrawn', 'Logged the wrong aircraft'))
        self.assertFalse(signature['withdrawable'])
        self.assertIsNotNone(signature['withdrawn_at'])

        # Signing again after a withdrawal starts a fresh signature.
        self.login('cfi')
        res = self.sign(self.lesson['id'])
        self.assertEqual((res.status_code, res.data['status']), (201, 'valid'))

    def test_only_the_signer_can_withdraw(self):
        self.login('student')
        self.assertEqual(self.withdraw().status_code, 404)
        self.make_instructor('other_cfi')
        self.assertEqual(self.withdraw().status_code, 404)
        self.assertIsNone(Signature.objects.get().withdrawn_at)

    def test_withdrawing_after_unlinking(self):
        self.client.delete(f'/api/instruction/links/{self.link_id}/')
        self.assertEqual(self.withdraw().status_code, 200)


class EndorsementTests(InstructionTestCase):
    SOLO = {
        'kind': 'solo', 'aircraft': 'Cessna 172', 'given_on': '2026-03-01',
        'text': 'I certify that Sam has received the training required to fly solo in the Cessna 172.',
    }

    def setUp(self):
        super().setUp()
        self.link_id = self.link()

    def endorse(self, **data):
        return self.client.post(
            f'/api/instruction/links/{self.link_id}/endorsements/',
            {**self.SOLO, 'agree': True, 'password': PASSWORD, **data}, format='json',
        )

    def test_kinds(self):
        kinds = {k['kind']: k for k in self.client.get('/api/instruction/endorsements/kinds/').json()}
        self.assertEqual(kinds['solo']['validity'], ['days', 90])
        self.assertIn('{student}', kinds['solo']['draft'])
        self.assertTrue(kinds['solo']['needs_aircraft'])
        self.assertEqual(kinds['other']['title'], '')

    def test_give_and_student_sees_it(self):
        res = self.endorse()
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual((res.data['title'], res.data['regulation']), ('Solo flight', '14 CFR 61.87(n)'))
        self.assertEqual((res.data['expires_on'], res.data['certificate_number']), ('2026-05-30', '1234567CFI'))
        self.assertTrue(res.data['withdrawable'])
        self.assertEqual(len(self.client.get(f'/api/instruction/links/{self.link_id}/endorsements/').data), 1)

        self.login('student')
        [mine] = self.client.get('/api/instruction/endorsements/').data
        self.assertEqual((mine['title'], mine['instructor_name'], mine['withdrawable']), ('Solo flight', 'Carol Fly', False))

    def test_status(self):
        expired = self.endorse(given_on='2025-01-10').data
        self.assertEqual((expired['expires_on'], expired['status']), ('2025-04-10', 'expired'))
        lasting = self.endorse(kind='tailwheel', aircraft='', given_on='2025-01-10').data
        self.assertEqual((lasting['expires_on'], lasting['status']), (None, 'current'))
        review = self.endorse(kind='flight_review', aircraft='', given_on='2025-01-10').data
        self.assertEqual(review['expires_on'], '2027-01-31')

    def test_validation(self):
        self.assertIn('aircraft', self.endorse(aircraft='').data)
        self.assertIn('text', self.endorse(text='I certify that {student} is ready.').data)
        self.assertIn('given_on', self.endorse(given_on='2099-01-01').data)
        self.assertIn('title', self.endorse(kind='other', aircraft='').data)
        self.assertEqual(self.endorse(kind='other', title='Night VFR', aircraft='').data['title'], 'Night VFR')
        self.assertIn('agree', self.endorse(agree=False).data)
        self.assertIn('password', self.endorse(password='nope').data)
        self.client.patch('/api/me/', {'instructor_certificate_expires': '2026-01-31'}, format='json')
        self.assertIn('expired on 2026-01-31', self.endorse().data['error'])

    def test_only_a_linked_instructor_endorses_and_withdraws(self):
        endorsement = self.endorse().data
        self.make_instructor('other_cfi')
        self.assertEqual(self.endorse().status_code, 404)
        withdraw_url = f"/api/instruction/endorsements/{endorsement['id']}/withdraw/"
        self.assertEqual(self.client.post(withdraw_url, {'password': PASSWORD}, format='json').status_code, 404)
        self.login('student')
        self.assertEqual(self.client.post(withdraw_url, {'password': PASSWORD}, format='json').status_code, 404)
        self.assertEqual(self.client.get(f'/api/instruction/links/{self.link_id}/endorsements/').status_code, 404)

        self.login('cfi')
        res = self.client.post(withdraw_url, {'password': PASSWORD, 'reason': 'Wrong student'}, format='json')
        self.assertEqual((res.data['status'], res.data['withdrawal_reason']), ('withdrawn', 'Wrong student'))
        self.login('student')
        self.assertEqual(self.client.get('/api/instruction/endorsements/').data[0]['status'], 'withdrawn')

    def test_endorsements_survive_the_instructor_deleting_their_account(self):
        self.endorse(kind='tailwheel', aircraft='')
        self.client.delete('/api/me/', {'confirm': 'cfi', 'password': PASSWORD}, format='json')
        self.login('student')
        [mine] = self.client.get('/api/instruction/endorsements/').data
        self.assertEqual((mine['instructor_name'], mine['status']), ('Carol Fly', 'current'))


class CalendarMonthTests(SimpleTestCase):
    def test_runs_to_the_end_of_the_month(self):
        self.assertEqual(add_calendar_months(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(add_calendar_months(date(2026, 11, 3), 2), date(2027, 1, 31))
        self.assertEqual(add_calendar_months(date(2026, 3, 15), 24), date(2028, 3, 31))


class DraftAndExportTests(InstructionTestCase):
    def test_drafts_are_not_shown_or_signable(self):
        link_id = self.link()
        self.login('student')
        draft = self.add_flight(**LESSON, is_draft=True)
        self.login('cfi')
        self.assertEqual(self.client.get(f'/api/instruction/links/{link_id}/flights/').data['count'], 0)
        self.assertEqual(self.sign(draft['id']).status_code, 404)

    def test_export_has_instructor_columns_and_still_imports(self):
        self.link()
        self.login('student')
        lesson = self.add_flight(**LESSON)
        self.add_flight(**SOLO)
        self.login('cfi')
        self.sign(lesson['id'])
        self.login('student')
        self.client.patch(f"/api/flights/{lesson['id']}/", {'day_landings': 2}, format='json')

        rows = list(csv.DictReader(io.StringIO(self.client.get('/api/flights/export/').content.decode())))
        signed, unsigned = sorted(rows, key=lambda r: r['departure_time'])
        self.assertEqual(
            (signed['instructor_name'], signed['instructor_certificate'], signed['signature_status']),
            ('Carol Fly', '1234567CFI', 'invalidated'),
        )
        self.assertTrue(signed['instructor_signed_at'])
        self.assertEqual((unsigned['instructor_name'], unsigned['signature_status']), ('', ''))

        csv_text = self.client.get('/api/flights/export/').content
        self.login('importer')
        upload = SimpleUploadedFile('logbook.csv', csv_text, content_type='text/csv')
        res = self.client.post('/api/flights/import/', {'file': upload}, format='multipart')
        self.assertEqual(res.data['created'], 2, res.data)
        self.assertEqual(Signature.objects.filter(flight__user__username='importer').count(), 0)
