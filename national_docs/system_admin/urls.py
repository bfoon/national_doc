# urls.py in admin_app
from django.urls import path
from . import views

urlpatterns = [
    path('officer_profiles/', views.officer_profile_list, name='officer_profile_list'),

    path('profile/<str:user_id>/view/', views.view_profile, name='view_profile'),
    path('profile/<str:user_id>/edit/', views.edit_profile, name='edit_profile'),
    path('profile/<str:user_id>/delete/', views.delete_profile, name='delete_profile'),

    path('officer_profiles/add/', views.add_officer_profile, name='add_officer_profile'),
    path('officer_profiles/<int:pk>/edit/', views.edit_officer_profile, name='edit_officer_profile'),
]
