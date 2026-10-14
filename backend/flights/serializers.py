from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers

from . import airports, insights, realism
from .models import Aircraft, Comment, CrewSeat, Flight, Follow, Notification

MAX_PHOTO_BYTES = 10 * 1024 * 1024
ALLOWED_PHOTO_FORMATS = {'JPEG', 'PNG', 'WEBP', 'GIF', 'HEIF', 'MPO'}
TIME_COLUMNS = ('pic_time', 'sic_time', 'dual_received_time', 'night_time', 'instrument_time', 'simulated_instrument_time')


def airport_info(code):
    airport = airports.get(code)
    return airport.as_dict() if airport else None


def check_image(photo):
    if photo is None:
        return photo
    if photo.size > MAX_PHOTO_BYTES:
        raise serializers.ValidationError("Photos must be 10 MB or smaller.")
    image = getattr(photo, 'image', None)
    if image is not None and image.format not in ALLOWED_PHOTO_FORMATS:
        raise serializers.ValidationError("Upload a JPEG, PNG, WebP, GIF or HEIC image.")
    return photo


class AircraftSerializer(serializers.ModelSerializer):
    hours_since_maintenance = serializers.SerializerMethodField()
    maintenance_due = serializers.SerializerMethodField()
    maintenance_forecast = serializers.SerializerMethodField()
    total_flights = serializers.IntegerField(read_only=True, required=False)
    total_time = serializers.DurationField(read_only=True, required=False)

    class Meta:
        model = Aircraft
        fields = (
            'id', 'registration', 'type_code', 'make_model', 'aircraft_class', 'notes',
            'maintenance_interval_hours', 'last_maintenance_at', 'annual_due', 'grounded',
            'hours_since_maintenance', 'maintenance_due', 'maintenance_forecast', 'total_flights', 'total_time',
            'created_at', 'updated_at',
        )
        read_only_fields = ('grounded', 'created_at', 'updated_at')

    def validate_registration(self, value):
        value = value.strip().upper()
        user = self.context['request'].user
        clash = Aircraft.objects.filter(user=user, registration=value)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(f"{value} is already in your fleet.")
        return value

    def validate_type_code(self, value):
        return value.strip().upper()

    def get_hours_since_maintenance(self, obj):
        return round(obj.hours_since_maintenance().total_seconds() / 3600, 1)

    def get_maintenance_due(self, obj):
        return obj.grounded or self.get_hours_since_maintenance(obj) >= obj.maintenance_interval_hours

    def get_maintenance_forecast(self, obj):
        now = timezone.now()
        # The fleet queryset annotates recent_time; a freshly created aircraft doesn't have it.
        if hasattr(obj, 'recent_time'):
            recent = obj.recent_time
        else:
            since = now - timedelta(days=insights.FORECAST_WINDOW_DAYS)
            recent = obj.flights.logged().filter(departure_time__gte=since).aggregate(total=Sum('total_time'))['total']
        return insights.maintenance_forecast(
            self.get_hours_since_maintenance(obj), obj.maintenance_interval_hours,
            insights.hours(recent), obj.annual_due, now.date(),
        )

    def update(self, instance, validated_data):
        aircraft = super().update(instance, validated_data)
        # Keep the denormalised registration on the aircraft's flights in step.
        aircraft.flights.exclude(registration_number=aircraft.registration).update(
            registration_number=aircraft.registration
        )
        return aircraft


class FlightSerializer(serializers.ModelSerializer):
    # Both are worked out from the times and airports when left out.
    total_time = serializers.DurationField(required=False)
    distance = serializers.IntegerField(required=False, min_value=0)
    departure_info = serializers.SerializerMethodField()
    arrival_info = serializers.SerializerMethodField()
    aircraft_type = serializers.CharField(source='aircraft.type_code', read_only=True, default='')
    signature = serializers.SerializerMethodField()

    class Meta:
        model = Flight
        fields = '__all__'
        read_only_fields = ('user', 'aircraft', 'in_flight', 'created_at', 'updated_at')

    def get_departure_info(self, obj):
        return airport_info(obj.departure_airport)

    def get_arrival_info(self, obj):
        return airport_info(obj.arrival_airport)

    def get_signature(self, obj):
        """The latest instructor sign-off, and whether edits since have invalidated it."""
        from instruction.serializers import SignatureSerializer, latest_signature
        signature = latest_signature(obj)
        return SignatureSerializer(signature).data if signature else None

    def _validate_airport(self, value):
        code = value.strip().upper()
        if not airports.get(code):
            raise serializers.ValidationError(f"{code} isn't a known airport code. Use the 4-letter ICAO code, e.g. KJFK.")
        return code

    def validate_departure_airport(self, value):
        return self._validate_airport(value)

    def validate_arrival_airport(self, value):
        return self._validate_airport(value)

    def validate_registration_number(self, value):
        return value.strip().upper()

    def validate_photo(self, photo):
        return check_image(photo)

    def validate(self, data):
        # On a partial update, fall back to the stored values for anything not sent.
        current = lambda field: data.get(field, getattr(self.instance, field, None))
        if self.instance is not None and self.instance.in_flight and not current('is_draft'):
            raise serializers.ValidationError("Land the flight before logging it.")

        departure_time, arrival_time = current('departure_time'), current('arrival_time')
        if departure_time >= arrival_time:
            raise serializers.ValidationError("Departure time must be before arrival time")

        duration = arrival_time - departure_time
        if 'total_time' in data:
            if abs((duration - data['total_time']).total_seconds()) > 60:
                raise serializers.ValidationError("Total time does not match departure and arrival times")
        else:
            data['total_time'] = duration
        total_time = data['total_time']

        for column in TIME_COLUMNS:
            value = current(column) or timedelta(0)
            label = column.replace('_', ' ').replace(' time', '').capitalize()
            if value < timedelta(0):
                raise serializers.ValidationError({column: f"{label} time can't be negative."})
            if value > total_time:
                raise serializers.ValidationError({column: f"{label} time can't be longer than the flight."})

        great_circle = airports.distance_nm(
            airports.get(current('departure_airport')), airports.get(current('arrival_airport'))
        )
        supplied_distance = data.get('distance')
        airports_changed = 'departure_airport' in data or 'arrival_airport' in data
        if not supplied_distance and (self.instance is None or airports_changed or 'distance' in data):
            data['distance'] = great_circle

        unrealistic = realism.problems(
            departure_time=departure_time, arrival_time=arrival_time, total_time=total_time,
            now=timezone.now(), distance=current('distance') or 0,
            # Only the pilot's own figure is worth checking against the great circle; ours is the great circle.
            great_circle=great_circle if supplied_distance else None,
            day_landings=current('day_landings'), night_landings=current('night_landings'),
            approaches=current('approaches'), is_draft=bool(current('is_draft')),
            is_simulator=bool(current('is_simulator')),
        )
        if unrealistic:
            raise serializers.ValidationError(unrealistic)

        registration = current('registration_number')
        # A grounded aircraft can still be planned for; the block applies when a flight enters the logbook.
        entering_logbook = not current('is_draft') and (self.instance is None or self.instance.is_draft)
        if (entering_logbook or self.context.get('live')) and not self.context.get('historical'):
            grounded = Aircraft.objects.filter(
                user=self.context['request'].user, registration=registration, grounded=True
            ).exists()
            if grounded:
                raise serializers.ValidationError({
                    'registration_number': f"{registration} is grounded. Log its maintenance before adding new flights.",
                })
        return data

    def save(self, **kwargs):
        user = kwargs.get('user') or self.instance.user
        registration = self.validated_data.get('registration_number') or self.instance.registration_number
        aircraft, _ = Aircraft.objects.get_or_create(user=user, registration=registration)
        flight = super().save(aircraft=aircraft, **kwargs)
        if flight.aircraft_condition == 'GROUNDED' and not flight.is_draft and not self.context.get('historical'):
            Aircraft.objects.filter(pk=aircraft.pk).update(grounded=True)
        return flight


class PublicFlightSerializer(serializers.ModelSerializer):
    """What anyone can see of a public pilot's flight: no notes, gates or plan."""
    pilot = serializers.CharField(source='user.username', read_only=True)
    departure_info = serializers.SerializerMethodField()
    arrival_info = serializers.SerializerMethodField()
    aircraft_type = serializers.CharField(source='aircraft.type_code', read_only=True, default='')

    class Meta:
        model = Flight
        fields = (
            'id', 'pilot', 'departure_airport', 'arrival_airport', 'departure_time', 'arrival_time',
            'total_time', 'distance', 'registration_number', 'aircraft_type', 'photo',
            'night_time', 'instrument_time', 'day_landings', 'night_landings', 'approaches',
            'cross_country', 'is_simulator', 'departure_info', 'arrival_info',
        )

    def get_departure_info(self, obj):
        return airport_info(obj.departure_airport)

    def get_arrival_info(self, obj):
        return airport_info(obj.arrival_airport)


class FeedFlightSerializer(serializers.ModelSerializer):
    pilot = serializers.CharField(source='user.username', read_only=True)
    pilot_is_public = serializers.BooleanField(source='user.is_public', read_only=True)
    aircraft_type = serializers.CharField(source='aircraft.type_code', read_only=True, default='')
    notes = serializers.SerializerMethodField()
    like_count = serializers.IntegerField(read_only=True)
    liked = serializers.BooleanField(read_only=True)
    comment_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Flight
        fields = (
            'id', 'pilot', 'pilot_is_public', 'departure_airport', 'arrival_airport', 'departure_time',
            'total_time', 'distance', 'registration_number', 'aircraft_type', 'notes', 'like_count', 'liked', 'comment_count',
        )

    def get_notes(self, obj):
        return None if obj.hide_notes else obj.notes


class ReplySerializer(serializers.ModelSerializer):
    author = serializers.CharField(source='author.username', read_only=True, default=None)
    like_count = serializers.SerializerMethodField()
    liked = serializers.SerializerMethodField()
    mine = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ('id', 'author', 'body', 'edited', 'created_at', 'like_count', 'liked', 'mine', 'can_delete')

    def get_like_count(self, obj):
        return getattr(obj, 'like_count', 0)

    def get_liked(self, obj):
        return getattr(obj, 'liked', False)

    def get_mine(self, obj):
        return obj.author_id == self.context['request'].user.pk

    def get_can_delete(self, obj):
        return obj.author_id is not None and (self.get_mine(obj) or obj.flight.user_id == self.context['request'].user.pk)


class CommentSerializer(ReplySerializer):
    replies = ReplySerializer(many=True, read_only=True)

    class Meta(ReplySerializer.Meta):
        fields = ReplySerializer.Meta.fields + ('replies',)


class NotificationSerializer(serializers.ModelSerializer):
    kind = serializers.SerializerMethodField()
    actor = serializers.SerializerMethodField()
    flight = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ('id', 'kind', 'actor', 'flight', 'read', 'created_at')

    def get_kind(self, obj):
        if obj.follow:
            if obj.recipient_id != obj.follow.pilot_id:
                return 'approved'
            return 'follow_request' if obj.follow.status == Follow.PENDING else 'follow'
        if obj.comment:
            return 'reply' if obj.comment.parent and obj.comment.parent.author_id == obj.recipient_id else 'comment'
        return 'comment_like' if obj.like.comment_id else 'flight_like'

    def get_actor(self, obj):
        if obj.follow:
            return (obj.follow.follower if obj.recipient_id == obj.follow.pilot_id else obj.follow.pilot).username
        return (obj.comment.author if obj.comment else obj.like.user).username

    def get_flight(self, obj):
        flight = obj.comment.flight if obj.comment else obj.like.flight if obj.like else None
        if flight is None:
            return None
        route = f'{flight.departure_airport} → {flight.arrival_airport}'
        return {'id': flight.id, 'route': route, 'mine': flight.user_id == obj.recipient_id}


class CrewSeatSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='pilot.username', read_only=True)
    avatar = serializers.SerializerMethodField()
    is_me = serializers.SerializerMethodField()

    class Meta:
        model = CrewSeat
        fields = ('id', 'username', 'avatar', 'role', 'status', 'is_me')

    def get_avatar(self, obj):
        if not obj.pilot.avatar or obj.status in (CrewSeat.PENDING, CrewSeat.DECLINED):
            return None
        return self.context['request'].build_absolute_uri(obj.pilot.avatar.url)

    def get_is_me(self, obj):
        return obj.pilot_id == self.context['request'].user.pk


class CrewInviteSerializer(serializers.ModelSerializer):
    invited_by = serializers.CharField(source='flight.user.username', read_only=True)
    flight = PublicFlightSerializer(read_only=True)

    class Meta:
        model = CrewSeat
        fields = ('id', 'role', 'invited_by', 'flight', 'created_at')


class CrewRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=CrewSeat.ROLE_CHOICES)


class AddCrewSerializer(CrewRoleSerializer):
    username = serializers.CharField(max_length=150)


class StartFlightSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=CrewSeat.ROLE_CHOICES, default=CrewSeat.PIC)
    departure_airport = serializers.CharField(max_length=4)
    arrival_airport = serializers.CharField(max_length=4)
    registration_number = serializers.CharField(max_length=10)
    ete_minutes = serializers.IntegerField(min_value=1, max_value=realism.MAX_FLIGHT_HOURS * 60)
    crew = AddCrewSerializer(many=True, required=False, max_length=8)
    hidden_from_followers = serializers.BooleanField(default=False)


class LandSerializer(serializers.Serializer):
    arrival_time = serializers.DateTimeField(required=False)


class LiveFlightSerializer(serializers.ModelSerializer):
    pilot = serializers.CharField(source='user.username', read_only=True)
    eta = serializers.DateTimeField(source='arrival_time', read_only=True)
    is_mine = serializers.SerializerMethodField()
    unconfirmed = serializers.SerializerMethodField()

    class Meta:
        model = Flight
        fields = ('id', 'pilot', 'departure_airport', 'arrival_airport', 'registration_number', 'departure_time', 'eta', 'is_mine', 'unconfirmed')

    def get_is_mine(self, obj):
        return obj.user_id == self.context['request'].user.pk

    def get_unconfirmed(self, obj):
        from .live import unconfirmed
        return unconfirmed(obj)
