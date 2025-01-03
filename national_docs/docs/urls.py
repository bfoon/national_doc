from django.urls import path
from . import views

urlpatterns = [
    # Landing and Authentication
    path('', views.landing_page, name='landing_page'),
    path('login/', views.login_page, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.logout_view, name='logout'),

    # Profile Management
    path('profile/', views.profile_view, name='profile_view'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('send-edit-profile-otp/', views.send_edit_profile_otp, name='send_edit_profile_otp'),
    path('verify-edit-profile-otp/', views.verify_edit_profile_otp, name='verify_edit_profile_otp'),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Applications
    path('apply/national-id/', views.apply_national_id, name='apply_national_id'),
    path('apply-resident-permit/', views.apply_resident_permit, name='apply_resident_permit'),
    path('apply-work-permit/', views.apply_work_permit, name='apply_work_permit'),
    path('fetch-application-details/', views.fetch_application_details, name='fetch_application_details'),
    path('cancel-application/', views.cancel_application, name='cancel_application'),
    path('application/<int:application_id>/extend-or-reprint/', views.apply_extend_or_reprint, name='apply_extend_or_reprint'),

    # Document Uploads
    path('upload-document/<int:id>/', views.upload_document, name='upload_document'),

    # Chat and Support
    path('chat/', views.chat_with_support, name='chat_with_support'),
    path('faqs/', views.faq_list, name='faq_list'),

    # Appointment Management
    path('manage_appointments/', views.manage_appointments, name='manage_appointments'),

    # Token Verification
    path('verify-token/', views.verify_token, name='verify_token'),

    # Certification
    path('certificates/', views.CertificationView.as_view(), name='certificate_list'),
    path('certificates/create/', views.create_certification, name='certificate_create'),
    path('certificates/<int:pk>/', views.CertificationDetailView.as_view(), name='certificate_detail'),
    path('certificates/download/<int:certificate_id>/', views.download_certificate, name='download_certificate'),
    path('certificates/track/<int:pk>/', views.track_certificate, name='track_certificate'),
    path('certificates/appeal/<int:pk>/', views.appeal_certificate, name='appeal_certificate'),
    path('certificates/update-status/<int:pk>/', views.update_certification_status, name='update_status'),
]
