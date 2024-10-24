from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('login/', views.login_page, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout'),  # Add this line
    path('profile/', views.profile_view, name='profile_view'),

    path('edit-profile/', views.edit_profile, name='edit_profile'),

    path('dashboard/', views.dashboard, name='dashboard'),

    path('apply/national-id/', views.apply_national_id, name='apply_national_id'),
    # path('view-national-id/<int:id>/', views.view_national_id, name='view_national_id'),

    path('apply-resident-permit/', views.apply_resident_permit, name='apply_resident_permit'),
    # path('view-resident-permit/<int:id>/', views.view_resident_permit, name='view_resident_permit'),

    path('apply-work-permit/', views.apply_work_permit, name='apply_work_permit'),
    # path('view-work-permit/<int:id>/', views.view_work_permit, name='view_work_permit'),

    path('fetch-application-details/', views.fetch_application_details, name='fetch_application_details'),
    path('cancel-application/', views.cancel_application, name='cancel_application'),

    path('upload-document/<int:id>/', views.upload_document, name='upload_document'),
]
