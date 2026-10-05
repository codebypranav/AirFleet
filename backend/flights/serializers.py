from datetime import timedelta

from rest_framework import serializers

from . import airports
from .models import Aircraft, Flight

MAX_PHOTO_BYTES = 10 * 1024 * 1024
ALLOWED_PHOTO_FORMATS = {'JPEG', 'PNG', 'WEBP', 'GIF', 'HEIF', 'MPO'}
TIME_COLUMNS = ('pic_time', 'sic_time', 'dual_received_time', 'night_time', 'instrument_time', 'simulated_instrument_time')


def airport_info(code):
    airport = airports.get(code)
    return airport.as_dict() if airport else None


class AircraftSerializer(serializers.ModelSerializer):
    hours_since_maintenance = serializers.SerializerMethodField()
    maintenance_due = serializers.SerializerMethodField()
    total_flights = serializers.IntegerField(read_only=True, required=False)
    total_time = serializers.DurationField(read_only=True, required=False)

    class Meta:
        model = Aircraft
        fields = (
            'id', 'registration', 'type_code', 'make_model', 'aircraft_class', 'notes',
            'maintenance_interval_hours', 'last_maintenance_at', 'annual_due', 'grounded',
            'hours_since_maintenance', 'maintenance_due', 'total_flights', 'total_time',
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

    class Meta:
        model = Flight
        fields = '__all__'
        read_only_fields = ('user', 'aircraft', 'narrative', 'narrative_generated_at', 'created_at', 'updated_at')

    def get_departure_info(self, obj):
        return airport_info(obj.departure_airport)

    def get_arrival_info(self, obj):
        return airport_info(obj.arrival_airport)

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
        if photo is None:
            return photo
        if photo.size > MAX_PHOTO_BYTES:
            raise serializers.ValidationError("Photos must be 10 MB or smaller.")
        image = getattr(photo, 'image', None)
        if image is not None and image.format not in ALLOWED_PHOTO_FORMATS:
            raise serializers.ValidationError("Upload a JPEG, PNG, WebP, GIF or HEIC image.")
        return photo

    def validate(self, data):
        # On a partial update, fall back to the stored values for anything not sent.
        current = lambda field: data.get(field, getattr(self.instance, field, None))

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
            if (current(column) or timedelta(0)) > total_time:
                label = column.replace('_', ' ').replace(' time', '')
                raise serializers.ValidationError({column: f"{label.capitalize()} time can't be longer than the flight."})

        airports_changed = 'departure_airport' in data or 'arrival_airport' in data
        if not data.get('distance') and (self.instance is None or airports_changed or 'distance' in data):
            data['distance'] = airports.distance_nm(
                airports.get(current('departure_airport')), airports.get(current('arrival_airport'))
            )

        registration = current('registration_number')
        if self.instance is None and not self.context.get('historical'):
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
        if flight.aircraft_condition == 'GROUNDED' and not self.context.get('historical'):
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
            'total_time', 'distance', 'registration_number', 'aircraft_type', 'photo', 'narrative',
            'night_time', 'instrument_time', 'day_landings', 'night_landings', 'approaches',
            'cross_country', 'is_simulator', 'departure_info', 'arrival_info',
        )

    def get_departure_info(self, obj):
        return airport_info(obj.departure_airport)

    def get_arrival_info(self, obj):
        return airport_info(obj.arrival_airport)
