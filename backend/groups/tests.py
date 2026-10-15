from django.contrib.auth import get_user_model

from flights.tests import PASSWORD, ApiTestCase
from .models import Group, Membership


class GroupTestCase(ApiTestCase):
    def login(self, username):
        self.client.credentials()
        self.register(username)
        res = self.client.post('/api/login/', {'username': username, 'password': PASSWORD}, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def create(self, name='Bay Area Gliders', kind='community', **extra):
        return self.client.post('/api/groups/', {'name': name, 'kind': kind, 'description': '', **extra}, format='json')

    def make_official(self, slug, **fields):
        Group.objects.filter(slug=slug).update(is_official=True, **fields)

    def member_id(self, slug, username):
        return Membership.objects.get(group__slug=slug, user__username=username).pk


class GroupTests(GroupTestCase):
    def test_creator_becomes_admin_and_slug_never_changes(self):
        self.login('owner')
        res = self.create('Bay Area Gliders', is_official=True)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['slug'], 'bay-area-gliders')
        self.assertFalse(res.data['is_official'])
        self.assertEqual(res.data['my_membership']['role'], 'admin')
        self.assertEqual(res.data['member_count'], 1)

        res = self.client.patch('/api/groups/bay-area-gliders/', {'name': 'NorCal Gliders'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data['name'], res.data['slug']), ('NorCal Gliders', 'bay-area-gliders'))

    def test_names_are_unique_ignoring_case(self):
        self.login('owner')
        self.create('Delta Air Lines', 'airline')
        res = self.create('delta air lines', 'airline')
        self.assertEqual(res.status_code, 400)
        self.assertIn('name', res.data)

    def test_five_group_cap(self):
        self.login('owner')
        for n in range(5):
            self.assertEqual(self.create(f'Club {n}').status_code, 201)
        res = self.create('Club 5')
        self.assertEqual(res.status_code, 400)
        self.assertIn('5', str(res.data))

    def test_only_staff_make_alliances(self):
        self.login('owner')
        self.assertEqual(self.create('Star Alliance', 'alliance').status_code, 400)

    def test_search_and_my_groups(self):
        self.login('owner')
        self.create('Delta Air Lines', 'airline')
        self.login('other')
        self.create('Wheels Up', 'operator')
        self.assertEqual([g['slug'] for g in self.client.get('/api/groups/?q=delta').data], ['delta-air-lines'])
        self.assertEqual([g['slug'] for g in self.client.get('/api/groups/?mine=1').data], ['wheels-up'])

    def test_groups_need_sign_in(self):
        self.assertEqual(self.client.get('/api/groups/').status_code, 401)

    def test_open_join_and_leave(self):
        self.login('owner')
        self.create()
        self.login('pilot')
        res = self.client.post('/api/groups/bay-area-gliders/members/')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['status'], 'active')
        self.assertEqual(self.client.post('/api/groups/bay-area-gliders/members/').status_code, 200)
        res = self.client.delete(f"/api/groups/bay-area-gliders/members/{res.data['id']}/")
        self.assertEqual(res.status_code, 204)

    def test_official_join_needs_approval_and_decline_allows_retry(self):
        self.login('owner')
        self.create('Delta Air Lines', 'airline')
        self.make_official('delta-air-lines')
        self.login('pilot')
        self.assertEqual(self.client.post('/api/groups/delta-air-lines/members/').data['status'], 'pending')
        request_id = self.member_id('delta-air-lines', 'pilot')
        self.assertEqual(self.client.patch(f'/api/groups/delta-air-lines/members/{request_id}/', {'status': 'active'}, format='json').status_code, 403)

        self.login('owner')
        self.assertEqual([m['username'] for m in self.client.get('/api/groups/delta-air-lines/').data['pending']], ['pilot'])
        self.assertEqual(self.client.delete(f'/api/groups/delta-air-lines/members/{request_id}/').status_code, 204)

        self.login('pilot')
        self.client.post('/api/groups/delta-air-lines/members/')
        self.login('owner')
        request_id = self.member_id('delta-air-lines', 'pilot')
        res = self.client.patch(f'/api/groups/delta-air-lines/members/{request_id}/', {'status': 'active'}, format='json')
        self.assertEqual(res.data['status'], 'active')

    def test_last_admin_cannot_leave_or_step_down(self):
        self.login('owner')
        self.create()
        own = self.member_id('bay-area-gliders', 'owner')
        self.assertEqual(self.client.delete(f'/api/groups/bay-area-gliders/members/{own}/').status_code, 400)
        res = self.client.patch(f'/api/groups/bay-area-gliders/members/{own}/', {'role': 'member'}, format='json')
        self.assertEqual(res.status_code, 400)

        self.login('pilot')
        self.client.post('/api/groups/bay-area-gliders/members/')
        self.login('owner')
        pilot = self.member_id('bay-area-gliders', 'pilot')
        res = self.client.patch(f'/api/groups/bay-area-gliders/members/{pilot}/', {'role': 'admin'}, format='json')
        self.assertEqual(res.data['role'], 'admin')
        self.assertEqual(self.client.delete(f'/api/groups/bay-area-gliders/members/{own}/').status_code, 204)

    def test_members_only_edit_and_admins_cannot_delete_official_groups(self):
        self.login('owner')
        self.create('Delta Air Lines', 'airline')
        self.login('pilot')
        self.client.post('/api/groups/delta-air-lines/members/')
        self.assertEqual(self.client.patch('/api/groups/delta-air-lines/', {'description': 'x'}, format='json').status_code, 403)
        self.assertEqual(self.client.delete('/api/groups/delta-air-lines/').status_code, 403)

        self.make_official('delta-air-lines')
        self.login('owner')
        self.assertEqual(self.client.delete('/api/groups/delta-air-lines/').status_code, 403)
        get_user_model().objects.filter(username='owner').update(is_staff=True)
        self.assertEqual(self.client.delete('/api/groups/delta-air-lines/').status_code, 204)

    def test_private_members_are_counted_not_named(self):
        self.login('owner')
        self.create()
        get_user_model().objects.filter(username='owner').update(is_public=True)
        self.login('hidden')
        self.client.post('/api/groups/bay-area-gliders/members/')
        self.login('viewer')
        res = self.client.get('/api/groups/bay-area-gliders/')
        self.assertEqual([m['username'] for m in res.data['members']], ['owner'])
        self.assertEqual((res.data['private_count'], res.data['member_count']), (1, 2))
        self.assertEqual(res.data['pending'], [])

    def test_alliance_lists_member_airlines_and_cannot_be_joined(self):
        alliance = Group.objects.create(name='Star Alliance', kind='alliance', is_official=True)
        self.login('owner')
        self.create('United', 'airline')
        Group.objects.filter(slug='united').update(parent=alliance)
        self.login('pilot')
        self.assertEqual(self.client.post('/api/groups/star-alliance/members/').status_code, 400)
        res = self.client.get('/api/groups/star-alliance/')
        self.assertEqual(res.data['children'], [{'slug': 'united', 'name': 'United', 'member_count': 1}])
        self.assertEqual(self.client.get('/api/groups/united/').data['parent'], {'slug': 'star-alliance', 'name': 'Star Alliance'})

    def test_admins_remove_members_but_not_other_admins(self):
        self.login('owner')
        self.create()
        for username in ('cohost', 'pest'):
            self.login(username)
            self.client.post('/api/groups/bay-area-gliders/members/')
        self.login('owner')
        cohost = self.member_id('bay-area-gliders', 'cohost')
        self.client.patch(f'/api/groups/bay-area-gliders/members/{cohost}/', {'role': 'admin'}, format='json')
        self.assertEqual(self.client.delete(f"/api/groups/bay-area-gliders/members/{self.member_id('bay-area-gliders', 'pest')}/").status_code, 204)
        self.login('cohost')
        own = self.member_id('bay-area-gliders', 'owner')
        self.assertEqual(self.client.delete(f'/api/groups/bay-area-gliders/members/{own}/').status_code, 403)

    def test_official_groups_keep_their_name_and_kind(self):
        self.login('owner')
        self.create('Delta Air Lines', 'airline')
        self.make_official('delta-air-lines')
        res = self.client.patch('/api/groups/delta-air-lines/', {'name': 'Free Upgrades', 'kind': 'airline'}, format='json')
        self.assertEqual(res.status_code, 400)
        res = self.client.patch('/api/groups/delta-air-lines/', {'name': 'Delta Air Lines', 'kind': 'airline', 'description': 'Hi'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)

    def test_staff_alliances_start_without_members(self):
        self.login('staffer')
        get_user_model().objects.filter(username='staffer').update(is_staff=True)
        res = self.create('Star Alliance', 'alliance')
        self.assertEqual((res.status_code, res.data['member_count'], res.data['my_membership']), (201, 0, None))

    def test_deleting_the_only_admin_hands_the_group_on(self):
        self.login('owner')
        self.create()
        self.login('pilot')
        self.client.post('/api/groups/bay-area-gliders/members/')
        self.login('owner')
        self.assertEqual(self.client.delete('/api/me/', {'confirm': 'owner', 'password': PASSWORD}, format='json').status_code, 204)
        self.assertEqual(Membership.objects.get(group__slug='bay-area-gliders').role, 'admin')

    def test_public_profile_shows_active_groups_only(self):
        self.login('owner')
        self.create('Bay Area Gliders')
        self.create('Delta Air Lines', 'airline')
        self.make_official('delta-air-lines')
        self.login('pilot')
        get_user_model().objects.filter(username='pilot').update(is_public=True)
        self.client.post('/api/groups/bay-area-gliders/members/')
        self.client.post('/api/groups/delta-air-lines/members/')
        res = self.client.get('/api/pilots/pilot/')
        self.assertEqual(res.data['groups'], [
            {'slug': 'bay-area-gliders', 'name': 'Bay Area Gliders', 'kind': 'community', 'is_official': False},
        ])
