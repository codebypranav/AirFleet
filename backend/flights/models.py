from datetime import timedelta

from django.conf import settings
from django.core.validators import MinLengthValidator
from django.db import models
from django.db.models import Sum


class Aircraft(models.Model):
    CLASS_CHOICES = [
        ('SEL', 'Single-engine land'),
        ('MEL', 'Multi-engine land'),
        ('SES', 'Single-engine sea'),
        ('MES', 'Multi-engine sea'),
        ('HELICOPTER', 'Helicopter'),
        ('GLIDER', 'Glider'),
        ('OTHER', 'Other'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='aircraft')
    registration = models.CharField(max_length=10)
    type_code = models.CharField(max_length=4, blank=True, help_text="ICAO type designator, e.g. C172")
    make_model = models.CharField(max_length=60, blank=True)
    aircraft_class = models.CharField(max_length=10, choices=CLASS_CHOICES, default='SEL')
    notes = models.TextField(blank=True)
    maintenance_interval_hours = models.PositiveIntegerField(default=100)
    last_maintenance_at = models.DateTimeField(null=True, blank=True)
    annual_due = models.DateField(null=True, blank=True)
    # Set when a flight reports the aircraft GROUNDED; cleared by logging maintenance.
    grounded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['registration']
        constraints = [
            models.UniqueConstraint(fields=['user', 'registration'], name='unique_registration_per_user'),
        ]
        verbose_name_plural = 'aircraft'

    def __str__(self):
        return self.registration

    def hours_since_maintenance(self):
        flights = self.flights.logged()
        if self.last_maintenance_at:
            flights = flights.filter(departure_time__gte=self.last_maintenance_at)
        return flights.aggregate(total=Sum('total_time'))['total'] or timedelta(0)


class FlightQuerySet(models.QuerySet):
    def logged(self):
        """Flights in the logbook proper. Drafts (planned, not yet flown) don't count towards anything."""
        return self.filter(is_draft=False)


class Flight(models.Model):
    objects = FlightQuerySet.as_manager()

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='flights'
    )
    aircraft = models.ForeignKey(Aircraft, on_delete=models.SET_NULL, null=True, blank=True, related_name='flights')

    CONDITION_CHOICES = [
        ('GROUNDED', 'Grounded'),
        ('MAINTENANCE', 'Needs Maintenance'),
        ('MINOR_ISSUES', 'Minor Issues'),
        ('GOOD', 'Good Condition'),
        ('AIRWORTHY', 'Airworthy'),
    ]

    departure_airport = models.CharField(max_length=4, validators=[MinLengthValidator(4)])
    arrival_airport = models.CharField(max_length=4, validators=[MinLengthValidator(4)])
    departure_time = models.DateTimeField()
    arrival_time = models.DateTimeField()
    total_time = models.DurationField()
    departure_gate = models.CharField(max_length=10, blank=True)
    arrival_gate = models.CharField(max_length=10, blank=True)
    flight_plan = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    photo = models.ImageField(upload_to='flight_photos/', null=True, blank=True)
    aircraft_condition = models.CharField(
        max_length=20,
        choices=CONDITION_CHOICES,
        default='AIRWORTHY'
    )
    registration_number = models.CharField(max_length=10)
    distance = models.IntegerField(
        default=0,
        help_text="Distance in nautical miles"
    )

    # Logbook columns. Each time is a share of total_time.
    pic_time = models.DurationField(default=timedelta(0))
    sic_time = models.DurationField(default=timedelta(0))
    dual_received_time = models.DurationField(default=timedelta(0))
    night_time = models.DurationField(default=timedelta(0))
    instrument_time = models.DurationField(default=timedelta(0), help_text="Actual instrument conditions")
    simulated_instrument_time = models.DurationField(default=timedelta(0), help_text="Under the hood")
    day_landings = models.PositiveSmallIntegerField(default=0)
    night_landings = models.PositiveSmallIntegerField(default=0)
    approaches = models.PositiveSmallIntegerField(default=0)
    cross_country = models.BooleanField(default=False)
    is_simulator = models.BooleanField(default=False)
    # Started from a flight plan before the flight; finalised once the actual times are in.
    is_draft = models.BooleanField(default=False)

    weather_conditions = models.TextField(blank=True, help_text="Usually the departure METAR")
    narrative = models.TextField(blank=True)
    narrative_generated_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-departure_time']
        indexes = [models.Index(fields=['user', '-departure_time'])]

    def __str__(self):
        return f"{self.departure_airport} → {self.arrival_airport} ({self.departure_time.date()})"
