from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.immigration_dashboard, name='immigration_dashboard'),
    path('fulfiller/', views.fulfillers_list, name='fulfiller'),
    path('fulfiller_detail/<int:id>/', views.fulfiller_detail, name='fulfiller_detail'),
]