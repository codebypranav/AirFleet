from django.urls import path

from . import views

urlpatterns = [
    path('flights/', views.FlightListView.as_view(), name='flight-list'),
    path('flights/export/', views.export_flights, name='flight-export'),
    path('flights/import/', views.ImportFlightsView.as_view(), name='flight-import'),
    path('flights/from-plan/', views.FlightPlanView.as_view(), name='flight-from-plan'),
    path('flights/<int:pk>/', views.FlightDetailView.as_view(), name='flight-detail'),
    path('generate-narrative/', views.generate_narrative, name='generate-narrative'),
    path('stats/', views.stats, name='stats'),
    path('stats/routes/', views.routes, name='routes'),
    path('currency/', views.currency, name='currency'),
    path('achievements/', views.achievements, name='achievements'),
    path('aircraft/', views.AircraftListView.as_view(), name='aircraft-list'),
    path('aircraft/<int:pk>/', views.AircraftDetailView.as_view(), name='aircraft-detail'),
    path('aircraft/<int:pk>/maintenance/', views.log_maintenance, name='aircraft-maintenance'),
    path('airports/', views.airport_search, name='airport-search'),
    path('airports/<str:code>/', views.airport_detail, name='airport-detail'),
    path('weather/', views.weather, name='weather'),
    path('simbrief/', views.simbrief, name='simbrief'),
    path('public/flights/<int:pk>/', views.public_flight, name='public-flight'),
    path('pilots/<str:username>/', views.public_pilot, name='public-pilot'),
]
