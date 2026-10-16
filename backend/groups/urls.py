from django.urls import path

from . import views

urlpatterns = [
    path('', views.groups, name='groups'),
    path('<slug:slug>/', views.group, name='group'),
    path('<slug:slug>/members/', views.members, name='group-members'),
    path('<slug:slug>/members/<int:pk>/', views.member, name='group-member'),
]
