import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from openai import OpenAI, OpenAIError
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from . import airports, external, insights, logbook_io
from .models import Aircraft, Flight
from .serializers import AircraftSerializer, FlightSerializer, PublicFlightSerializer

logger = logging.getLogger(__name__)

MAX_IMPORT_BYTES = 5 * 1024 * 1024


class NarrativeThrottle(UserRateThrottle):
    scope = 'narrative'


class LookupThrottle(UserRateThrottle):
    scope = 'lookup'


class FlightPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def filter_flights(queryset, params):
    """Filters shared by the logbook list, CSV export and stats: ?from, ?to, ?airport, ?aircraft, ?q, ?simulator."""
    if date_from := parse_date(params.get('from', '')):
        queryset = queryset.filter(departure_time__date__gte=date_from)
    if date_to := parse_date(params.get('to', '')):
        queryset = queryset.filter(departure_time__date__lte=date_to)
    if airport := params.get('airport', '').strip().upper():
        queryset = queryset.filter(Q(departure_airport=airport) | Q(arrival_airport=airport))
    if aircraft := params.get('aircraft', '').strip().upper():
        queryset = queryset.filter(registration_number=aircraft)
    if q := params.get('q', '').strip():
        queryset = queryset.filter(Q(notes__icontains=q) | Q(flight_plan__icontains=q) | Q(narrative__icontains=q))
    if params.get('simulator') in ('true', 'false'):
        queryset = queryset.filter(is_simulator=params['simulator'] == 'true')
    return queryset


class UserFlightsMixin:
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Flight.objects.filter(user=self.request.user).select_related('aircraft')


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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_flights(request):
    flights = filter_flights(Flight.objects.filter(user=request.user), request.query_params)
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


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([NarrativeThrottle])
def generate_narrative(request):
    """Write a short story for one of the pilot's flights and save it on the flight."""
    flight_id = request.data.get('flight_id')
    if not flight_id:
        return Response({'error': 'flight_id is required'}, status=400)
    flight = get_object_or_404(Flight.objects.select_related('aircraft'), pk=flight_id, user=request.user)

    if not settings.OPENAI_API_KEY:
        return Response({"error": "OpenAI API key is not configured"}, status=503)

    dep, arr = airports.get(flight.departure_airport), airports.get(flight.arrival_airport)
    aircraft = flight.registration_number + (f" ({flight.aircraft.type_code})" if flight.aircraft and flight.aircraft.type_code else '')
    lines = [
        f"- Departure: {flight.departure_airport}{f' ({dep.name})' if dep else ''} at {flight.departure_time:%Y-%m-%d %H:%M} UTC",
        f"- Arrival: {flight.arrival_airport}{f' ({arr.name})' if arr else ''} at {flight.arrival_time:%Y-%m-%d %H:%M} UTC",
        f"- Duration: {flight.total_time}",
        f"- Distance: {flight.distance} nautical miles",
        f"- Aircraft: {aircraft}",
        f"- Aircraft condition: {flight.get_aircraft_condition_display()}",
        f"- Weather: {flight.weather_conditions or 'Unknown'}",
    ]
    if flight.night_time:
        lines.append(f"- Night time: {flight.night_time}")
    if flight.instrument_time or flight.approaches:
        lines.append(f"- Instrument time: {flight.instrument_time}, approaches flown: {flight.approaches}")
    if flight.is_simulator:
        lines.append("- Flown in a simulator")
    if flight.notes:
        lines.append(f"- Pilot's notes: {flight.notes[:500]}")
    prompt = (
        "Write a short account of this flight:\n" + "\n".join(lines) +
        "\n\nWrite 2-3 plain sentences in the voice of a pilot's own notes: where they went, how long it took, "
        "and anything notable about the weather, the aircraft or the notes. Stick to the details above and don't "
        "invent anything. No dramatic or flowery language, no exclamation marks."
    )

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You write brief, matter-of-fact summaries of flights for a pilot's logbook."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=250,
            temperature=0.7,
        )
    except OpenAIError:
        logger.exception("OpenAI request failed for flight %s", flight.pk)
        return Response({"error": "Failed to generate narrative"}, status=502)

    flight.narrative = (response.choices[0].message.content or '').strip()
    flight.narrative_generated_at = timezone.now()
    flight.save(update_fields=['narrative', 'narrative_generated_at', 'updated_at'])
    return Response({"narrative": flight.narrative, "narrative_generated_at": flight.narrative_generated_at})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stats(request):
    flights = filter_flights(Flight.objects.filter(user=request.user), request.query_params)
    return Response(insights.summary(flights))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def routes(request):
    flights = filter_flights(Flight.objects.filter(user=request.user), request.query_params)
    return Response(insights.routes(flights))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def currency(request):
    return Response(insights.currency(Flight.objects.filter(user=request.user)))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def achievements(request):
    return Response(insights.achievements(Flight.objects.filter(user=request.user)))


def fleet(user):
    recent = Q(flights__departure_time__gte=timezone.now() - timedelta(days=insights.FORECAST_WINDOW_DAYS))
    return Aircraft.objects.filter(user=user).annotate(
        total_flights=Count('flights'), total_time=Sum('flights__total_time'),
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
        Flight.objects.select_related('user', 'aircraft'), pk=pk, user__is_public=True, user__is_active=True,
    )
    return Response(PublicFlightSerializer(flight, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_pilot(request, username):
    pilot = get_object_or_404(get_user_model(), username=username, is_public=True, is_active=True)
    flights = Flight.objects.filter(user=pilot).select_related('aircraft')
    return Response({
        'username': pilot.username,
        'bio': pilot.bio,
        'home_airport': pilot.home_airport,
        'member_since': pilot.date_joined.date().isoformat(),
        'stats': insights.summary(flights)['totals'],
        'achievements': [a for a in insights.achievements(flights) if a['earned']],
        'recent_flights': PublicFlightSerializer(flights[:10], many=True, context={'request': request}).data,
        'routes': insights.routes(flights),
    })
