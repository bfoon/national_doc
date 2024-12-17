from django.shortcuts import render, redirect
from django.http import HttpResponse
from docs.models import Application, UploadedDocument, ChatMessage
from .models import (Fulfiller,Note, PostLocation, InterviewSlot,
                     Interview, ToDo, Boot, OfficerProfile, Notification,
                     FAQ, CallNote)
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
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
from weasyprint import HTML
from django.templatetags.static import static
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from threading import Thread
from django.core.mail import send_mail
from django.conf import settings

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

@login_required
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
    if user.is_superuser:
        locations_list = PostLocation.objects.all()
    else:
        locations_list = PostLocation.objects.filter(id=user.officerprofile.post_location.id)

    paginator = Paginator(locations_list, 10)  # Show 10 locations per page
    page_number = request.GET.get('page')
    locations = paginator.get_page(page_number)

    return render(request, 'immigration/post_locations.html', {'locations': locations})

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

    if request.method == 'POST':
        group_name = request.POST.get('group_name')

        if Group.objects.filter(name=group_name).exclude(id=group_id).exists():
            messages.error(request, 'Group name already exists.')
        else:
            group.name = group_name
            group.save()
            user = request.user  # Assuming the current user is the one to notify
            send_notification(user, f"Group {group_name} was updated.")
            messages.success(request, f'Group "{group_name}" updated successfully.')
            return redirect('list_officer_users')

    return render(request, 'immigration/edit_group.html', {'group': group})

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

    if user.is_superuser:
        todos = ToDo.objects.all().order_by('-created_at')
    elif is_admin:
        todos = ToDo.objects.filter(application__post_location=user.officerprofile.post_location).order_by('-created_at')
    else:
        messages.warning(request, "You do not have permission to view ToDo items.")
        return redirect('immigration_dashboard')  # Redirect to a suitable page

    return render(request, 'immigration/todo_list.html', {
        'todos': todos,
    })


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
    send_notification(requester, f"Your interview for application ID {application.id} has been approved.")

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

def support_desk(request):
    faqs = FAQ.objects.all()

    # Fetch top-level unread chats (main chats) and prefetch replies for efficiency
    chats = ChatMessage.objects.filter(parent__isnull=True, is_read=False).order_by('-timestamp').prefetch_related(
        'replies')

    call_notes = CallNote.objects.filter(user=request.user)

    context = {
        'faqs': faqs,
        'chats': chats,
        'call_notes': call_notes,
    }
    return render(request, 'immigration/support_desk.html', context)

@login_required
def add_faq(request):
    if request.method == 'POST':
        question = request.POST.get('question')
        answer = request.POST.get('answer')

        if question and answer:
            FAQ.objects.create(question=question, answer=answer)
            messages.success(request, "FAQ added successfully!")
        else:
            messages.error(request, "Please fill in all fields.")

    return redirect('support_desk')

@login_required
def add_call_note(request):
    if request.method == 'POST':
        note = request.POST.get('note')

        if note:
            CallNote.objects.create(user=request.user, note=note)
            messages.success(request, "Call note added successfully!")
        else:
            messages.error(request, "Please provide a call note.")

    return redirect('support_desk')

@login_required
def respond_chat(request):
    if request.method == 'POST':
        chat_id = request.POST.get('chat_id')
        response_text = request.POST.get('response')
        original_chat = get_object_or_404(ChatMessage, id=chat_id)

        # Create the response message
        ChatMessage.objects.create(
            sender=request.user,
            recipient=original_chat.sender,
            message=response_text,
            parent=original_chat
        )

        # Send email notification in a thread
        subject = 'New Response to Your Support Request'
        message = f'Hello {original_chat.sender.get_full_name()},\n\nYou have received a new response to your support request:\n\n"{response_text}"\n\nPlease check your support chat for more details.'
        recipient_email = original_chat.sender.email

        send_email_in_thread(subject, message, recipient_email)

        messages.success(request, 'Response sent successfully.')
        return redirect('support_desk')



@login_required
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
def birth_certificate_request(request):
    return render(request, 'immigration/birth_certificate_request.html')