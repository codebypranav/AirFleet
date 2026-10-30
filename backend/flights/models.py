from datetime import timedelta

from django.conf import settings
from django.core.validators import MinLengthValidator
from django.db import models
from django.db.models import Q, Sum


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

    def followed_by(self, viewer):
        pilots = Follow.objects.filter(follower=viewer, status=Follow.APPROVED).exclude(blocked_with(viewer, 'pilot')).values('pilot')
        return self.filter(user__in=pilots, user__is_active=True, hidden_from_followers=False)

    def open_to(self, viewer):
        return self.logged().filter(Q(user=viewer) | Q(pk__in=Flight.objects.followed_by(viewer).values('pk')))

    def shared(self):
        return self.logged().filter(user__is_public=True, user__is_active=True)


def blocked_with(user, field):
    return (
        Q(**{f'{field}__in': Block.objects.filter(blocked=user).values('blocker')})
        | Q(**{f'{field}__in': Block.objects.filter(blocker=user).values('blocked')})
    )


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
    in_flight = models.BooleanField(default=False)
    hidden_from_followers = models.BooleanField(default=False)
    hide_notes = models.BooleanField(default=True)

    MILESTONE_CHOICES = [
        ('first_solo', 'First solo'),
        ('first_solo_xc', 'First solo cross-country'),
        ('checkride_private', 'Private pilot checkride passed'),
        ('checkride_instrument', 'Instrument rating checkride passed'),
        ('checkride_commercial', 'Commercial pilot checkride passed'),
        ('checkride_cfi', 'Flight instructor checkride passed'),
        ('checkride_atp', 'ATP checkride passed'),
    ]
    milestone = models.CharField(max_length=24, choices=MILESTONE_CHOICES, blank=True, default='')

    weather_conditions = models.TextField(blank=True, help_text="Usually the departure METAR")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-departure_time']
        indexes = [models.Index(fields=['user', '-departure_time'])]
        constraints = [
            models.UniqueConstraint(fields=['user'], condition=models.Q(in_flight=True), name='one_live_flight_per_pilot'),
            models.UniqueConstraint(fields=['user', 'milestone'], condition=~models.Q(milestone=''), name='one_flight_per_milestone'),
        ]

    def __str__(self):
        return f"{self.departure_airport} → {self.arrival_airport} ({self.departure_time.date()})"


class CrewSeat(models.Model):
    PIC, SIC = 'PIC', 'SIC'
    ROLE_CHOICES = [(PIC, 'Captain'), (SIC, 'First officer')]
    LOGGER, PENDING, ACCEPTED, DECLINED = 'LOGGER', 'PENDING', 'ACCEPTED', 'DECLINED'
    STATUS_CHOICES = [(LOGGER, 'Logger'), (PENDING, 'Pending'), (ACCEPTED, 'Accepted'), (DECLINED, 'Declined')]

    crew = models.UUIDField(db_index=True)
    pilot = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='crew_seats')
    flight = models.ForeignKey(Flight, on_delete=models.CASCADE, related_name='crew_seats')
    role = models.CharField(max_length=3, choices=ROLE_CHOICES)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['flight'], condition=models.Q(status__in=['LOGGER', 'ACCEPTED']), name='one_crew_per_flight',
            ),
            models.UniqueConstraint(
                fields=['crew', 'pilot'], condition=~models.Q(status='DECLINED'), name='one_open_seat_per_pilot',
            ),
        ]

    def __str__(self):
        return f"{self.pilot} as {self.role} ({self.get_status_display()})"


class Follow(models.Model):
    PENDING, APPROVED = 'PENDING', 'APPROVED'
    STATUS_CHOICES = [(PENDING, 'Pending'), (APPROVED, 'Approved')]

    follower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='following')
    pilot = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='followers')
    status = models.CharField(max_length=8, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['follower', 'pilot'], name='one_follow_per_pair'),
            models.CheckConstraint(condition=~models.Q(follower=models.F('pilot')), name='no_self_follow'),
        ]

    def __str__(self):
        return f"{self.follower} follows {self.pilot} ({self.get_status_display()})"


class Block(models.Model):
    blocker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='blocks')
    blocked = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['blocker', 'blocked'], name='one_block_per_pair'),
            models.CheckConstraint(condition=~models.Q(blocker=models.F('blocked')), name='no_self_block'),
        ]

    def __str__(self):
        return f"{self.blocker} blocked {self.blocked}"


class Comment(models.Model):
    flight = models.ForeignKey(Flight, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    body = models.CharField(max_length=500, blank=True)
    edited = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(author__isnull=True, body='') | (models.Q(author__isnull=False) & ~models.Q(body='')),
                name='placeholder_is_empty',
            ),
        ]


class Like(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='likes')
    flight = models.ForeignKey(Flight, on_delete=models.CASCADE, related_name='likes')
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'flight'], condition=models.Q(comment__isnull=True), name='one_flight_like'),
            models.UniqueConstraint(fields=['user', 'comment'], name='one_comment_like'),
        ]


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    follow = models.ForeignKey(Follow, on_delete=models.CASCADE, null=True, related_name='+')
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, related_name='+')
    like = models.ForeignKey(Like, on_delete=models.CASCADE, null=True, related_name='+')
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        indexes = [models.Index(fields=['recipient', 'read'])]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(follow__isnull=False, comment=None, like=None)
                    | models.Q(follow=None, comment__isnull=False, like=None)
                    | models.Q(follow=None, comment=None, like__isnull=False)
                ),
                name='one_cause',
            ),
            models.UniqueConstraint(fields=['recipient', 'follow'], name='one_notification_per_follow'),
            models.UniqueConstraint(fields=['recipient', 'comment'], name='one_notification_per_comment'),
            models.UniqueConstraint(fields=['recipient', 'like'], name='one_notification_per_like'),
        ]
