from django.shortcuts import render, redirect
from django.http import HttpResponse
from docs.models import Application, UploadedDocument, ChatMessage, Certification
from .models import (Fulfiller,Note, PostLocation, InterviewSlot,
                     Interview, ToDo, Boot, OfficerProfile, Notification,
                     FAQ, FAQCategory, CallNote, MessageNote, FollowUpNote)
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.dateparse import parse_date
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
from django.db.models import F, Q
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from django.shortcuts import render, get_object_or_404
from datetime import datetime
from datetime import date
import csv
import pandas as pd
import json
import qrcode
from io import BytesIO
import base64
import tempfile
from django.template.loader import get_template
from django.templatetags.static import static
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from threading import Thread
from django.core.mail import send_mail
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.utils.text import slugify
import logging
from django.http import HttpResponseForbidden, HttpResponse
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_POST
from django.db.models import Prefetch
from django.db.models import Exists, OuterRef
from django.db import models
from datetime import timedelta
from django.utils.timezone import now
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from weasyprint import HTML, CSS
import logging
import os


def send_email_in_thread(subject, message, recipient_email):
    def send():
        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [recipient_email],
            fail_silently=False,
        )

    # Start the email sending in a new thread
    email_thread = Thread(target=send)
    email_thread.start()


def send_notification(user, message):
    notification = Notification.objects.create(user=user, message=message)
    notification.save()

@login_required
def mark_notification_as_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    return redirect('immigration_dashboard')


@login_required
def immigration_dashboard(request):
    user = request.user

    # Default counts to avoid potential NameError
    new_requests_count = 0
    pending_requests_count = 0
    waiting_requests_count = 0
    interview_requests_count = 0
    pending_todo_count = 0

    # Check if the user is a superuser
    if user.is_superuser:
        # Superusers can see all data
        new_requests_count = Application.objects.filter(status='pending').count()
        pending_requests_count = Application.objects.filter(status='processing').count()
        waiting_requests_count = Application.objects.filter(status='waiting').count()

        today = date.today()
        interview_requests_count = Application.objects.filter(
            status='interview',
            interview_slot__date_time__date=today
        ).count()

        pending_todo_count = ToDo.objects.filter(status=0).count()

    elif hasattr(user, 'officerprofile') and user.officerprofile.post_location:
        # For regular users, filter by post location
        post_location = user.officerprofile.post_location

        new_requests_count = Application.objects.filter(
            status='pending',
            post_location=post_location
        ).count()

        pending_requests_count = Application.objects.filter(
            status='processing',
            post_location=post_location
        ).count()

        waiting_requests_count = Application.objects.filter(
            status='waiting',
            post_location=post_location
        ).count()

        today = date.today()
        interview_requests_count = Application.objects.filter(
            status='interview',
            interview_slot__date_time__date=today,
            post_location=post_location
        ).count()

        pending_todo_count = ToDo.objects.filter(
            status=0,
            application__post_location=post_location
        ).count()

    context = {
        'new_requests_count': new_requests_count,
        'pending_requests_count': pending_requests_count,
        'waiting_requests_count': waiting_requests_count,
        'interview_requests_count': interview_requests_count,
        'pending_todo_count': pending_todo_count,
    }

    return render(request, 'immigration/dashboard.html', context)


@login_required
def fulfillers_list(request):
    user = request.user
    fulfillers = Fulfiller.objects.all()

    # Filtering based on user group and post location
    if not user.is_superuser:
        if user.groups.filter(name__in=['immigration', 'police', 'tax']).exists():
            fulfillers = fulfillers.filter(location=user.officerprofile.post_location)
        else:
            fulfillers = Fulfiller.objects.none()

    # Pagination
    paginator = Paginator(fulfillers, 10)  # Show 10 fulfillers per page
    page_number = request.GET.get('page')
    try:
        fulfillers_page = paginator.get_page(page_number)
    except (EmptyPage, PageNotAnInteger):
        fulfillers_page = paginator.get_page(1)

    # Pass filter parameters back to the template to persist them in the form
    context = {
        'fulfillers': fulfillers_page,
    }

    return render(request, 'immigration/fulfillers_list.html', context)

@login_required
def filler_search(request):
    search_query = request.GET.get('search', '')
    date_from = request.GET.get('dateFrom', '')
    date_to = request.GET.get('dateTo', '')
    priority = request.GET.get('priority', '')
    status = request.GET.get('status', '')

    # Start with all fulfillers if the user is a superuser
    if request.user.is_superuser:
        fulfillers = Fulfiller.objects.all()
    else:
        user_location = request.user.officerprofile.post_location  # Adjust as necessary
        fulfillers = Fulfiller.objects.filter(location=user_location)

    # Apply filters
    if search_query:
        fulfillers = fulfillers.filter(
            Q(application__status__icontains=search_query) |  # Application's status
            Q(location__name__icontains=search_query) |       # PostLocation's name
            Q(action__username__icontains=search_query) |     # User's username
            Q(status__icontains=search_query)                  # Fulfiller's status
        )

    if date_from:
        fulfillers = fulfillers.filter(created_at__gte=date_from)

    if date_to:
        fulfillers = fulfillers.filter(created_at__lte=date_to)

    if priority:
        fulfillers = fulfillers.filter(priority=priority)

    if status:
        fulfillers = fulfillers.filter(status=status)

    # Render the filtered results as HTML
    return render(request, 'immigration/filler_search.html', {'fulfillers': fulfillers})

def update_fulfiller_details(fulfiller, request):
    """Updates the fulfiller details from the POST request and notifies the requester."""
    fulfiller.location_id = request.POST.get('location')
    fulfiller.action_id = request.user.id
    fulfiller.schedule = request.POST.get('schedule')
    fulfiller.priority = request.POST.get('priority')
    fulfiller.status = request.POST.get('status')
    fulfiller.progress = request.POST.get('progress')
    fulfiller.save()

    # Notify the requester about the state update
    application = fulfiller.application
    requester = application.user

    state = request.POST.get('state')

    subject = 'Your Application State Has Been Updated'
    message = f"""
    Dear {requester.get_full_name()},

    The state of your application (ID: {application.id}) has been updated to: {state}.

    Please log in to your portal to view more details.

    Best regards,  
    The Gambia Immigration Office
    """

    send_email_in_thread(subject, message, requester.email)


def assign_interview_slot(application, request, questionnaire, notes_text):
    """Assigns an available interview slot to the application."""
    interview_slot = InterviewSlot.objects.filter(
        current_interviewees__lt=F('max_interviewees'),
        date_time__gte=timezone.now(),
        is_available=True,
        location=application.post_location
    ).order_by('date_time').first()

    if interview_slot:
        application.interview_slot = interview_slot
        application.interview_queue_number = interview_slot.current_interviewees + 1
        interview_slot.current_interviewees += 1

        if interview_slot.current_interviewees >= interview_slot.max_interviewees:
            interview_slot.is_available = False
        interview_slot.save()

        Interview.objects.create(
            application=application,
            interviewer=request.user,
            questionnaire=questionnaire,
            notes=notes_text,
            status='scheduled'
        )
        return True
    else:
        messages.warning(request, 'No available interview slots.')
        return False

@login_required
def fulfiller_detail(request, id):
    user = request.user
    fulfiller = get_object_or_404(Fulfiller, id=id)
    application = fulfiller.application

    # Permission check for non-superusers
    if not user.is_superuser and getattr(user, 'officerprofile', None) and fulfiller.application.post_location != user.officerprofile.post_location:
        messages.warning(request, "You do not have permission to view this fulfiller.")
        return redirect('fulfiller')

    # Fetch related data
    doc_uploads = UploadedDocument.objects.filter(application=application)
    notes = Note.objects.filter(application=application).order_by('-created_at')
    post_locations = PostLocation.objects.all()

    if request.method == 'POST':
        try:
            # Update fulfiller details
            update_fulfiller_details(fulfiller, request)

            # Handle interview slot assignment
            application_status = request.POST.get('state')
            questionnaire = request.POST.get('questionnaire')
            notes_text = request.POST.get('notes')

            if application_status == 'interview' and not application.interview_slot:
                if not assign_interview_slot(application, request, questionnaire, notes_text):
                    return redirect('fulfiller_detail', id=fulfiller.id)

            # Update application status
            application.status = application_status
            application.save()

            messages.success(request, 'Fulfiller details and message updated successfully.')

        except ValidationError as e:
            messages.warning(request, f"Validation error: {e}")
        except Exception as e:
            messages.success(request, f"Error updating fulfiller details: {e}")

        return redirect('fulfiller_detail', id=fulfiller.id)

    # Get all users for the template
    users = User.objects.all()

    # Render the template with context data
    return render(request, 'immigration/fulfiller_detail.html', {
        'fulfiller': fulfiller,
        'application': application,
        'doc_uploads': doc_uploads,
        'post_locations': post_locations,
        'users': users,
        'notes': notes,
    })

@login_required
def send_note_to_requester(request, fulfiller_id):
    """Sends a note to the requester and notifies them via email."""
    if request.method == 'POST':
        fulfiller = get_object_or_404(Fulfiller, id=fulfiller_id)
        application = fulfiller.application
        requester = application.user
        message_text = request.POST.get('message')

        if message_text:
            # Create a new note for the requester
            Note.objects.create(
                application=application,
                user=request.user,
                message=message_text
            )

            # Send email notification to the requester
            subject = 'You Have Received a New Message Regarding Your Application'
            email_message = f"""
            Dear {requester.get_full_name()},

            You have received a new message regarding your application (ID: {application.id}):

            "{message_text}"

            Please log in to your portal to view more details.

            Best regards,  
            The Gambia Immigration Office
            """

            send_email_in_thread(subject, email_message, requester.email)

            messages.success(request, 'Message sent successfully to the requester and email notification sent.')
        else:
            messages.warning(request, 'Please enter a message before sending.')

        return redirect('fulfiller_detail', id=fulfiller_id)
    else:
        messages.error(request, 'Invalid request method.')
        return redirect('fulfiller_detail', id=fulfiller_id)

@login_required
def post_locations(request):
    user = request.user

    # Fetch locations based on user type
    if user.is_superuser:
        locations_list = PostLocation.objects.all()
    else:
        # Check if the user has an OfficerProfile
        officer_profile = getattr(user, 'officerprofile', None)
        if officer_profile and officer_profile.post_location:
            locations_list = PostLocation.objects.filter(id=officer_profile.post_location.id)
        else:
            # If no OfficerProfile or post_location is found, deny access or handle gracefully
            messages.warning(request, "You do not have permission to view post locations.")
            return  redirect('immigration_dashboard')

    # Paginate locations (10 per page)
    paginator = Paginator(locations_list, 10)
    page_number = request.GET.get('page', 1)  # Default to the first page
    locations = paginator.get_page(page_number)

    # Render template with paginated locations
    context = {'locations': locations}
    return render(request, 'immigration/post_locations.html', context)

@login_required
def add_post_location(request):
    if not request.user.is_superuser:
        messages.warning(request, "You do not have permission to add post locations.")
        return redirect('post_locations')

    if request.method == 'POST':
        name = request.POST.get('name')
        address = request.POST.get('address')
        city = request.POST.get('city')
        region = request.POST.get('region')
        district = request.POST.get('district')
        settlement = request.POST.get('settlement')
        postal_code = request.POST.get('postal_code')
        country = request.POST.get('country')

        # Create a new post location with all fields
        PostLocation.objects.create(
            name=name,
            address=address,
            city=city,
            region=region,
            district=district,
            settlement=settlement,
            postal_code=postal_code,
            country=country
        )
        # user = request.user  # Assuming the current user is the one to notify
        # send_notification(user, f"A location has been added {name}.")
        messages.success(request, "Post location added successfully.")
        return redirect('post_locations')

    return render(request, 'immigration/add_post_location.html')

@login_required
def edit_post_location(request, id):
    location = get_object_or_404(PostLocation, id=id)

    # Check if the user is a superuser or has the admin group for the location
    if not request.user.is_superuser:
        if location != request.user.officerprofile.post_location or not request.user.groups.filter(name='admin').exists():
            messages.warning(request, "You do not have permission to edit this post location.")
            return redirect('post_locations')

    if request.method == 'POST':
        location.name = request.POST.get('name')
        location.address = request.POST.get('address')
        location.city = request.POST.get('city')
        location.region = request.POST.get('region')
        location.district = request.POST.get('district')
        location.settlement = request.POST.get('settlement')
        location.postal_code = request.POST.get('postal_code')
        location.country = request.POST.get('country')
        location.save()
        messages.success(request, "Post location updated successfully.")
        # user = request.user  # Assuming the current user is the one to notify
        # send_notification(user, f"Post location was added {name}.")
        return redirect('post_locations')

    return render(request, 'immigration/edit_post_location.html', {'location': location})


@login_required
def delete_post_location(request, id):
    location = get_object_or_404(PostLocation, id=id)

    # Check if the user is a superuser or has the admin group for the location
    if not request.user.is_superuser:
        if location != request.user.officerprofile.post_location or not request.user.groups.filter(name='admin').exists():
            messages.warning(request, "You do not have permission to delete this post location.")
            return redirect('post_locations')

    location.delete()
    user = request.user  # Assuming the current user is the one to notify
    send_notification(user, f"Post location was deleted.")
    messages.success(request, "Post location deleted successfully.")
    return redirect('post_locations')

@login_required
def list_officer_users(request):
    # Ensure that only superusers can view this list
    if not request.user.is_superuser:
        messages.warning(request, "You do not have permission to view this list.")
        return redirect('immigration_dashboard')  # Redirect to a safe page

    immigration_officers = User.objects.filter(groups__name='immigration')
    police_officers = User.objects.filter(groups__name='police')
    tax_officers = User.objects.filter(groups__name='tax')

    context = {
        'immigration_officers': immigration_officers,
        'police_officers': police_officers,
        'tax_officers': tax_officers
    }

    return render(request, 'immigration/list_officer_users.html', context)

@login_required
def create_user(request):
    # Ensure that only superusers can create users
    if not request.user.is_superuser:
        messages.warning(request, "You do not have permission to create users.")
        return redirect('list_officer_users')

    if request.method == 'POST':
        username = request.POST.get('username')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role')  # Immigration, Police, or Tax officer
        post_location_id = request.POST.get('post_location')
        officer_batch_number = request.POST.get('officer_batch_number')

        # Check if the username already exists
        if User.objects.filter(username=username).exists():
            messages.warning(request, 'Username already exists.')
        else:
            # Create the user
            user = User.objects.create_user(username=username, email=email, password=password)
            user.first_name = first_name
            user.last_name = last_name
            user.save()

            # Try to get the group by name (role) instead of id
            try:
                group = Group.objects.get(name=role)
                user.groups.add(group)  # Add the user to the group
                user.save()

                # Create the officer profile
                post_location = PostLocation.objects.get(id=post_location_id)
                OfficerProfile.objects.create(
                    user=user,
                    officer_batch_number=officer_batch_number,
                    post_location=post_location
                )
                # user = request.user  # Assuming the current user is the one to notify
                # send_notification(user, f"Officer user account {username} was created.")
                messages.success(request, f'{role.capitalize()} user created successfully!')
                return redirect('list_officer_users')
            except Group.DoesNotExist:
                messages.warning(request, f'Group "{role}" does not exist.')
            except PostLocation.DoesNotExist:
                messages.warning(request, 'Invalid post location.')

    # Fetch groups based on their name
    groups = Group.objects.filter(name__in=['immigration', 'police', 'tax', 'admin'])
    post_locations = PostLocation.objects.all()

    return render(request, 'immigration/create_user.html', {'groups': groups, 'post_locations': post_locations})

@login_required
def edit_user(request, user_id):
    # Ensure that only superusers can edit users
    if not request.user.is_superuser:
        messages.warning(request, "You do not have permission to edit users.")
        return redirect('list_officer_users')

    user = get_object_or_404(User, id=user_id)
    officer_profile = get_object_or_404(OfficerProfile, user=user)

    if request.method == 'POST':
        user.username = request.POST.get('username')
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.email = request.POST.get('email')
        user.save()

        officer_profile.officer_batch_number = request.POST.get('officer_batch_number')
        post_location_id = request.POST.get('post_location')
        officer_profile.post_location = get_object_or_404(PostLocation, id=post_location_id)
        officer_profile.save()

        # Update user groups
        group_ids = request.POST.getlist('groups')
        user.groups.set(group_ids)

        # Remove selected groups
        remove_group_ids = request.POST.getlist('remove_groups')
        for group_id in remove_group_ids:
            group = Group.objects.get(id=group_id)
            user.groups.remove(group)

        messages.success(request, 'User updated successfully!')
        return redirect('list_officer_users')

    groups = Group.objects.all()
    post_locations = PostLocation.objects.all()

    return render(request, 'immigration/edit_officer_user.html', {
        'user': user,
        'officer_profile': officer_profile,
        'groups': groups,
        'post_locations': post_locations
    })

@login_required
def delete_user(request, user_id):
    # Ensure that only superusers can delete users
    if not request.user.is_superuser:
        messages.warning(request, "You do not have permission to delete users.")
        return redirect('list_officer_users')

    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        user.delete()
        messages.success(request, 'User deleted successfully!')
        return redirect('list_officer_users')

    return render(request, 'immigration/delete_post_user.html', {'user': user})

@login_required
def create_group(request):
    # Ensure that only superusers can create groups
    if not request.user.is_superuser:
        messages.warning(request, "You do not have permission to create groups.")
        return redirect('list_officer_users')

    if request.method == 'POST':
        group_name = request.POST.get('group_name')

        if Group.objects.filter(name=group_name).exists():
            messages.error(request, 'Group already exists.')
        else:
            Group.objects.create(name=group_name)
            user = request.user  # Assuming the current user is the one to notify
            send_notification(user, f"Group {group_name} was created.")
            messages.success(request, f'Group "{group_name}" created successfully.')
            return redirect('list_officer_users')

    groups = Group.objects.all()
    return render(request, 'immigration/create_group.html', {'groups': groups})


@login_required
def edit_group(request, group_id):
    # Ensure that only superusers can edit groups
    if not request.user.is_superuser:
        messages.warning(request, "You do not have permission to edit groups.")
        return redirect('list_officer_users')

    group = get_object_or_404(Group, id=group_id)
    available_users = OfficerProfile.objects.exclude(user__groups=group).order_by('user__username')
    group_members = OfficerProfile.objects.filter(user__groups=group).order_by('user__username')

    if request.method == 'POST':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            action = request.POST.get('action')
            user_id = request.POST.get('user_id')

            if not user_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No user specified.'
                }, status=400)

            try:


                if action == 'remove':
                    officer_profile = OfficerProfile.objects.get(user__id=user_id)
                    officer_profile.user.groups.remove(group)
                    send_notification(officer_profile.user, f"You have been removed from group {group.name}.")
                    return JsonResponse({
                        'status': 'success',
                        'message': f'{officer_profile.user.get_full_name()} was removed from the group successfully.'
                    })
                elif action == 'add':
                    officer_profile = OfficerProfile.objects.get(id=user_id)
                    officer_profile.user.groups.add(group)
                    send_notification(officer_profile.user, f"You have been added to group {group.name}.")
                    return JsonResponse({
                        'status': 'success',
                        'message': f'{officer_profile.user.get_full_name()} was added to the group successfully.'
                    })

            except OfficerProfile.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Officer profile not found.'
                }, status=404)

        # Regular form submission for group name update
        group_name = request.POST.get('group_name')
        if Group.objects.filter(name=group_name).exclude(id=group_id).exists():
            messages.error(request, 'Group name already exists.')
        else:
            group.name = group_name
            group.save()
            user = request.user
            send_notification(user, f"Group {group_name} was updated.")
            messages.success(request, f'Group "{group_name}" updated successfully.')
            return redirect('list_officer_users')

    return render(request, 'immigration/edit_group.html', {
        'group': group,
        'available_users': available_users,
        'group_members': group_members,
    })

@login_required
def delete_group(request, group_id):
    # Ensure that only superusers can delete groups
    if not request.user.is_superuser:
        messages.warning(request, "You do not have permission to delete groups.")
        return redirect('list_officer_users')

    group = get_object_or_404(Group, id=group_id)

    if request.method == 'POST':
        group.delete()
        user = request.user  # Assuming the current user is the one to notify
        send_notification(user, f"Group {group.name} was deleted.")
        messages.success(request, f'Group "{group.name}" deleted successfully.')
        return redirect('list_officer_users')

    return render(request, 'immigration/delete_group.html', {'group': group})


@login_required
def available_slots(request):
    user = request.user

    # Check if the user is in the admin group for their location
    is_admin = user.groups.filter(name='admin').exists() and user.officerprofile.post_location

    # Ensure that only users in the admin group for the specific location or superusers can access the slots
    if not user.is_superuser and not is_admin:
        messages.warning(request, "You do not have permission to view available interview slots.")
        return redirect('todo_list')

    # Retrieve interview slots sorted from newest to oldest
    if user.is_superuser:
        interview_slots = InterviewSlot.objects.all().order_by('-date_time')
    else:
        interview_slots = InterviewSlot.objects.filter(location=user.officerprofile.post_location).order_by('-date_time')

    paginator = Paginator(interview_slots, 5)  # Show 5 slots per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    if request.method == 'POST':
        date_time = request.POST.get('date_time')
        max_interviewees = request.POST.get('max_interviewees')
        location_id = request.POST.get('location')
        location = get_object_or_404(PostLocation, id=location_id)

        try:
            # Create a new interview slot
            InterviewSlot.objects.create(
                date_time=date_time,
                max_interviewees=max_interviewees,
                location=location,
                is_available=True
            )
            # Notify the user about the new slot
            send_notification(user, f"Interview slot {date_time} was created.")
            messages.success(request, "Interview slot added successfully!")
            return redirect('available_slots')
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")

    post_locations = PostLocation.objects.all()

    return render(request, 'immigration/available_slots.html', {
        'page_obj': page_obj,
        'post_locations': post_locations,
    })

@login_required
def interview_list(request):
    user = request.user
    current_datetime = timezone.now()

    if user.is_superuser:
        interviews = Interview.objects.exclude(Q(status='completed') | Q(status='canceled')).filter(application__interview_slot__date_time__lte=current_datetime).order_by('date_created')
    else:
        interviews = Interview.objects.exclude(Q(status='completed') | Q(status='canceled')).filter(application__post_location=user.officerprofile.post_location, application__interview_slot__date_time__lte=current_datetime).order_by('date_created')

    return render(request, 'immigration/interview_list.html', {
        'interviews': interviews,
        'current_datetime': current_datetime,
    })

@login_required
def interview_view(request, interview_id):
    interview = get_object_or_404(Interview, id=interview_id)
    application = interview.application

    # Ensure the user can only see interviews in their post location if not a superuser
    if not request.user.is_superuser and application.post_location != request.user.officerprofile.post_location:
        messages.error(request, "You do not have permission to view this interview.")
        return redirect('interview_list')

    documents = UploadedDocument.objects.filter(application=application)  # Fetch the related documents

    # Determine if the form should be read-only (when status is 'waiting' or 'canceled')
    read_only = interview.status in ['waiting', 'canceled']

    if request.method == 'POST':
        duration_str = request.POST.get('duration', '0')
        try:
            duration = int(duration_str)
        except ValueError:
            duration = 0  # Default to 0 if the duration is not a valid number

        if 'postpone' in request.POST:  # Handle postponing the interview
            # Change interview status to postponed
            interview.status = 'postponed'
            interview.duration = duration  # Save the duration
            interview.save()

            # Get the current interview slot's date
            current_interview_date = interview.application.interview_slot.date_time

            # Find the next available interview slot after the current interview date
            interview_slot = InterviewSlot.objects.filter(
                current_interviewees__lt=F('max_interviewees'),
                date_time__gt=current_interview_date,  # Ensure it is after the current date
                is_available=True
            ).order_by('date_time').first()

            if interview_slot:
                # Assign the new interview slot and update the queue number
                application.interview_slot = interview_slot
                application.interview_queue_number = interview_slot.current_interviewees + 1

                # Update the interview slot's current interviewees count
                interview_slot.current_interviewees += 1
                if interview_slot.current_interviewees >= interview_slot.max_interviewees:
                    interview_slot.is_available = False
                interview_slot.save()

                application.save()  # Save the application updates
                # user = request.user  # Assuming the current user is the one to notify
                # send_notification(user, f"Interview was postpone")
                messages.success(request, "Interview postponed successfully, and a new slot assigned.")
            else:
                messages.warning(request, "No available interview slots for postponement.")
            return redirect('interview_list')

        else:  # Handle submitting the interview questionnaire and notes
            questionnaire = request.POST.get('questionnaire')
            notes = request.POST.get('notes')
            interview.questionnaire = questionnaire
            interview.notes = notes
            interview.status = 'waiting'  # Update the status to 'waiting'
            interview.duration = duration  # Save the duration
            interview.save()

            # Create a ToDo instance when interview status changes to 'waiting'
            ToDo.objects.create(
                application=application,
                interview=interview,
                user=request.user,  # The user who is conducting the interview
                approver=None,  # Approver can be set later
                status=0  # Default to pending (0)
            )
            user = request.user  # Assuming the current user is the one to notify
            send_notification(user, f"Interview is awaiting {application.user.get_full_name()} approval ")
            messages.success(request, 'Interview details updated and ToDo created successfully.')
            return redirect('interview_list')

    return render(request, 'immigration/interview.html', {
        'interview': interview,
        'application': application,
        'documents': documents,
        'read_only': read_only,
    })

@login_required
def todo_list(request):
    user = request.user
    # Check if the user is in the admin group for their location
    is_admin = user.groups.filter(name='admin').exists() and user.officerprofile.post_location

    # Base queryset based on user permissions
    if user.is_superuser:
        base_queryset = ToDo.objects.all()
    elif is_admin:
        base_queryset = ToDo.objects.filter(
            application__post_location=user.officerprofile.post_location
        )
    else:
        messages.warning(request, "You do not have permission to view ToDo items.")
        return redirect('immigration_dashboard')

    # Apply filters if provided
    filters = Q()

    # Application Type filter
    application_type = request.GET.get('application_type')
    if application_type:
        filters &= Q(application__application_type=application_type)

    # Status filter
    status = request.GET.get('status')
    if status:
        filters &= Q(status=status)

    # Date Range filter
    date_range = request.GET.get('date_range')
    if date_range:
        try:
            selected_date = datetime.strptime(date_range, '%Y-%m-%d').date()
            filters &= Q(created_at__date=selected_date)
        except ValueError:
            messages.error(request, "Invalid date format")

    # Apply filters and ordering to base queryset
    todos = base_queryset.filter(filters).order_by('-created_at')

    # Pagination
    page = request.GET.get('page', 1)
    items_per_page = 10  # You can adjust this number
    paginator = Paginator(todos, items_per_page)

    try:
        todos_page = paginator.page(page)
    except PageNotAnInteger:
        todos_page = paginator.page(1)
    except EmptyPage:
        todos_page = paginator.page(paginator.num_pages)

    # Calculate completed today count
    today = timezone.now().date()
    completed_today = base_queryset.filter(
        status=1,  # Approved status
        updated_at__date=today
    ).count()
    pending = base_queryset.filter(
        status=0,  # Approved status
    ).count()

    # Get unique application types for the filter dropdown
    application_types = ToDo.objects.values_list(
        'application__application_type',
        'application__application_type'
    ).distinct()

    # Prepare context with all necessary data
    context = {
        'todos': todos_page,  # Now using paginated queryset
        'completed_today': completed_today,
        'pending': pending,
        'application_types': application_types,
        'current_filters': {
            'application_type': application_type,
            'status': status,
            'date_range': date_range,
        }
    }

    return render(request, 'immigration/todo_list.html', context)

@login_required
def todo_detail(request, todo_id):
    todo = get_object_or_404(ToDo, id=todo_id)

    # Ensure the user is in the admin group for their location if not a superuser
    is_admin = request.user.groups.filter(name='admin').exists() and request.user.officerprofile.post_location

    if not request.user.is_superuser and not is_admin:
        messages.warning(request, "You do not have permission to view this ToDo item.")
        return redirect('todo_list')

    # Further check for specific location
    if not request.user.is_superuser and todo.application.post_location != request.user.officerprofile.post_location:
        messages.warning(request, "You do not have permission to view this ToDo item.")
        return redirect('todo_list')

    return render(request, 'immigration/todo_detail.html', {
        'todo': todo,
    })

@login_required
def approve_todo(request, todo_id):
    todo = get_object_or_404(ToDo, id=todo_id)

    # Check if the user is in the admin group for their location
    is_admin = request.user.groups.filter(name='admin').exists() and request.user.officerprofile.post_location

    # Ensure the user can only approve ToDo items in their post location if not a superuser
    if not request.user.is_superuser and not is_admin:
        messages.warning(request, "You do not have permission to approve this ToDo item.")
        return redirect('todo_list')

    # Further check for specific location
    if not request.user.is_superuser and todo.application.post_location != request.user.officerprofile.post_location:
        messages.warning(request, "You do not have permission to approve this ToDo item.")
        return redirect('todo_list')

    # Update the status to approved and set the approver to the current user
    todo.status = 1  # Approved status
    todo.approver = request.user
    todo.save()

    # Also update the related application and interview statuses to 'completed'
    application = todo.application
    interview = todo.interview

    application.status = 'completed'
    interview.status = 'completed'

    # Set the fulfiller status to 'closed' and progress to 100
    fulfiller = application.fulfiller
    if fulfiller:
        fulfiller.status = 'closed'
        fulfiller.progress = 100
        fulfiller.save()

    application.save()
    interview.save()

    # Notify the requester via in-app notification
    requester = application.user
    # send_notification(requester, f"Your interview for application ID {application.id} has been approved.")

    # Send email notification to the requester
    subject = 'Your Application For National Document Has Been Approved'
    email_message = f"""
    Dear {requester.get_full_name()},

    Your interview for application ID {application.id} has been approved and marked as completed.

    Please log in to your portal to view more details.

    Best regards,  
    The Gambia Immigration Office
    """

    send_email_in_thread(subject, email_message, requester.email)

    messages.success(request, "ToDo item has been approved successfully. Application and Interview are marked as completed.")
    return redirect('todo_list')


@login_required
def reject_todo(request, todo_id):
    todo = get_object_or_404(ToDo, id=todo_id)

    # Check if the user is in the admin group for their location
    is_admin = request.user.groups.filter(name='admin').exists() and request.user.officerprofile.post_location

    # Ensure the user can only reject ToDo items in their post location if not a superuser
    if not request.user.is_superuser and not is_admin:
        messages.warning(request, "You do not have permission to reject this ToDo item.")
        return redirect('todo_list')

    # Further check for specific location
    if not request.user.is_superuser and todo.application.post_location != request.user.officerprofile.post_location:
        messages.warning(request, "You do not have permission to reject this ToDo item.")
        return redirect('todo_list')

    if request.method == 'POST':
        rejection_reason = request.POST.get('rejection_reason', '')
        todo.status = 2  # Assuming 2 is the status code for rejected
        todo.approver = request.user
        todo.rejection_reason = rejection_reason
        todo.save()

        # Also update the related application and interview statuses to 'canceled'
        application = todo.application
        interview = todo.interview

        application.status = 'canceled'
        interview.status = 'canceled'

        fulfiller = application.fulfiller
        if fulfiller:
            fulfiller.status = 'closed'
            fulfiller.progress = 100
            fulfiller.save()

        application.save()
        interview.save()

        # Notify the requester via in-app notification
        requester = application.user
        send_notification(requester, f"Your ToDo item for application ID {application.id} has been rejected.")

        # Send email notification to the requester
        subject = 'Your Application For National Document Has Been Rejected'
        email_message = f"""
        Dear {requester.get_full_name()},

        Your application item for application ID {application.id} has been rejected.

        Rejection Reason: {rejection_reason}

        Please log in to your portal to view more details.

        Best regards,  
        The Gambia Immigration Office
        """

        send_email_in_thread(subject, email_message, requester.email)

        messages.success(request, "ToDo item has been rejected successfully and the requester has been notified.")
        return redirect('todo_list')

    return render(request, 'immigration/reject_todo.html', {
        'todo': todo,
    })

@login_required
def generate_todo_receipt_pdf(request, todo_id):
    # Fetch the ToDo item by id
    todo = get_object_or_404(ToDo, id=todo_id)

    # Generate QR code from the application token
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(todo.application.token)
    qr.make(fit=True)

    # Save QR code to a BytesIO object
    img = qr.make_image(fill='black', back_color='white')
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    qr_code_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

    # Get the full URL for the logo
    logo_url = request.build_absolute_uri(static('img/logo.png'))

    # Load the receipt template and render it with context
    template = get_template('immigration/todo_receipt.html')
    context = {
        'todo': todo,
        'user': request.user,
        'qr_code_base64': qr_code_base64,
        'logo_url': logo_url,
    }
    html_content = template.render(context)

    # Generate the PDF directly into the response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="ToDo_Receipt_{todo.id}.pdf"'

    try:
        # Write the PDF to the response
        HTML(string=html_content).write_pdf(target=response)
    except Exception as e:
        return HttpResponse(f"Error generating PDF: {str(e)}", status=500)

    return response

@login_required
def queue_info(request):
    user = request.user
    current_date = timezone.now().date()

    if user.is_superuser:
        boots = Boot.objects.all()
        interviews = Interview.objects.exclude(status__in=["waiting", "completed", "canceled"]).filter(application__interview_slot__date_time__lte=current_date).order_by('application__interview_queue_number')
    else:
        boots = Boot.objects.filter(post_location=user.officerprofile.post_location)
        interviews = Interview.objects.exclude(status__in=["waiting", "completed", "canceled"]).filter(application__post_location=user.officerprofile.post_location, application__interview_slot__date_time__lte=current_date).order_by('application__interview_queue_number')

    # if request.method == 'POST':
    #     interview_id = request.POST.get('interview_id')
    #     interview = get_object_or_404(Interview, id=interview_id)
    #     interview.status = 'in_progress'
    #     interview.save()
    #     messages.success(request, 'Interview started successfully.')
    #     return redirect(f'/immigration/interview/{interview_id}')

    return render(request, 'immigration/queue_info.html', {
        'boots': boots,
        'interviews': interviews,
    })

@login_required
def start_interview(request):
    if request.method == 'POST':
        # Parse JSON data
        try:
            data = json.loads(request.body)
            interview_id = data.get('interview_id')
        except (ValueError, KeyError):
            return JsonResponse({"success": False, "message": "Invalid data received."}, status=400)

        # Ensure interview_id is provided
        if not interview_id:
            return JsonResponse({"success": False, "message": "Interview ID not provided."}, status=400)

        # Try to get the Interview object
        try:
            interview = Interview.objects.get(id=interview_id)

            # Check if the interview is already in progress
            if interview.status == 'in_progress':
                return JsonResponse({"success": False, "message": "Interview is already in progress."}, status=400)

            # Assign the user's boot automatically
            # Get the user's assigned boot (assuming user has only one boot assigned)
            user_boot = Boot.objects.filter(assigned_to=request.user).first()

            if user_boot:
                # If the user has a boot assigned, update the interview's boot
                interview.boot = user_boot
                interview.status = 'in_progress'
                interview.save()

                return JsonResponse({"success": True, "boot_id": user_boot.id})
            else:
                return JsonResponse({"success": False, "message": "No boot assigned to the user."}, status=400)

        except Interview.DoesNotExist:
            return JsonResponse({"success": False, "message": "Interview not found."}, status=404)

    return JsonResponse({"success": False, "message": "Invalid request method."}, status=405)

@login_required
def fetch_interview_queue(request):
    current_date = timezone.now().date()
    boots = Boot.objects.all()
    interviews = Interview.objects.exclude(status__in=["waiting", "completed", "canceled"]).filter(application__interview_slot__date_time__lte=current_date).order_by('application__interview_queue_number')
    return render(request, 'immigration/interview_queue_partial.html', {
        'boots': boots,
        'interviews': interviews,
    })

@login_required
def boot_list(request):
    user = request.user
    if user.is_superuser:
        boots = Boot.objects.all()
    else:
        boots = Boot.objects.filter(post_location=user.officerprofile.post_location)

    users = User.objects.all()
    groups = Group.objects.all()
    post_locations = PostLocation.objects.all()
    return render(request, 'immigration/boot_list.html', {'boots': boots, 'users': users, 'groups': groups, 'post_locations': post_locations})

@login_required
def add_boot(request):
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to add boots.")
        return redirect('boot_list')

    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        assigned_to_id = request.POST.get('assigned_to')
        group_id = request.POST.get('group')
        post_location_id = request.POST.get('post_location')

        if name and assigned_to_id and group_id and post_location_id:
            assigned_to = User.objects.get(id=assigned_to_id)
            group = Group.objects.get(id=group_id)
            post_location = PostLocation.objects.get(id=post_location_id)
            Boot.objects.create(name=name, description=description, assigned_to=assigned_to, group=group, post_location=post_location)
            user = request.user  # Assuming the current user is the one to notify
            send_notification(user, f"Boot {name} was added")
            messages.success(request, 'Boot added successfully.')
            return redirect('boot_list')
        else:
            messages.error(request, 'Please fill in all required fields.')

    users = User.objects.all()
    groups = Group.objects.all()
    post_locations = PostLocation.objects.all()
    return render(request, 'immigration/add_boot.html', {'users': users, 'groups': groups, 'post_locations': post_locations})

@login_required
def change_assignment(request, boot_id):
    boot = get_object_or_404(Boot, id=boot_id)

    # Ensure the user can only change assignments for boots in their post location if not a superuser
    if not request.user.is_superuser and boot.post_location != request.user.officerprofile.post_location:
        messages.error(request, "You do not have permission to change the assignment for this boot.")
        return redirect('boot_list')

    if request.method == 'POST':
        assigned_to_id = request.POST.get('assigned_to')
        group_id = request.POST.get('group')
        post_location_id = request.POST.get('post_location')
        if assigned_to_id and group_id and post_location_id:
            assigned_to = User.objects.get(id=assigned_to_id)
            group = Group.objects.get(id=group_id)
            post_location = PostLocation.objects.get(id=post_location_id)
            boot.assigned_to = assigned_to
            boot.group = group
            boot.post_location = post_location
            boot.save()
            user = request.user  # Assuming the current user is the one to notify
            send_notification(user, f"Boot {boot.name} was just updated ")
            messages.success(request, 'Boot assignment updated successfully.')
        else:
            messages.error(request, 'Please select valid user, group, and post location.')

    return redirect('boot_list')

@login_required
def export_pdf(request):
    # Implement your PDF export logic here
    return HttpResponse("PDF export not implemented yet.")

@login_required
def export_excel(request):
    if request.user.is_superuser or request.user.is_staff:
        fulfillers = Fulfiller.objects.all()
    else:
        fulfillers = Fulfiller.objects.filter(action=request.user)

    data = []
    for fulfiller in fulfillers:
        data.append({
            'service_type': fulfiller.application.get_service_type(),
            'created_at': fulfiller.created_at,
            'updated_at': fulfiller.updated_at,
            'location': fulfiller.location,
            'action': fulfiller.action,
            'schedule': fulfiller.schedule,
            'priority': fulfiller.priority,
            'status': fulfiller.status,
            'progress': fulfiller.progress,
        })

    df = pd.DataFrame(data)

    # Convert datetime fields to be timezone-unaware
    df['created_at'] = pd.to_datetime(df['created_at']).dt.tz_localize(None)
    df['updated_at'] = pd.to_datetime(df['updated_at']).dt.tz_localize(None)
    df['schedule'] = pd.to_datetime(df['schedule']).dt.tz_localize(None)

    response = HttpResponse(content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename="fulfillers.xlsx"'
    df.to_excel(response, index=False)
    return response

@login_required
def export_csv(request):
    if request.user.is_superuser or request.user.is_staff:
        fulfillers = Fulfiller.objects.all()
    else:
        fulfillers = Fulfiller.objects.filter(action=request.user)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="fulfillers.csv"'
    writer = csv.writer(response)
    writer.writerow(['Service Type', 'Created At', 'Updated At', 'Location', 'Action', 'Schedule', 'Priority', 'Status', 'Progress'])
    for fulfiller in fulfillers:
        writer.writerow([
            fulfiller.application.get_service_type(),
            fulfiller.created_at,
            fulfiller.updated_at,
            fulfiller.location,
            fulfiller.action,
            fulfiller.schedule,
            fulfiller.priority,
            fulfiller.status,
            fulfiller.progress,
        ])
    return response

@login_required
def export_webpage(request):
    if request.user.is_superuser or request.user.is_staff:
        fulfillers = Fulfiller.objects.all()
    else:
        fulfillers = Fulfiller.objects.filter(action=request.user)
    return render(request, 'immigration/export_webpage.html', {'fulfillers': fulfillers})

def is_staff_or_superuser(user):
    return user.is_staff or user.is_superuser


@login_required
def support_desk(request):
    # Fetch FAQs
    faqs = FAQ.objects.all()

    # Fetch top-level unread chats (main chats) and prefetch replies for efficiency
    chats = (
        ChatMessage.objects.filter(parent__isnull=True, is_read=False)
        .order_by('-timestamp')
        .annotate(
            has_note=Exists(MessageNote.objects.filter(chat_id=OuterRef('id')))
        )
        .prefetch_related(
            Prefetch(
                'replies',
                queryset=ChatMessage.objects.all()
            )
        )
    )

    # Fetch call notes for the logged-in user
    call_notes = CallNote.objects.filter(user=request.user)
    incomplete_notes = call_notes.filter(completed=False)

    # Define open and closed application statuses
    open_statuses = ['pending', 'processing', 'waiting', 'interview']
    closed_statuses = ['completed', 'canceled']

    # Fetch counts for open/closed applications
    open_applications = Application.objects.filter(status__in=open_statuses).count()
    closed_applications = Application.objects.filter(status__in=closed_statuses).count()

    # Fetch counts for open/closed chats
    open_chats = ChatMessage.objects.filter(is_read=False, parent__isnull=True).count()
    closed_chats = ChatMessage.objects.filter(is_read=True, parent__isnull=True).count()

    # Fetch FAQ categories for the form
    faq_categories = FAQCategory.objects.all()

    faq_data = []
    for faq in faqs:
        faq_data.append({
            'view_count': faq.view_count,
            'created_by': faq.created_by.get_full_name() if faq.created_by else 'N/A',
            'updated_by': faq.updated_by.get_full_name() if faq.updated_by else 'N/A',
            'priority': faq.get_priority_display(),
            'created_at': faq.created_at,
            'updated_at': faq.updated_at,
        })



    # Context data for the template
    context = {
        'meta': faq_data,
        'faqs': faqs,
        'chats': chats,
        'call_notes': call_notes,
        'open_applications': open_applications,
        'closed_applications': closed_applications,
        'open_chats': open_chats,
        'closed_chats': closed_chats,
        'categories': faq_categories,
        'incomplete_notes': incomplete_notes,
    }
    return render(request, 'immigration/support_desk.html', context)

# Validation function for FAQ data
def validate_faq_data(data):
    """Validate FAQ data and return any errors"""
    errors = {}

    if len(data['question']) < 10:
        errors['question'] = 'Question must be at least 10 characters long.'

    if len(data['answer']) < 20:
        errors['answer'] = 'Answer must be at least 20 characters long.'

    if data['category_id']:
        try:
            FAQCategory.objects.get(id=data['category_id'])
        except FAQCategory.DoesNotExist:
            errors['category'] = 'Invalid category selected.'

    if data['priority'] not in dict(FAQ.PRIORITY_CHOICES):
        errors['priority'] = 'Invalid priority selected.'

    return errors

@login_required
def add_faq(request):
    if request.method == 'POST':
        # Extract data from the form
        category_id = request.POST.get('category')
        question = request.POST.get('question')
        answer = request.POST.get('answer')
        tags = request.POST.get('tags', '')
        priority = request.POST.get('priority', 'low')

        # Validate and process the category
        try:
            category = FAQCategory.objects.get(id=category_id)
        except FAQCategory.DoesNotExist:
            category = None

        # Create the FAQ
        faq = FAQ(
            category=category,
            question=question,
            answer=answer,
            tags=tags,
            priority=priority,
            created_by=request.user,
            updated_by=request.user,
        )
        faq.save()

        # Display success message and redirect
        messages.success(request, 'FAQ added successfully.')
        return redirect('support_desk')  # Redirect to the support desk view

    return redirect('support_desk')  # Redirect for non-POST requests

@login_required
def update_faq(request, faq_id):
    faq = FAQ.objects.get(id=faq_id)

    if request.method == 'POST':
        # Ensure the user is authenticated
        if not request.user.is_authenticated:
            return JsonResponse({"success": False, "error": "User not authenticated"})

        # Get the data from the form submission
        question = request.POST.get('question')
        answer = request.POST.get('answer')
        category_id = request.POST.get('category')
        tags = request.POST.get('tags')

        # Set the updated fields
        faq.question = question
        faq.answer = answer
        faq.category_id = category_id  # Assuming category ID is sent
        faq.tags = tags
        faq.updated_by = request.user  # Set the user who updated the FAQ

        # Save the changes
        faq.save()

        return JsonResponse({"success": True})

    return JsonResponse({"success": False, "error": "Invalid request"})

# Delete FAQ View
@login_required
@require_http_methods(["POST", "DELETE"])
def delete_faq(request, faq_id):
    try:
        faq = get_object_or_404(FAQ, id=faq_id)

        # Soft delete
        faq.is_active = False
        faq.updated_by = request.user
        faq.save()

        messages.success(request, 'FAQ deleted successfully!')
        return redirect('support_desk')

    except Exception as e:
        logging.error(f"Error deleting FAQ: {str(e)}", exc_info=True)
        messages.error(request, 'An unexpected error occurred while deleting the FAQ.')
        return redirect('support_desk')

# AJAX Add FAQ View
@login_required
@require_http_methods(["POST"])
def add_faq_ajax(request):
    try:
        # Extract and clean form data
        data = {
            'question': request.POST.get('question', '').strip(),
            'answer': request.POST.get('answer', '').strip(),
            'category_id': request.POST.get('category'),
            'priority': request.POST.get('priority', 'low'),
            'tags': request.POST.get('tags', '').strip(),
        }

        # Validate input
        errors = validate_faq_data(data)
        if errors:
            return JsonResponse({'success': False, 'errors': errors}, status=400)

        # Create FAQ
        faq = FAQ.objects.create(
            question=data['question'],
            answer=data['answer'],
            category_id=data['category_id'],
            priority=data['priority'],
            tags=data['tags'],
            created_by=request.user,
            updated_by=request.user,
        )

        return JsonResponse({
            'success': True,
            'message': 'FAQ added successfully!',
            'faq': {
                'id': faq.id,
                'question': faq.question,
                'answer': faq.answer,
                'category': faq.category.name if faq.category else None,
                'priority': faq.priority,
                'view_count': faq.view_count,
                'updated_at': faq.updated_at,
                'created_by': faq.created_by,
                'tags': faq.tags,
                'created_at': faq.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            }
        })

    except Exception as e:
        logging.error(f"Error in AJAX Add FAQ: {str(e)}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'An unexpected error occurred.'}, status=500)

@login_required
def search_faqs(request):
    try:
        query = request.GET.get('q', '').strip()
        category = request.GET.get('category')
        priority = request.GET.get('priority')

        faqs = FAQ.objects.filter(is_active=True)

        # Apply filters
        if query:
            faqs = FAQ.search(query)

        if category:
            faqs = faqs.filter(category_id=category)

        if priority:
            faqs = faqs.filter(priority=priority)

        # Increment view count for search results
        for faq in faqs:
            faq.increment_view_count()

        faqs_data = faqs.values(
            'id', 'question', 'answer', 'priority',
            'view_count', 'tags', 'created_at', 'updated_at',
            'category__name', 'created_by__first_name',
            'created_by__last_name'
        )

        return JsonResponse({
            'success': True,
            'faqs': list(faqs_data)
        })

    except Exception as e:
        import logging
        logging.error(f"Error searching FAQs: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while searching FAQs'
        }, status=500)


@login_required
@user_passes_test(is_staff_or_superuser)
def add_call_note(request):
    if request.method == 'POST':
        note = request.POST.get('note')
        customer = request.POST.get('customer')
        call_type = request.POST.get('call_type')
        priority = request.POST.get('priority')
        followup = request.POST.get('followup') == 'on'  # Handle checkbox input for followup
        # followup_date = request.POST.get('followup_date')

        # Validate required fields
        if not note:
            messages.error(request, "Please provide a call note.")
            return redirect('support_desk')

        # # If follow-up is checked, ensure followup_date is provided
        # if followup and not followup_date:
        #     messages.error(request, "Please provide a follow-up date.")
        #     return redirect('support_desk')

        # Convert followup_date to DateTime if provided
        # if followup_date:
        #     try:
        #         followup_date = timezone.make_aware(timezone.datetime.strptime(followup_date, "%Y-%m-%d %H:%M"))
        #     except ValueError:
        #         messages.error(request, "Invalid follow-up date format. Use YYYY-MM-DD HH:MM format.")
        #         return redirect('support_desk')

        # Create the CallNote object
        CallNote.objects.create(
            user=request.user,
            customer=customer,
            call_type=call_type,
            priority=priority,
            note=note,
            followup=followup,
            # followup_date=followup_date,
        )

        messages.success(request, "Call note added successfully!")

    return redirect('support_desk')

@login_required
@user_passes_test(lambda user: user.is_staff or user.is_superuser, login_url='login')
def respond_chat(request):
    if request.method == 'POST':
        chat_id = request.POST.get('chat_id')
        response_text = request.POST.get('response')
        response_type = request.POST.get('response_type')

        if not response_type:
            messages.error(request, "Response type is required.")
            return redirect('support_desk')

        is_urgent = 'mark_urgent' in request.POST  # Checkbox, True if checked
        requires_follow_up = 'require_followup' in request.POST  # Checkbox, True if checked

        # Fetch the original chat message
        original_chat = get_object_or_404(ChatMessage, id=chat_id)

        # Create the response message
        response_message = ChatMessage.objects.create(
            sender=request.user,
            recipient=original_chat.sender,
            message=response_text,
            parent=original_chat,
            response_type=response_type,
            is_urgent=is_urgent,  # Ensure this field exists in the model
            requires_follow_up=requires_follow_up  # Ensure this field exists in the model
        )

        # Prepare and send email notification in a thread
        subject = 'New Response to Your Support Request'
        message = (
            f"Hello {original_chat.sender.get_full_name()},\n\n"
            f"You have received a new response to your support request:\n\n"
            f'"{response_text}"\n\n'
            "Please check your support chat for more details."
        )
        recipient_email = original_chat.sender.email

        if recipient_email:
            send_email_in_thread(subject, message, recipient_email)

        messages.success(request, 'Response sent successfully.')
        return redirect('support_desk')
    else:
        messages.error(request, 'Invalid request method.')
        return redirect('support_desk')



@login_required
@user_passes_test(is_staff_or_superuser)
@csrf_exempt
def close_chat(request):
    if request.method == 'POST':
        chat_id = request.POST.get('chat_id')
        try:
            # Get the main chat message
            chat = ChatMessage.objects.get(id=chat_id)
            chat.is_read = True
            chat.save()

            # Mark all replies to this chat as read
            ChatMessage.objects.filter(parent=chat).update(is_read=True)

            # Send email notification to the requester
            subject = 'Your Support Request Has Been Closed'
            message = f'Hello {chat.sender.get_full_name()},\n\nYour support request has been closed. If you need further assistance, please contact us again.\n\nThank you!'
            recipient_email = chat.sender.email

            send_mail(
                subject,
                message,
                settings.EMAIL_HOST_USER,
                [recipient_email],
                fail_silently=False,
            )

            return JsonResponse({'success': True})
        except ChatMessage.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Chat message not found'})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def certificate_request(request):
    certifications = Certification.objects.all()

    # Current counts
    pending_count = certifications.filter(status='pending').count()
    approved_count = certifications.filter(status='approved').count()
    rejected_count = certifications.filter(status='rejected').count()

    # Calculate date ranges
    today = now()
    last_week = today - timedelta(weeks=1)
    last_month = today - timedelta(days=30)

    # Previous period counts for comparison
    last_week_pending = certifications.filter(status='pending', submission_date__range=(last_week, today)).count()
    last_week_approved = certifications.filter(status='approved', submission_date__range=(last_week, today)).count()
    last_week_rejected = certifications.filter(status='rejected', submission_date__range=(last_week, today)).count()

    last_month_pending = certifications.filter(status='pending', submission_date__range=(last_month, today)).count()
    last_month_approved = certifications.filter(status='approved', submission_date__range=(last_month, today)).count()
    last_month_rejected = certifications.filter(status='rejected', submission_date__range=(last_month, today)).count()

    # Calculate percentage changes
    def calculate_percentage_change(current, previous):
        if previous == 0:
            return 0  # Avoid division by zero
        return round(((current - previous) / previous) * 100, 2)

    pending_change_week = calculate_percentage_change(pending_count, last_week_pending)
    approved_change_week = calculate_percentage_change(approved_count, last_week_approved)
    rejected_change_week = calculate_percentage_change(rejected_count, last_week_rejected)

    pending_change_month = calculate_percentage_change(pending_count, last_month_pending)
    approved_change_month = calculate_percentage_change(approved_count, last_month_approved)
    rejected_change_month = calculate_percentage_change(rejected_count, last_month_rejected)

    # Determine arrow directions
    pending_arrow_week = 'up' if pending_change_week >= 0 else 'down'
    approved_arrow_week = 'up' if approved_change_week >= 0 else 'down'
    rejected_arrow_week = 'up' if rejected_change_week >= 0 else 'down'

    pending_arrow_month = 'up' if pending_change_month >= 0 else 'down'
    approved_arrow_month = 'up' if approved_change_month >= 0 else 'down'
    rejected_arrow_month = 'up' if rejected_change_month >= 0 else 'down'

    # Recent activity
    recent_activity = certifications.order_by('-submission_date')[:5]

    return render(request, 'immigration/certificate-dashboard.html', {
        'certifications': certifications,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'pending_change_week': pending_change_week,
        'approved_change_week': approved_change_week,
        'rejected_change_week': rejected_change_week,
        'pending_change_month': pending_change_month,
        'approved_change_month': approved_change_month,
        'rejected_change_month': rejected_change_month,
        'pending_arrow_week': pending_arrow_week,
        'approved_arrow_week': approved_arrow_week,
        'rejected_arrow_week': rejected_arrow_week,
        'pending_arrow_month': pending_arrow_month,
        'approved_arrow_month': approved_arrow_month,
        'rejected_arrow_month': rejected_arrow_month,
        'recent_activity': recent_activity,
    })

@login_required
def certificate_detail(request, cert_id):
    # Fetch the certificate
    certificate = get_object_or_404(Certification, id=cert_id)

    # Initialize related_data and qr_url
    related_data = None
    qr_url = None

    # Fetch related data based on certificate type
    if certificate.certificate_type == 'birth':
        related_data = getattr(certificate, 'birth_registration', None)

        if related_data and hasattr(related_data, 'birth_registration_number'):  # Check if birth registration number exists
            # Generate QR code for birth registration number
            qr = qrcode.make(related_data.birth_registration_number)
            qr_io = BytesIO()
            qr.save(qr_io, format='PNG')
            qr_io.seek(0)

            # Save QR code to a temporary file in the media folder
            file_name = f"birth_registration_qr_{certificate.id}.png"
            path = default_storage.save(f"documents/{file_name}", ContentFile(qr_io.read()))
            qr_url = default_storage.url(path)

    elif certificate.certificate_type == 'marriage':
        related_data = getattr(certificate, 'marriage_details', None)
    elif certificate.certificate_type == 'death':
        related_data = getattr(certificate, 'death_details', None)
    elif certificate.certificate_type == 'character':
        related_data = getattr(certificate, 'character_certificate', None)
    elif certificate.certificate_type == 'academic':
        related_data = getattr(certificate, 'academic_certificate', None)

    # Fetch supporting documents for the certificate
    supporting_documents = certificate.attachments.all()

    # Add qr_url directly to the context with a fallback value if None
    return render(request, 'immigration/certificate-detail.html', {
        'certificate': certificate,
        'related_data': related_data,
        'supporting_documents': supporting_documents,
        'qr_url': qr_url if qr_url is not None else '',  # Ensure qr_url is never None
    })

# Set up logging
logger = logging.getLogger(__name__)

class CertificateError(Exception):
    """Custom exception for certificate-related errors"""
    pass


def get_related_data(certificate):
    """
    Get related data for a certificate based on its type.

    Args:
        certificate: Certificate instance

    Returns:
        Related model instance or None

    Raises:
        CertificateError: If related data is not found
    """
    try:
        related_data_mapping = {
            'birth': 'birth_registration',
            'marriage': 'marriage_details',
            'death': 'death_details',
            'character': 'character_certificate',
            'academic': 'academic_certificate'
        }

        if certificate.certificate_type not in related_data_mapping:
            raise CertificateError(f"Invalid certificate type: {certificate.certificate_type}")

        related_field = related_data_mapping[certificate.certificate_type]
        related_data = getattr(certificate, related_field, None)

        if related_data is None:
            raise CertificateError(f"No related {certificate.certificate_type} data found")

        return related_data

    except Exception as e:
        logger.error(f"Error getting related data for certificate {certificate.id}: {str(e)}")
        raise CertificateError(f"Error retrieving related data: {str(e)}")


def get_certificate_identifier(certificate, related_data):
    """
    Generate a unique identifier for QR code based on certificate type.

    Args:
        certificate: Certificate instance
        related_data: Related model instance

    Returns:
        str: Unique identifier for the certificate
    """
    try:
        identifier_mapping = {
            'birth': lambda: related_data.birth_registration_number,
            'marriage': lambda: f"MAR-{related_data.id}-{datetime.now().year}",
            'death': lambda: f"DTH-{related_data.id}-{datetime.now().year}",
            'character': lambda: f"CHR-{related_data.id}-{datetime.now().year}",
            'academic': lambda: f"ACD-{related_data.id}-{datetime.now().year}"
        }

        get_identifier = identifier_mapping.get(certificate.certificate_type)
        if not get_identifier:
            raise CertificateError(f"Cannot generate identifier for type: {certificate.certificate_type}")

        return get_identifier()

    except Exception as e:
        logger.error(f"Error generating identifier for certificate {certificate.id}: {str(e)}")
        raise CertificateError(f"Error generating certificate identifier: {str(e)}")


def generate_qr_code(registration_number):
    """Generate QR code and return as base64 string"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(registration_number)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Save image to bytes buffer
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    # Convert to base64
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"


def print_certificate(request, certificate_id):
    """
    Generate PDF certificate.

    Args:
        request: HTTP request object
        certificate_id: ID of the certificate to print

    Returns:
        HttpResponse with PDF content

    Raises:
        Http404: If certificate not found
        CertificateError: If PDF generation fails
    """
    try:
        # Get the certificate and related data
        certificate = Certification.objects.select_related(
            'birth_registration',
            'marriage_details',
            'death_details',
            'character_certificate',
            'academic_certificate'
        ).get(id=certificate_id)

        # Check if the certificate is approved
        if certificate.status != 'approved':  # Check the status field
            logger.warning(f"Attempted to print an unapproved certificate {certificate_id}")
            return HttpResponse(
                "This certificate is not approved and cannot be printed.",
                status=403
            )

        # Determine QR data based on certificate type
        if certificate.certificate_type == 'birth':
            qr_data = certificate.birth_registration.birth_registration_number
        elif certificate.certificate_type == 'marriage':
            qr_data = f"{certificate.marriage_details.spouse1_name} & {certificate.marriage_details.spouse2_name}"
        elif certificate.certificate_type == 'death':
            qr_data = certificate.death_details.death_registration_number
        elif certificate.certificate_type == 'character':
            qr_data = f"Character-{certificate.character_certificate.full_name}"
        elif certificate.certificate_type == 'academic':
            qr_data = certificate.academic_certificate.certificate_number
        else:
            qr_data = "Unknown Certificate Type"

        # Generate QR code as base64
        qr_image = generate_qr_code(qr_data)

        # Update context
        context = {
            'certificate': certificate,
            'qr_image': qr_image,  # Pass the base64 QR code
            'generated_date': datetime.now().strftime('%B %d, %Y'),
            'certificate_number': f"{certificate.certificate_type.upper()}-{certificate.id}"
        }

        # Render HTML
        html_string = render_to_string('immigration/certificate_template.html', context)
        html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))

        # Generate PDF response
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="{certificate.certificate_type}_'
            f'certificate_{certificate.id}.pdf"'
        )

        # Write PDF
        html.write_pdf(response, presentational_hints=True)

        # Log successful generation
        logger.info(f"Successfully generated PDF for certificate {certificate_id}")

        return response

    except Certification.DoesNotExist:
        logger.error(f"Certificate {certificate_id} not found")
        raise Http404(f"Certificate with id {certificate_id} not found")

    except CertificateError as ce:
        logger.error(f"Certificate error: {str(ce)}")
        raise

    except Exception as e:
        logger.error(f"Error generating PDF for certificate {certificate_id}: {str(e)}")
        raise CertificateError(f"Error generating PDF: {str(e)}")



@login_required
def approve_certificate(request, cert_id):
    certification = get_object_or_404(Certification, id=cert_id)

    if certification.status == 'approved':
        messages.info(request, "This certificate is already approved.")
        return redirect('certificate_dashboard')

    certification.status = 'approved'
    certification.approved_by = request.user
    certification.save()

    messages.success(request, f"Certificate {certification.get_certificate_type_display()} has been approved.")
    return redirect('certificate_dashboard')


@login_required
def get_user_application(request, user_id):
    try:
        # Fetch the latest application for the user
        application = Application.objects.exclude(
            Q(status='completed') | Q(status='cancelled')
        ).filter(user_id=user_id).latest('application_date')

        # Prepare the response data
        response_data = {
            'success': True,
            'application_id': application.get_service_type(),
            'application_date': application.application_date.strftime('%Y-%m-%d'),
            'application_location': application.post_location.name if application.post_location else 'N/A',
        }

        # Check if the application has a fulfiller and add progress if it exists
        if hasattr(application, 'fulfiller') and application.fulfiller is not None:
            response_data['progress'] = application.fulfiller.progress  # Adjust as per your Fulfiller model's field/method

        return JsonResponse(response_data)

    except Application.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'No application found for this user'})

    except Application.fulfiller.RelatedObjectDoesNotExist:
        # Handle missing fulfiller explicitly
        response_data = {
            'success': True,
            'application_id': application.get_service_type(),
            'application_date': application.application_date.strftime('%Y-%m-%d'),
            'application_location': application.post_location.name if application.post_location else 'N/A',
            'progress': 'N/A',  # No progress available
        }
        return JsonResponse(response_data)

# Take not for chat
@login_required
@require_POST
def save_note(request):
    """
    Save a new note for a chat with optional title and importance.
    """
    # Extract POST data
    sender_id = request.POST.get('sender_id')
    chat_id = request.POST.get('chat_id')
    note_text = request.POST.get('note')
    title = request.POST.get('title', '').strip()  # Optional field
    important = request.POST.get('important', '0') == '1' # Boolean conversion

    # Validate input data
    if not note_text:
        return JsonResponse({'success': False, 'error': 'Note content cannot be empty'}, status=400)

    try:
        # Fetch sender and chat objects
        sender = User.objects.get(id=sender_id)
        chat = ChatMessage.objects.get(id=chat_id)

        # Optional: Check if the user has permission to create a note for the chat
        if not request.user.has_perm('can_add_note', chat):  # Example permission
            raise PermissionDenied("You do not have permission to add notes to this chat.")

        # Create the note
        new_note = MessageNote.objects.create(
            user=sender,
            chat=chat,
            note=note_text,
            title=title,
            important=important,
            created_by=request.user
        )

        # Return success response
        return JsonResponse({
            'success': True,
            'created_by': request.user.get_full_name(),
            'note': new_note.note,
            'title': new_note.title,
            'important': new_note.important,
            'created_at': new_note.created_at.strftime('%Y-%m-%d %H:%M'),
        })
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Sender not found'}, status=404)
    except ChatMessage.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Chat not found'}, status=404)
    except PermissionDenied as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=403)
    except Exception as e:
        return JsonResponse({'success': False, 'error': 'An unexpected error occurred'}, status=500)

@login_required
def get_user_notes(request, user_id):
    """
    Fetches notes for a specific user where the chat is not closed.
    Includes title and important fields in the response.
    """
    # Validate if the user exists
    get_object_or_404(User, id=user_id)

    # Fetch notes for the user with non-closed chats
    notes = MessageNote.objects.filter(user_id=user_id, chat__is_read=False).order_by('-created_at')

    # Prepare notes data
    notes_data = [
        {
            'created_by': note.created_by.get_full_name(),
            'note': note.note,
            'title': note.title,
            'important': note.important,
            'created_at': note.created_at.strftime('%Y-%m-%d %H:%M'),
        }
        for note in notes
    ]

    # Return notes as JSON
    return JsonResponse({'notes': notes_data})

@login_required
@csrf_exempt
def close_call_note(request, note_id):
    """Marks a call note as completed."""
    if request.method == 'POST':
        try:
            note = CallNote.objects.get(id=note_id)
            note.completed = True
            note.save()
            return JsonResponse({'success': True})
        except CallNote.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Note not found'})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def search_call_notes(request):
    query = request.GET.get('q', '')
    notes = CallNote.objects.filter(
        Q(note__icontains=query) | Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query)
    ).order_by('-created_at')

    notes_data = [
        {
            'user': note.user.get_full_name(),
            'note': note.note,
            'created_at': note.created_at.strftime('%Y-%m-%d %H:%M'),
            'completed': note.completed
        } for note in notes
    ]

    return JsonResponse({'notes': notes_data})

# In your view (manage_follow_up_note)
@login_required
def manage_follow_up_note(request, call_note_id):
    call_note = get_object_or_404(CallNote, id=call_note_id)

    if request.method == "POST":
        note_id = request.POST.get('note_id', None)
        note_content = request.POST.get('note', '').strip()


        # Calculate the next sort order
        max_sort_order = call_note.follow_up_notes.aggregate(
                max_order=models.Max('sort_order')
            )['max_order'] or 0
        sort_order = max_sort_order + 1

        FollowUpNote.objects.create(
                call_note=call_note,
                note=note_content,
                created_by=request.user,
                sort_order=sort_order
            )
        messages.success(request, "The follow-up note was created successfully.")
        return redirect('support_desk')

@login_required
@csrf_exempt
def sort_follow_up_notes(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        call_note_id = data.get('call_note_id')
        sorted_ids = data.get('sorted_ids', [])

        # Update sort_order for each note
        for order, note_id in enumerate(sorted_ids):
            FollowUpNote.objects.filter(id=note_id, call_note_id=call_note_id).update(sort_order=order)

        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'error'}, status=400)

@login_required
def toggle_follow_up_completion(request, note_id):
    if request.method == 'POST':
        follow_up_note = get_object_or_404(FollowUpNote, id=note_id)
        follow_up_note.completed = not follow_up_note.completed
        follow_up_note.save()
        return JsonResponse({'success': True, 'completed': follow_up_note.completed})
    return JsonResponse({'success': False}, status=400)

