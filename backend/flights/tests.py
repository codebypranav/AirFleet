from unittest import mock

from django.test import override_settings
from rest_framework.test import APITestCase

from .models import Flight

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


class ApiFlowTests(APITestCase):
    def register(self, username='pilot'):
        return self.client.post('/api/register/', {
            'username': username,
            'email': f'{username}@example.com',
            'password': 'Sup3r-secret-pw',
            'password2': 'Sup3r-secret-pw',
        }, format='json')

    def authenticate(self, username='pilot'):
        self.register(username)
        res = self.client.post('/api/login/', {'username': username, 'password': 'Sup3r-secret-pw'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        return res.data

    def test_register_returns_tokens(self):
        res = self.register()
        self.assertEqual(res.status_code, 201)
        self.assertIn('access', res.data)
        self.assertIn('refresh', res.data)

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
        res = self.client.post('/api/flights/', FLIGHT, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        flight_id = res.data['id']

        self.assertEqual(len(self.client.get('/api/flights/').data), 1)

        updated = {**FLIGHT, 'notes': 'Smooth ride'}
        res = self.client.put(f'/api/flights/{flight_id}/', updated, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['notes'], 'Smooth ride')

        self.assertEqual(self.client.delete(f'/api/flights/{flight_id}/').status_code, 204)
        self.assertFalse(Flight.objects.exists())

    def test_flight_validation(self):
        self.authenticate()
        res = self.client.post('/api/flights/', {**FLIGHT, 'total_time': '01:00:00'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_users_only_see_their_own_flights(self):
        self.authenticate('alice')
        flight_id = self.client.post('/api/flights/', FLIGHT, format='json').data['id']
        self.authenticate('bob')
        self.assertEqual(self.client.get('/api/flights/').data, [])
        self.assertEqual(self.client.get(f'/api/flights/{flight_id}/').status_code, 404)

    def test_rankings(self):
        self.authenticate()
        self.client.post('/api/flights/', FLIGHT, format='json')
        self.client.credentials()
        res = self.client.get('/api/rankings/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['flights'][0], {'username': 'pilot', 'total_flights': 1})
        self.assertEqual(res.data['distance'][0]['total_distance'], 2145)

    @override_settings(OPENAI_API_KEY='sk-test')
    def test_generate_narrative(self):
        self.authenticate()
        completion = mock.Mock()
        completion.choices = [mock.Mock(message=mock.Mock(content='  A smooth flight.  '))]
        with mock.patch('flights.views.OpenAI') as client_cls:
            client_cls.return_value.chat.completions.create.return_value = completion
            res = self.client.post('/api/generate-narrative/', FLIGHT, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, {'narrative': 'A smooth flight.'})

    @override_settings(OPENAI_API_KEY='')
    def test_generate_narrative_without_key(self):
        self.authenticate()
        res = self.client.post('/api/generate-narrative/', FLIGHT, format='json')
        self.assertEqual(res.status_code, 503)


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
class PhotoUploadTests(APITestCase):
    def test_flight_with_photo(self):
        import io
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.post('/api/register/', {
            'username': 'pilot', 'email': 'pilot@example.com',
            'password': 'Sup3r-secret-pw', 'password2': 'Sup3r-secret-pw',
        }, format='json')
        token = self.client.post('/api/login/', {'username': 'pilot', 'password': 'Sup3r-secret-pw'}, format='json').data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        buf = io.BytesIO()
        Image.new('RGB', (4, 4), 'blue').save(buf, 'PNG')
        photo = SimpleUploadedFile('runway.png', buf.getvalue(), content_type='image/png')
        res = self.client.post('/api/flights/', {**FLIGHT, 'photo': photo}, format='multipart')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertIn('flight_photos/runway', res.data['photo'])
        self.assertTrue(Flight.objects.get().photo.storage.exists(Flight.objects.get().photo.name))
