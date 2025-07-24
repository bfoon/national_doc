from django.urls import path
from . import views

urlpatterns = [
    path("token-management/", views.token_management_view, name="token_management"),
    path('generate-token/', views.generate_token, name='generate_token'),
    path('verify-token/', views.verify_token, name='verify_token'),
    path('complete-service/<int:token_id>/', views.complete_service, name='complete_service'),
    path('token-logs/<str:token_value>/', views.token_logs_partial_view, name='token_logs_partial'),
]
