import hashlib
import json
from datetime import timezone as dt_timezone

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from flights.models import Flight

# The logbook entry an instructor vouches for. Editing any of these after signing
# invalidates the signature; notes, photos and weather can change freely.
SIGNED_FIELDS = (
    'departure_airport', 'arrival_airport', 'departure_time', 'arrival_time', 'total_time',
    'registration_number', 'pic_time', 'sic_time', 'dual_received_time', 'night_time',
    'instrument_time', 'simulated_instrument_time', 'day_landings', 'night_landings',
    'approaches', 'cross_country', 'is_simulator',
)


def flight_snapshot(flight, fields=SIGNED_FIELDS):
    """The signed fields as plain JSON values. Includes the flight and pilot ids so a
    signature can't be carried over to another entry."""
    snapshot = {'flight_id': flight.pk, 'pilot_id': flight.user_id}
    for field in fields:
        if field in snapshot:
            continue
        value = getattr(flight, field)
        if hasattr(value, 'astimezone'):
            value = value.astimezone(dt_timezone.utc).isoformat()
        elif hasattr(value, 'total_seconds'):
            value = int(value.total_seconds())
        snapshot[field] = value
    return snapshot


def snapshot_hash(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def attestation(flight, instructor):
    """The statement an instructor agrees to when signing, worded in their voice."""
    minutes = int(flight.dual_received_time.total_seconds()) // 60
    student = flight.user.get_full_name() or flight.user.username
    teacher = instructor.get_full_name() or instructor.username
    return (
        f"I, {teacher}, certificate {instructor.instructor_certificate_number}, gave {student} "
        f"{minutes // 60}:{minutes % 60:02d} of flight instruction on {flight.departure_time:%Y-%m-%d} "
        f"in {flight.registration_number}, {flight.departure_airport} to {flight.arrival_airport}, "
        f"and this logbook entry is accurate."
    )


class InstructorLink(models.Model):
    """A student and their instructor. Either side invites; the other accepts."""
    PENDING, ACTIVE, ENDED = 'PENDING', 'ACTIVE', 'ENDED'
    STATUS_CHOICES = [(PENDING, 'Pending'), (ACTIVE, 'Active'), (ENDED, 'Ended')]

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='instructor_links')
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='student_links')
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'instructor'], condition=~Q(status='ENDED'), name='one_open_link_per_pair',
            ),
            models.CheckConstraint(condition=~Q(student=F('instructor')), name='no_self_instruction'),
        ]

    def __str__(self):
        return f"{self.instructor} instructs {self.student} ({self.get_status_display()})"

    @property
    def invitee(self):
        return self.instructor if self.invited_by_id == self.student_id else self.student


class Signature(models.Model):
    """An instructor's sign-off of one flight, with the entry as it stood when they signed.

    This is AirFleet's "instructor-verified" mark. It is not presented as a signature that
    meets 14 CFR 61.51(h) or the FAA's electronic signature guidance (AC 120-78A).
    """
    flight = models.ForeignKey(Flight, on_delete=models.CASCADE, related_name='signatures')
    # Kept when the instructor deletes their account: the student's record still shows who signed.
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='signatures_given',
    )
    instructor_name = models.CharField(max_length=300)
    certificate_number = models.CharField(max_length=20)
    certificate_expires = models.DateField(null=True, blank=True)
    statement = models.TextField(help_text="The attestation the instructor agreed to")
    remarks = models.TextField(blank=True)
    flight_snapshot = models.JSONField()
    flight_hash = models.CharField(max_length=64)
    signed_at = models.DateTimeField(auto_now_add=True)
    # The instructor can take a signature back. The record stays, marked withdrawn.
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    withdrawal_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-signed_at', '-pk']

    def __str__(self):
        return f"{self.instructor_name} signed flight {self.flight_id}"

    def status(self, flight=None):
        if self.withdrawn_at:
            return 'withdrawn'
        return 'valid' if self.is_valid(flight) else 'invalidated'

    def holds(self, flight=None):
        """Not withdrawn, and the flight still matches what was signed."""
        return self.status(flight) == 'valid'

    def changed_fields(self, flight=None):
        """Signed fields whose value differs from the snapshot. Empty while the signature holds."""
        current = flight_snapshot(flight or self.flight, fields=self.flight_snapshot.keys())
        return sorted(k for k in self.flight_snapshot if current.get(k) != self.flight_snapshot[k])

    def is_valid(self, flight=None):
        current = flight_snapshot(flight or self.flight, fields=self.flight_snapshot.keys())
        return snapshot_hash(current) == self.flight_hash


class Endorsement(models.Model):
    """An instructor's endorsement of a student, such as solo or a practical test.

    The text is the instructor's: AirFleet offers a starting draft per kind, which they edit before signing.
    """
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='endorsements_received')
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='endorsements_given',
    )
    instructor_name = models.CharField(max_length=300)
    certificate_number = models.CharField(max_length=20)
    certificate_expires = models.DateField(null=True, blank=True)
    kind = models.CharField(max_length=30)
    title = models.CharField(max_length=120)
    text = models.TextField()
    aircraft = models.CharField(max_length=60, blank=True, help_text="Make and model, where the endorsement names one")
    given_on = models.DateField()
    expires_on = models.DateField(null=True, blank=True)
    signed_at = models.DateTimeField(auto_now_add=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    withdrawal_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-given_on', '-signed_at', '-pk']

    def __str__(self):
        return f"{self.title} for {self.student} by {self.instructor_name}"

    def status(self, today):
        if self.withdrawn_at:
            return 'withdrawn'
        if self.expires_on and self.expires_on < today:
            return 'expired'
        return 'current'
