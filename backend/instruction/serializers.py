from rest_framework import serializers

from flights.serializers import airport_info
from .models import SIGNED_FIELDS, InstructorLink, Signature, attestation


def display_name(user):
    return user.get_full_name() or user.username


class SignatureSerializer(serializers.ModelSerializer):
    """A signature as the student or instructor sees it, with whether it still holds."""
    status = serializers.SerializerMethodField()
    changed_fields = serializers.SerializerMethodField()

    class Meta:
        model = Signature
        fields = (
            'id', 'instructor_name', 'certificate_number', 'certificate_expires', 'statement', 'remarks',
            'signed_at', 'status', 'changed_fields',
        )

    def get_status(self, obj):
        return 'valid' if obj.is_valid() else 'invalidated'

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
            fields[name] = serializers.ReadOnlyField()
        return fields

    def get_departure_info(self, obj):
        return airport_info(obj.departure_airport)

    def get_arrival_info(self, obj):
        return airport_info(obj.arrival_airport)

    def get_signature(self, obj):
        signature = latest_signature(obj)
        return SignatureSerializer(signature).data if signature else None

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


class SignSerializer(serializers.Serializer):
    remarks = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    agree = serializers.BooleanField()
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    def validate_agree(self, value):
        if not value:
            raise serializers.ValidationError("Confirm the statement to sign.")
        return value

    def validate(self, attrs):
        # Signing is deliberate: re-enter the password, as for deleting an account.
        user = self.context['request'].user
        if user.has_usable_password() and not user.check_password(attrs.get('password', '')):
            raise serializers.ValidationError({'password': "Your password is incorrect."})
        return attrs
