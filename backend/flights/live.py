from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from . import crew, realism
from .models import CrewSeat, Flight
from .serializers import FlightSerializer

CHECK_IN = timedelta(minutes=30)
AUTO_LAND = timedelta(hours=2)


def unconfirmed(flight):
    return timezone.now() >= flight.arrival_time + CHECK_IN


def settle():
    Flight.objects.filter(in_flight=True, arrival_time__lte=timezone.now() - AUTO_LAND).update(in_flight=False)


def visible_to(user):
    crewed = CrewSeat.objects.filter(pilot=user).exclude(status=CrewSeat.DECLINED).values('flight')
    mine = Flight.objects.filter(Q(user=user) | Q(pk__in=crewed))
    return (mine | Flight.objects.followed_by(user)).filter(in_flight=True).select_related('user')


@transaction.atomic
def start(request, *, role, ete_minutes, crew_members=(), **route):
    settle()
    now = timezone.now()
    serializer = FlightSerializer(
        data={**route, 'departure_time': now, 'arrival_time': now + timedelta(minutes=ete_minutes), 'is_draft': True},
        context={'request': request, 'live': True},
    )
    serializer.is_valid(raise_exception=True)
    try:
        with transaction.atomic():
            flight = serializer.save(user=request.user, in_flight=True)
    except IntegrityError:
        raise ValidationError("You already have a flight in progress. Land it first.")
    crew.set_role(flight, role)
    for member in crew_members:
        crew.invite(flight, **member)
    return flight


def still_flying(flight):
    cap = flight.departure_time + timedelta(hours=realism.MAX_FLIGHT_HOURS)
    flight.arrival_time = min(max(flight.arrival_time, timezone.now()), cap)
    flight.total_time = flight.arrival_time - flight.departure_time
    flight.save(update_fields=['arrival_time', 'total_time', 'updated_at'])
    return flight


def land(flight, arrival_time=None):
    now = timezone.now()
    arrival_time = arrival_time or now
    if not flight.departure_time < arrival_time <= now + realism.CLOCK_SKEW:
        raise ValidationError({'arrival_time': ["Pick a landing time between take-off and now."]})
    flight.arrival_time, flight.total_time, flight.in_flight = arrival_time, arrival_time - flight.departure_time, False
    flight.save(update_fields=['arrival_time', 'total_time', 'in_flight', 'updated_at'])
    return flight
