import uuid

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from .models import CrewSeat, Flight
from .serializers import FlightSerializer

OWN = (CrewSeat.LOGGER, CrewSeat.ACCEPTED)
COPIED_FIELDS = (
    'departure_airport', 'arrival_airport', 'departure_time', 'arrival_time', 'total_time',
    'departure_gate', 'arrival_gate', 'distance', 'registration_number', 'night_time', 'instrument_time',
    'cross_country', 'is_simulator', 'weather_conditions', 'flight_plan', 'aircraft_condition',
)


def own_seat(flight):
    return flight.crew_seats.filter(status__in=OWN).first()


def logger_seat(flight):
    if flight.is_draft:
        raise ValidationError({'username': ["Log the flight before adding crew."]})
    Flight.objects.select_for_update().filter(pk=flight.pk).first()
    seat = own_seat(flight)
    if seat is None:
        role = CrewSeat.PIC if flight.pic_time >= flight.sic_time else CrewSeat.SIC
        seat = CrewSeat.objects.create(crew=uuid.uuid4(), pilot=flight.user, flight=flight, role=role, status=CrewSeat.LOGGER)
    return seat


def members(flight):
    seat = own_seat(flight)
    if seat is None:
        return CrewSeat.objects.none()
    seats = CrewSeat.objects.filter(crew=seat.crew).select_related('pilot')
    return seats if seat.status == CrewSeat.LOGGER else seats.filter(status__in=OWN)


@transaction.atomic
def set_role(flight, role):
    seat = logger_seat(flight)
    seat.role = role
    seat.save(update_fields=['role'])
    return seat


@transaction.atomic
def invite(flight, username, role):
    seat = logger_seat(flight)
    if seat.status != CrewSeat.LOGGER:
        raise ValidationError({'username': ["Only the pilot who logged this flight can add crew."]})
    pilot = get_user_model().objects.filter(username__iexact=username.strip(), is_active=True).first()
    if pilot is None:
        raise ValidationError({'username': [f"No AirFleet pilot is called {username.strip()}."]})
    if pilot == flight.user:
        raise ValidationError({'username': ["You're already on this flight."]})
    try:
        with transaction.atomic():
            return CrewSeat.objects.create(crew=seat.crew, pilot=pilot, flight=flight, role=role, status=CrewSeat.PENDING)
    except IntegrityError:
        raise ValidationError({'username': [f"{pilot.username} is already on this crew."]})


@transaction.atomic
def accept(seat, request):
    original = seat.flight
    if original.is_draft:
        raise ValidationError({'error': ["This flight has gone back to being a draft. Ask the pilot to log it again."]})
    data = {field: getattr(original, field) for field in COPIED_FIELDS}
    data['pic_time' if seat.role == CrewSeat.PIC else 'sic_time'] = original.total_time
    serializer = FlightSerializer(data=data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    copy = serializer.save(user=request.user)
    seat.flight, seat.status = copy, CrewSeat.ACCEPTED
    seat.save(update_fields=['flight', 'status'])
    return serializer.data
