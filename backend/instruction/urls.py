from django.urls import path

from . import views

urlpatterns = [
    path('links/', views.LinksView.as_view(), name='instructor-links'),
    path('links/<int:pk>/', views.end_link, name='instructor-link-end'),
    path('links/<int:pk>/accept/', views.accept_link, name='instructor-link-accept'),
    path('links/<int:pk>/flights/', views.student_flights, name='student-flights'),
    path('flights/<int:pk>/sign/', views.sign_flight, name='sign-flight'),
]
