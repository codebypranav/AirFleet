from django.contrib import admin

from .models import Aircraft, Flight


@admin.register(Flight)
class FlightAdmin(admin.ModelAdmin):
    list_display = ('departure_airport', 'arrival_airport', 'departure_time', 'total_time', 'registration_number', 'user')
    list_filter = ('aircraft_condition', 'is_simulator', 'cross_country')
    search_fields = ('departure_airport', 'arrival_airport', 'registration_number', 'user__username')
    raw_id_fields = ('user', 'aircraft')
    date_hierarchy = 'departure_time'


@admin.register(Aircraft)
class AircraftAdmin(admin.ModelAdmin):
    list_display = ('registration', 'type_code', 'aircraft_class', 'grounded', 'user')
    list_filter = ('aircraft_class', 'grounded')
    search_fields = ('registration', 'type_code', 'user__username')
    raw_id_fields = ('user',)
