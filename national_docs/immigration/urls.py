from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.immigration_dashboard, name='immigration_dashboard'),
    path('fulfiller/', views.fulfillers_list, name='fulfiller'),
    path('fulfiller_detail/<int:id>/', views.fulfiller_detail, name='fulfiller_detail'),
    path('post_locations/', views.post_locations, name='post_locations'),
    path('post-locations/add/', views.add_post_location, name='add_post_location'),
    path('post-locations/edit/<int:id>/', views.edit_post_location, name='edit_post_location'),
    path('post-locations/delete/<int:id>/', views.delete_post_location, name='delete_post_location'),
    path('create_user/', views.create_user, name='create_user'),
    path('create_group/', views.create_group, name='create_group'),
    path('list_officer_users/', views.list_officer_users, name='list_officer_users'),
]