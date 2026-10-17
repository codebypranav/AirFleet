import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from groups.models import Group
from . import airports, ask, crew, external, flight_plans, follows, insights, live, logbook_io, patterns, plan_review, quick_log, social
from .models import Aircraft, Block, CrewSeat, Flight, Follow
from .serializers import (
    AddCrewSerializer, AircraftSerializer, CommentSerializer, CrewInviteSerializer, CrewRoleSerializer, CrewSeatSerializer, FlightSerializer,
    LandSerializer, FeedFlightSerializer, LiveFlightSerializer, NotificationSerializer, PublicFlightSerializer, StartFlightSerializer,
)

logger = logging.getLogger(__name__)

MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_PLAN_BYTES = 10 * 1024 * 1024


class QuickLogThrottle(UserRateThrottle):
    scope = 'quick_log'


class LookupThrottle(UserRateThrottle):
    scope = 'lookup'


class CrewInviteThrottle(UserRateThrottle):
    scope = 'invite'


class FollowThrottle(UserRateThrottle):
    scope = 'follow'


class CommentThrottle(UserRateThrottle):
    scope = 'comment'

    def allow_request(self, request, view):
        return request.method not in ('POST', 'PATCH') or super().allow_request(request, view)


class LikeThrottle(UserRateThrottle):
    scope = 'like'


class FlightPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def filter_flights(queryset, params):
    """Filters shared by the logbook list, CSV export and stats: ?from, ?to, ?airport, ?aircraft, ?q, ?simulator, ?draft."""
    if date_from := parse_date(params.get('from', '')):
        queryset = queryset.filter(departure_time__date__gte=date_from)
    if date_to := parse_date(params.get('to', '')):
        queryset = queryset.filter(departure_time__date__lte=date_to)
    if airport := params.get('airport', '').strip().upper():
        queryset = queryset.filter(Q(departure_airport=airport) | Q(arrival_airport=airport))
    if aircraft := params.get('aircraft', '').strip().upper():
        queryset = queryset.filter(registration_number=aircraft)
    if q := params.get('q', '').strip():
        queryset = queryset.filter(Q(notes__icontains=q) | Q(flight_plan__icontains=q))
    if params.get('simulator') in ('true', 'false'):
        queryset = queryset.filter(is_simulator=params['simulator'] == 'true')
    if params.get('draft') in ('true', 'false'):
        queryset = queryset.filter(is_draft=params['draft'] == 'true')
    return queryset


class UserFlightsMixin:
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        live.settle()
        return Flight.objects.filter(user=self.request.user).select_related('aircraft').prefetch_related('signatures')


class FlightListView(UserFlightsMixin, generics.ListCreateAPIView):
    serializer_class = FlightSerializer
    pagination_class = FlightPagination

    def get_queryset(self):
        return filter_flights(super().get_queryset(), self.request.query_params)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'status': 'error', 'errors': serializer.errors, 'message': 'Invalid flight data'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class FlightDetailView(UserFlightsMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FlightSerializer


class CrewView(APIView):
    permission_classes = [IsAuthenticated]

    def get_throttles(self):
        return [CrewInviteThrottle()] if self.request.method == 'POST' else []

    def flight(self, pk):
        return get_object_or_404(Flight, pk=pk, user=self.request.user)

    def seats(self, flight):
        return CrewSeatSerializer(crew.members(flight), many=True, context={'request': self.request}).data

    def get(self, request, pk):
        return Response(self.seats(self.flight(pk)))

    def post(self, request, pk):
        flight = self.flight(pk)
        serializer = AddCrewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        crew.invite(flight, **serializer.validated_data)
        return Response(self.seats(flight), status=201)

    def patch(self, request, pk):
        flight = self.flight(pk)
        serializer = CrewRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        crew.set_role(flight, serializer.validated_data['role'])
        return Response(self.seats(flight))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def crew_invites(request):
    seats = CrewSeat.objects.filter(pilot=request.user, status=CrewSeat.PENDING).select_related('flight__user', 'flight__aircraft')
    return Response(CrewInviteSerializer(seats, many=True, context={'request': request}).data)


class LiveFlightsView(APIView):
    permission_classes = [IsAuthenticated]

    def get_throttles(self):
        return [CrewInviteThrottle()] if self.request.method == 'POST' else []

    def get(self, request):
        live.settle()
        return Response(LiveFlightSerializer(live.visible_to(request.user), many=True, context={'request': request}).data)

    def post(self, request):
        serializer = StartFlightSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        flight = live.start(request, crew_members=data.pop('crew', []), **data)
        return Response(LiveFlightSerializer(flight, context={'request': request}).data, status=201)


def pilot_card(request, user, avatar=True, **extra):
    url = request.build_absolute_uri(user.avatar.url) if avatar and user.avatar else None
    return {'username': user.username, 'avatar': url, **extra}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def follow_list(request):
    following = Follow.objects.filter(follower=request.user, pilot__is_active=True).select_related('pilot')
    followers = Follow.objects.filter(pilot=request.user, follower__is_active=True).select_related('follower')
    blocked = Block.objects.filter(blocker=request.user).select_related('blocked')
    return Response({
        'following': [pilot_card(request, f.pilot, f.status == Follow.APPROVED, status=f.status) for f in following],
        'followers': [pilot_card(request, f.follower) for f in followers if f.status == Follow.APPROVED],
        'requests': [pilot_card(request, f.follower) for f in followers if f.status == Follow.PENDING],
        'blocked': [pilot_card(request, b.blocked, False) for b in blocked],
    })


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
@throttle_classes([FollowThrottle])
def follow_pilot(request, username):
    if request.method == 'DELETE':
        follows.unfollow(request.user, username)
        return Response(status=204)
    follow = follows.follow(request.user, username)
    return Response({'username': follow.pilot.username, 'status': follow.status})


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
@throttle_classes([FollowThrottle])
def follower(request, username):
    (follows.approve if request.method == 'POST' else follows.remove)(request.user, username)
    return Response(status=204)


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
@throttle_classes([FollowThrottle])
def block_pilot(request, username):
    (follows.block if request.method == 'POST' else follows.unblock)(request.user, username)
    return Response(status=204)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def feed(request):
    paginator = FlightPagination()
    page = paginator.paginate_queryset(feed_flights(request.user).order_by('-departure_time', '-pk'), request)
    return paginator.get_paginated_response(FeedFlightSerializer(page, many=True).data)


def feed_flights(user):
    return social.with_counts(user, Flight.objects.logged().followed_by(user).select_related('user', 'aircraft'))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def feed_entry(request, pk):
    return Response(FeedFlightSerializer(get_object_or_404(feed_flights(request.user), pk=pk)).data)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([CommentThrottle])
def flight_comments(request, pk):
    flight = social.flight_for(request.user, pk)
    if request.method == 'POST':
        comment = social.comment(request.user, flight, request.data.get('body'), request.data.get('parent'))
        return Response(CommentSerializer(comment, context={'request': request}).data, status=201)
    return Response(CommentSerializer(social.thread(request.user, flight), many=True, context={'request': request}).data)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
@throttle_classes([CommentThrottle])
def comment_detail(request, pk):
    if request.method == 'DELETE':
        social.delete(request.user, pk)
        return Response(status=204)
    comment = social.edit(request.user, pk, request.data.get('body'))
    return Response(CommentSerializer(comment, context={'request': request}).data)


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
@throttle_classes([LikeThrottle])
def like_flight(request, pk):
    return Response(social.set_like(request.user, social.flight_for(request.user, pk), request.method == 'POST'))


@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
@throttle_classes([LikeThrottle])
def like_comment(request, pk):
    flight, comment = social.comment_for_like(request.user, pk)
    return Response(social.set_like(request.user, flight, request.method == 'POST', comment))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_list(request):
    return Response(NotificationSerializer(social.notifications(request.user), many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_notifications(request):
    return Response({'count': social.unread_count(request.user)})


def my_live_flight(request, pk):
    live.settle()
    return get_object_or_404(Flight.objects.select_for_update(), pk=pk, user=request.user, in_flight=True)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def still_flying(request, pk):
    flight = live.still_flying(my_live_flight(request, pk))
    return Response(LiveFlightSerializer(flight, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def land_flight(request, pk):
    serializer = LandSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    flight = live.land(my_live_flight(request, pk), serializer.validated_data.get('arrival_time'))
    return Response(FlightSerializer(flight, context={'request': request}).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_crew_invite(request, pk):
    with transaction.atomic():
        seat = get_object_or_404(
            CrewSeat.objects.select_for_update().select_related('flight'), pk=pk, pilot=request.user, status=CrewSeat.PENDING,
        )
        return Response(crew.accept(seat, request), status=201)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def end_crew_seat(request, pk):
    seat = get_object_or_404(
        CrewSeat.objects.filter(Q(pilot=request.user) | Q(flight__user=request.user)), pk=pk, status=CrewSeat.PENDING,
    )
    pending = CrewSeat.objects.filter(pk=seat.pk, status=CrewSeat.PENDING)
    if seat.pilot_id == request.user.pk:
        changed = pending.update(status=CrewSeat.DECLINED)
    else:
        changed, _ = pending.delete()
    return Response(status=204 if changed else 404)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_flights(request):
    flights = filter_flights(Flight.objects.logged().filter(user=request.user), request.query_params)
    response = HttpResponse(logbook_io.export_csv(flights), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="airfleet-logbook-{timezone.now():%Y-%m-%d}.csv"'
    return response


class ImportFlightsView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload = request.FILES.get('file')
        if not upload:
            return Response({'error': 'Attach a CSV file as "file".'}, status=400)
        if upload.size > MAX_IMPORT_BYTES:
            return Response({'error': 'Imports are limited to 5 MB.'}, status=400)
        raw = upload.read()
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = raw.decode('latin-1')
        try:
            result = logbook_io.import_flights(text, request)
        except logbook_io.LogbookImportError as e:
            return Response({'error': str(e)}, status=400)
        return Response(result, status=201 if result['created'] else 200)


class FlightPlanView(APIView):
    """Read an uploaded flight plan PDF into a draft flight for the pilot to check. Nothing is saved, the PDF included."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]
    throttle_classes = [LookupThrottle]

    def post(self, request):
        upload = request.FILES.get('file')
        if not upload:
            return Response({'error': 'Attach a flight plan PDF as "file".'}, status=400)
        if upload.size > MAX_PLAN_BYTES:
            return Response({'error': 'Flight plans are limited to 10 MB.'}, status=400)
        data = upload.read()
        if not data.startswith(b'%PDF'):
            return Response({'error': 'Upload the flight plan as a PDF.'}, status=400)
        try:
            return Response(flight_plans.read(data))
        except flight_plans.FlightPlanError as e:
            return Response({'error': str(e)}, status=422)


class QuickLogView(APIView):
    """Read a plain-text description of a flight into the new-flight form. Nothing is saved.

    GET says whether quick log is set up, so the form can hide it when no AI provider is configured.
    """
    permission_classes = [IsAuthenticated]

    def get_throttles(self):
        return [QuickLogThrottle()] if self.request.method == 'POST' else []

    def get(self, request):
        return Response({'enabled': quick_log.enabled()})

    def post(self, request):
        fleet = list(Aircraft.objects.filter(user=request.user).values_list('registration', 'type_code'))
        try:
            return Response(quick_log.read(request.data.get('text'), request.data.get('now'), fleet))
        except quick_log.QuickLogError as e:
            return Response({'error': str(e)}, status=422)
        except quick_log.QuickLogUnavailable:
            return Response({'error': 'Quick log isn’t available right now. Fill in the form instead.'}, status=503)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stats(request):
    flights = filter_flights(Flight.objects.logged().filter(user=request.user), request.query_params)
    return Response(insights.summary(flights))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([QuickLogThrottle])
def ask_logbook(request):
    fleet = list(Aircraft.objects.filter(user=request.user).values_list('registration', 'type_code'))
    try:
        asked = ask.read(request.data.get('question'), quick_log._local_now(request.data.get('now')), fleet)
    except ask.AskError as e:
        return Response({'error': str(e)}, status=422)
    except quick_log.QuickLogUnavailable:
        return Response({'error': 'Asking isn’t available right now. Try again later.'}, status=503)
    return Response(ask.answer(Flight.objects.logged().filter(user=request.user), asked))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def routes(request):
    flights = filter_flights(Flight.objects.logged().filter(user=request.user), request.query_params)
    return Response(insights.routes(flights))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def currency(request):
    return Response(insights.currency(Flight.objects.logged().filter(user=request.user)))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def achievements(request):
    return Response(insights.achievements(Flight.objects.logged().filter(user=request.user)))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def flight_patterns(request):
    """What stands out across the pilot's flights and fleet; see patterns.py. themes_enabled says whether notes can be read by AI."""
    flights = Flight.objects.logged().filter(user=request.user)
    return Response({
        'findings': patterns.findings(flights, fleet(request.user), timezone.now().date()),
        'themes_enabled': quick_log.enabled(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([QuickLogThrottle])
def note_themes(request):
    """Recurring themes in the pilot's flight notes, read by a language model. Shares quick log's providers and rate limit."""
    try:
        return Response(patterns.note_themes(Flight.objects.logged().filter(user=request.user)))
    except patterns.ThemesError as e:
        return Response({'error': str(e)}, status=422)
    except quick_log.QuickLogUnavailable:
        return Response({'error': 'Reading your notes isn’t available right now. Try again later.'}, status=503)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([LookupThrottle])
def review_plan(request, pk):
    """Checks on a planned (draft) flight against the pilot's own logbook; see plan_review.py."""
    flight = get_object_or_404(Flight, pk=pk, user=request.user)
    if not flight.is_draft:
        return Response({'error': 'Only planned (draft) flights are reviewed.'}, status=400)
    aircraft = Aircraft.objects.filter(user=request.user, registration=flight.registration_number).first()
    return Response(plan_review.review(flight, Flight.objects.logged().filter(user=request.user), aircraft))


def fleet(user):
    logged = Q(flights__is_draft=False)
    recent = logged & Q(flights__departure_time__gte=timezone.now() - timedelta(days=insights.FORECAST_WINDOW_DAYS))
    return Aircraft.objects.filter(user=user).annotate(
        total_flights=Count('flights', filter=logged), total_time=Sum('flights__total_time', filter=logged),
        recent_time=Sum('flights__total_time', filter=recent),
    )


class AircraftMixin:
    permission_classes = [IsAuthenticated]
    serializer_class = AircraftSerializer

    def get_queryset(self):
        return fleet(self.request.user)


class AircraftListView(AircraftMixin, generics.ListCreateAPIView):
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AircraftDetailView(AircraftMixin, generics.RetrieveUpdateDestroyAPIView):
    pass


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def log_maintenance(request, pk):
    """Record completed maintenance: resets the hours counter and clears a grounding."""
    aircraft = get_object_or_404(Aircraft, pk=pk, user=request.user)
    performed_at = parse_datetime(request.data.get('performed_at') or '') or timezone.now()
    if timezone.is_naive(performed_at):
        performed_at = timezone.make_aware(performed_at)
    aircraft.last_maintenance_at = performed_at
    aircraft.grounded = False
    if annual_due := parse_date(request.data.get('annual_due') or ''):
        aircraft.annual_due = annual_due
    aircraft.save()
    aircraft = fleet(request.user).get(pk=pk)
    return Response(AircraftSerializer(aircraft, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def airport_search(request):
    try:
        limit = min(int(request.query_params.get('limit', 10)), 25)
    except ValueError:
        limit = 10
    return Response([a.as_dict() for a in airports.search(request.query_params.get('q', ''), limit)])


@api_view(['GET'])
@permission_classes([AllowAny])
def airport_detail(request, code):
    airport = airports.get(code)
    if not airport:
        return Response({'error': f'{code.upper()} is not a known airport'}, status=404)
    return Response(airport.as_dict())


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([LookupThrottle])
def weather(request):
    """?airport=KJFK&time=2026-01-01T10:00:00Z → the closest METAR."""
    airport = airports.get(request.query_params.get('airport', ''))
    if not airport:
        return Response({'error': 'Pass a known airport code as ?airport='}, status=400)
    at = parse_datetime(request.query_params.get('time') or '')
    if at and timezone.is_naive(at):
        at = timezone.make_aware(at)
    try:
        return Response(external.metar(airport.code, at))
    except external.ExternalLookupError as e:
        return Response({'error': str(e)}, status=e.status)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([LookupThrottle])
def simbrief(request):
    username = request.query_params.get('username', '').strip()
    if not username:
        return Response({'error': 'Pass your SimBrief username as ?username='}, status=400)
    try:
        return Response(external.simbrief_latest(username))
    except external.ExternalLookupError as e:
        return Response({'error': str(e)}, status=e.status)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_flight(request, pk):
    """A shareable flight page. Only flights of pilots who made their profile public."""
    flight = get_object_or_404(
        Flight.objects.logged().select_related('user', 'aircraft'), pk=pk, user__is_public=True, user__is_active=True,
    )
    return Response(PublicFlightSerializer(flight, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_pilot(request, username):
    pilot = get_object_or_404(get_user_model(), username=username, is_public=True, is_active=True)
    flights = Flight.objects.logged().filter(user=pilot).select_related('aircraft')
    return Response({
        'username': pilot.username,
        'avatar': request.build_absolute_uri(pilot.avatar.url) if pilot.avatar else None,
        'bio': pilot.bio,
        'home_airport': pilot.home_airport,
        'member_since': pilot.date_joined.date().isoformat(),
        'followers': follows.follower_counts([pilot.username]).get(pilot.username, 0),
        'following': Follow.objects.filter(follower=pilot, status=Follow.APPROVED, pilot__is_active=True).count(),
        'stats': insights.summary(flights)['totals'],
        'achievements': [a for a in insights.achievements(flights) if a['earned']],
        'recent_flights': PublicFlightSerializer(flights[:10], many=True, context={'request': request}).data,
        'routes': insights.routes(flights),
        'groups': list(Group.objects.filter(memberships__user=pilot, memberships__status='active').values('slug', 'name', 'kind', 'is_official')),
    })
