from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('dashboard/', views.immigration_dashboard, name='immigration_dashboard'),

    # Fulfillers
    path('fulfiller/', views.fulfillers_list, name='fulfiller'),
    path('fulfiller/search/', views.filler_search, name='filler_search'),
    path('fulfiller/<int:fulfiller_id>/send-note/', views.send_note_to_requester, name='send_note_to_requester'),
    path('fulfiller_detail/<int:id>/', views.fulfiller_detail, name='fulfiller_detail'),

    # Post Locations
    path('post_locations/', views.post_locations, name='post_locations'),
    path('post-locations/add/', views.add_post_location, name='add_post_location'),
    path('post-locations/edit/<int:id>/', views.edit_post_location, name='edit_post_location'),
    path('post-locations/delete/<int:id>/', views.delete_post_location, name='delete_post_location'),

    # User Management
    path('create_user/', views.create_user, name='create_user'),
    path('edit_user/<int:user_id>/', views.edit_user, name='edit_user'),
    path('delete_user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('list_officer_users/', views.list_officer_users, name='list_officer_users'),

    # Group Management
    path('create_group/', views.create_group, name='create_group'),
    path('edit_group/<int:group_id>/', views.edit_group, name='edit_group'),
    path('delete_group/<int:group_id>/', views.delete_group, name='delete_group'),

    # Interview Slots
    path('available_slots/', views.available_slots, name='available_slots'),

    # Interviews
    path('interviews/', views.interview_list, name='interview_list'),
    path('interview/<int:interview_id>/', views.interview_view, name='interview_view'),
    path('queue-info/', views.queue_info, name='queue_info'),
    path('fetch-interview-queue/', views.fetch_interview_queue, name='fetch_interview_queue'),
    path('start-interview/', views.start_interview, name='start_interview'),

    # To-Do List
    path('todos/', views.todo_list, name='todo_list'),
    path('todos/<int:todo_id>/', views.todo_detail, name='todo_detail'),
    path('todos/<int:todo_id>/approve/', views.approve_todo, name='approve_todo'),
    path('todo/reject/<int:todo_id>/', views.reject_todo, name='reject_todo'),
    path('todo/<int:todo_id>/receipt-pdf/', views.generate_todo_receipt_pdf, name='todo_receipt_pdf'),

    # Boots
    path('boots/', views.boot_list, name='boot_list'),
    path('boots/add/', views.add_boot, name='add_boot'),
    path('boots/change-assignment/<int:boot_id>/', views.change_assignment, name='change_assignment'),

    # Export Functions
    path('export/pdf/', views.export_pdf, name='export_pdf'),
    path('export/excel/', views.export_excel, name='export_excel'),
    path('export/csv/', views.export_csv, name='export_csv'),
    path('export/webpage/', views.export_webpage, name='export_webpage'),

    # Notifications
    path('notifications/mark-as-read/<int:notification_id>/', views.mark_notification_as_read, name='mark_notification_as_read'),

    path('support_desk/', views.support_desk, name='support_desk'),
    path('add_faq/', views.add_faq, name='add_faq'),
    path('add_call_note/', views.add_call_note, name='add_call_note'),
    path('respond_chat/', views.respond_chat, name='respond_chat'),
    path('close_chat/', views.close_chat, name='close_chat'),

    path('birth_certificate_request/', views.birth_certificate_request, name='birth_certificate_request'),

]
