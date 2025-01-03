from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('login/', views.login_page, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout'),  # Add this line
    path('profile/', views.profile_view, name='profile_view'),

    path('send-edit-profile-otp/', views.send_edit_profile_otp, name='send_edit_profile_otp'),
    path('verify-edit-profile-otp/', views.verify_edit_profile_otp, name='verify_edit_profile_otp'),
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

    path('chat/', views.chat_with_support, name='chat_with_support'),
    path('faqs/', views.faq_list, name='faq_list'),
    path('manage_appointments/', views.manage_appointments, name='manage_appointments'),

    path('application/<int:application_id>/extend-or-reprint/', views.apply_extend_or_reprint,
         name='apply_extend_or_reprint'),
    path('verify-token/', views.verify_token, name='verify_token'),
    path('request-certificate/', views.request_certificate, name='request_certificate'),
]
