from django.utils import timezone
from rest_framework import serializers

from flights.serializers import TIME_COLUMNS, airport_info
from .endorsements import KINDS
from .models import SIGNED_FIELDS, Endorsement, InstructorLink, Signature, attestation


DURATION_FIELDS = {'total_time', *TIME_COLUMNS}


def display_name(user):
    return user.get_full_name() or user.username


class WithdrawableMixin(serializers.Serializer):
    """`withdrawable` is true for the instructor who gave it, until they withdraw it."""
    withdrawable = serializers.SerializerMethodField()

    def get_withdrawable(self, obj):
        request = self.context.get('request')
        return bool(request and obj.instructor_id == request.user.pk and not obj.withdrawn_at)


class SignatureSerializer(WithdrawableMixin, serializers.ModelSerializer):
    """A signature as the student or instructor sees it, with whether it still holds."""
    status = serializers.SerializerMethodField()
    changed_fields = serializers.SerializerMethodField()

    class Meta:
        model = Signature
        fields = (
            'id', 'instructor_name', 'certificate_number', 'certificate_expires', 'statement', 'remarks',
            'signed_at', 'status', 'changed_fields', 'withdrawn_at', 'withdrawal_reason', 'withdrawable',
        )

    def get_status(self, obj):
        return obj.status()

    def get_changed_fields(self, obj):
        return obj.changed_fields()


def latest_signature(flight):
    """The flight's newest signature. Uses prefetched signatures when the queryset has them."""
    signatures = list(flight.signatures.all())
    return signatures[0] if signatures else None


class StudentFlightSerializer(serializers.Serializer):
    """What an instructor sees of a student's flight: exactly the fields they would sign."""
    id = serializers.IntegerField()
    departure_info = serializers.SerializerMethodField()
    arrival_info = serializers.SerializerMethodField()
    aircraft_type = serializers.CharField(source='aircraft.type_code', default='')
    signature = serializers.SerializerMethodField()
    statement = serializers.SerializerMethodField()

    def get_fields(self):
        fields = super().get_fields()
        for name in SIGNED_FIELDS:
            # Durations render as "HH:MM:SS", the same as on the pilot's own flights.
            fields[name] = serializers.DurationField(read_only=True) if name in DURATION_FIELDS else serializers.ReadOnlyField()
        return fields

    def get_departure_info(self, obj):
        return airport_info(obj.departure_airport)

    def get_arrival_info(self, obj):
        return airport_info(obj.arrival_airport)

    def get_signature(self, obj):
        signature = latest_signature(obj)
        return SignatureSerializer(signature, context=self.context).data if signature else None

    def get_statement(self, obj):
        """What signing would attest to, so the instructor reads it first."""
        return attestation(obj, self.context['request'].user)


class PartySerializer(serializers.Serializer):
    username = serializers.CharField()
    name = serializers.SerializerMethodField()

    def get_name(self, obj):
        return display_name(obj)


class InstructorLinkSerializer(serializers.ModelSerializer):
    """A link from the requesting pilot's side: their role in it and the other party."""
    role = serializers.SerializerMethodField()
    other = serializers.SerializerMethodField()
    awaiting_my_response = serializers.SerializerMethodField()
    unsigned_flights = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = InstructorLink
        fields = ('id', 'status', 'role', 'other', 'awaiting_my_response', 'unsigned_flights', 'created_at', 'accepted_at')

    def _me(self):
        return self.context['request'].user

    def get_role(self, obj):
        return 'student' if obj.student_id == self._me().pk else 'instructor'

    def get_other(self, obj):
        other = obj.instructor if obj.student_id == self._me().pk else obj.student
        data = PartySerializer(other).data
        if other == obj.instructor:
            data['certificate_number'] = other.instructor_certificate_number
        return data

    def get_awaiting_my_response(self, obj):
        return obj.status == InstructorLink.PENDING and obj.invited_by_id != self._me().pk


class InviteSerializer(serializers.Serializer):
    invitee = serializers.CharField(help_text="Username or email of the other pilot")
    # The role the invitee will have: "instructor" asks them to be my instructor.
    invitee_role = serializers.ChoiceField(choices=['instructor', 'student'])


class ConfirmPasswordSerializer(serializers.Serializer):
    """Signing, endorsing and withdrawing are deliberate: re-enter the password, as for deleting an account."""
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    def validate(self, attrs):
        user = self.context['request'].user
        if user.has_usable_password() and not user.check_password(attrs.get('password', '')):
            raise serializers.ValidationError({'password': "Your password is incorrect."})
        return attrs


class AgreeSerializer(ConfirmPasswordSerializer):
    agree = serializers.BooleanField()

    def validate_agree(self, value):
        if not value:
            raise serializers.ValidationError("Confirm the statement to sign.")
        return value


class SignSerializer(AgreeSerializer):
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class WithdrawSerializer(ConfirmPasswordSerializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class EndorsementSerializer(WithdrawableMixin, serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    regulation = serializers.SerializerMethodField()
    student = serializers.SerializerMethodField()

    class Meta:
        model = Endorsement
        fields = (
            'id', 'kind', 'title', 'regulation', 'text', 'aircraft', 'student', 'instructor_name', 'certificate_number',
            'certificate_expires', 'given_on', 'expires_on', 'signed_at', 'status', 'withdrawn_at', 'withdrawal_reason',
            'withdrawable',
        )

    def get_status(self, obj):
        return obj.status(timezone.localdate())

    def get_regulation(self, obj):
        return KINDS.get(obj.kind, {}).get('regulation', '')

    def get_student(self, obj):
        return display_name(obj.student)


class GiveEndorsementSerializer(AgreeSerializer):
    kind = serializers.ChoiceField(choices=list(KINDS))
    title = serializers.CharField(required=False, allow_blank=True, max_length=120)
    text = serializers.CharField(max_length=2000)
    aircraft = serializers.CharField(required=False, allow_blank=True, max_length=60)
    given_on = serializers.DateField(required=False)

    def validate_given_on(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError("An endorsement can't be dated in the future.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        info = KINDS[attrs['kind']]
        attrs['title'] = (attrs.get('title') or '').strip() or info['title']
        if not attrs['title']:
            raise serializers.ValidationError({'title': "Give this endorsement a title."})
        attrs['aircraft'] = (attrs.get('aircraft') or '').strip()
        if info.get('needs_aircraft') and not attrs['aircraft']:
            raise serializers.ValidationError({'aircraft': "This endorsement names an aircraft make and model."})
        attrs['text'] = attrs['text'].strip()
        if '{' in attrs['text'] or '}' in attrs['text']:
            raise serializers.ValidationError({'text': "Fill in the blanks in braces before signing."})
        attrs.setdefault('given_on', timezone.localdate())
        return attrs
