from django.shortcuts import render, redirect
from docs.models import Application, UploadedDocument
from .models import (Fulfiller,Note, PostLocation, InterviewSlot,
                     Interview, ToDo, Boot, OfficerProfile, Notification)
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

def send_notification(user, message):
    notification = Notification.objects.create(user=user, message=message)
    notification.save()

def mark_notification_as_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    return redirect('dashboard')

@login_required
def immigration_dashboard(request):
    # Count the number of applications for each status
    new_requests_count = Application.objects.filter(status='pending').count()
    pending_requests_count = Application.objects.filter(status='processing').count()
    waiting_requests_count = Application.objects.filter(status='waiting').count()

    # Count interviews scheduled for today
    today = date.today()
    interview_requests_count = Application.objects.filter(status='interview', interview_slot__date_time=today).count()

    context = {
        'new_requests_count': new_requests_count,
        'pending_requests_count': pending_requests_count,
        'waiting_requests_count': waiting_requests_count,
        'interview_requests_count': interview_requests_count,
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

@login_required
def fulfiller_detail(request, id):
    user = request.user
    fulfiller = get_object_or_404(Fulfiller, id=id)

    # Ensure the user can only see fulfillers in their post location if not a superuser
    if not user.is_superuser and fulfiller.application.post_location != user.officerprofile.post_location:
        messages.error(request, "You do not have permission to view this fulfiller.")
        return redirect('fulfillers_list')

    application = fulfiller.application
    doc_uploads = UploadedDocument.objects.filter(application=application)  # Get the queryset

    # No need to check if doc_uploads exists; just set it to an empty list if no documents found
    if not doc_uploads.exists():
        doc_uploads = []  # Ensure this is an empty list

    notes = Note.objects.filter(application=application).order_by('-created_at')
    post_locations = PostLocation.objects.all()

    if request.method == 'POST':
        try:
            # Get data from POST request
            location = request.POST.get('location')
            # action_user_id = request.POST.get('action')
            schedule = request.POST.get('schedule')
            priority = request.POST.get('priority')
            status = request.POST.get('status')
            progress = request.POST.get('progress')
            message_to_requester = request.POST.get('message')
            questionnaire = request.POST.get('questionnaire')  # Get questionnaire responses
            notes_text = request.POST.get('notes')  # Get additional notes

            # Update the fulfiller details
            fulfiller.location_id = location

            fulfiller.action = request.user
            fulfiller.schedule = schedule
            fulfiller.priority = priority
            fulfiller.status = status
            fulfiller.progress = progress
            fulfiller.save()

            # Update application status
            application_status = request.POST.get('state')
            if application_status == 'interview':
                # Check if the application already has an interview slot
                if not application.interview_slot:
                    # Find available interview slot at the closest location
                    interview_slot = InterviewSlot.objects.filter(
                        current_interviewees__lt=F('max_interviewees'),
                        date_time__gte=timezone.now(),
                        is_available=True,
                        location=application.post_location  # Ensure the slot is at the application's post location
                    ).order_by('date_time').first()

                    if interview_slot:
                        # Assign interview slot to the application
                        application.interview_slot = interview_slot
                        application.interview_queue_number = interview_slot.current_interviewees + 1

                        # Increment the current interviewees count in the interview slot
                        interview_slot.current_interviewees += 1
                        if interview_slot.current_interviewees >= interview_slot.max_interviewees:
                            interview_slot.is_available = False
                        interview_slot.save()

                        # Create an Interview instance
                        Interview.objects.create(
                            application=application,
                            interviewer=request.user,  # Assuming the logged-in user is the interviewer
                            questionnaire=questionnaire,
                            notes=notes_text,
                            status='scheduled'
                        )
                    else:
                        messages.warning(request, 'No available interview slots.')
                        return redirect('fulfiller_detail', id=fulfiller.id)

            # Update the application status
            application.status = application_status
            application.save()

            # Capture the message to the requester if provided
            if message_to_requester:
                Note.objects.create(
                    application=application,
                    user=request.user,
                    message=message_to_requester
                )
            user = request.user  # Assuming the current user is the one to notify
            send_notification(user, f"Your application status has change to {status}.")
            messages.success(request, 'Fulfiller details and message updated successfully.')
        except Exception as e:
            messages.warning(request, f"Error updating fulfiller details: {e}")

        return redirect('fulfiller_detail', id=fulfiller.id)

    users = User.objects.all()

    return render(request, 'immigration/fulfiller_detail.html', {
        'fulfiller': fulfiller,
        'application': application,
        'doc_uploads': doc_uploads,  # This is now always an iterable
        'post_locations': post_locations,
        'users': users,
        'notes': notes,
    })



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
        user = request.user  # Assuming the current user is the one to notify
        send_notification(user, f"A location has been added {name}.")
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
        user = request.user  # Assuming the current user is the one to notify
        send_notification(user, f"Post location was added {name}.")
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
                user = request.user  # Assuming the current user is the one to notify
                send_notification(user, f"Officer user account {username} was created.")
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

    return render(request, 'immigration/create_group.html')



@login_required
def available_slots(request):
    user = request.user

    # Check if the user is in the admin group for their location
    is_admin = user.groups.filter(name='admin').exists() and user.officerprofile.post_location

    # Ensure that only users in the admin group for the specific location or superusers can access the slots
    if not user.is_superuser and not is_admin:
        messages.warning(request, "You do not have permission to view available interview slots.")
        return redirect('todo_list')

    if user.is_superuser:
        interview_slots = InterviewSlot.objects.all()
    else:
        interview_slots = InterviewSlot.objects.filter(location=user.officerprofile.post_location)

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
            user = request.user  # Assuming the current user is the one to notify
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
    if user.is_superuser:
        interviews = Interview.objects.exclude(Q(status='completed') | Q(status='canceled')).order_by('date_created')
    else:
        interviews = Interview.objects.exclude(Q(status='completed') | Q(status='canceled')).filter(application__post_location=user.officerprofile.post_location).order_by('date_created')

    return render(request, 'immigration/interview_list.html', {
        'interviews': interviews,
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
                user = request.user  # Assuming the current user is the one to notify
                send_notification(user, f"Interview was postpone")
                messages.success(request, "Interview postponed successfully, and a new slot assigned.")
            else:
                messages.error(request, "No available interview slots for postponement.")
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
            send_notification(user, f"Interview is awaiting {application.user.get_full_name} approval ")
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

    # Update application and interview status to 'completed'
    application.status = 'completed'
    interview.status = 'completed'

    # Set the fulfiller status to 'closed' and progress to 100
    fulfiller = application.fulfiller  # Accessing the related fulfiller
    if fulfiller:
        fulfiller.status = 'closed'
        fulfiller.progress = 100
        fulfiller.save()

    application.save()
    interview.save()
    user = request.user  # Assuming the current user is the one to notify
    send_notification(user, f"Interview for {application.user.get_full_name} is approved ")

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

        # Update application and interview status to 'canceled'
        application.status = 'canceled'
        interview.status = 'canceled'

        fulfiller = application.fulfiller  # Accessing the related fulfiller
        if fulfiller:
            fulfiller.status = 'closed'
            fulfiller.progress = 100
            fulfiller.save()

        application.save()
        interview.save()

        user = request.user  # Assuming the current user is the one to notify
        send_notification(user, f"Interview for {application.user.get_full_name} is rejected ")
        messages.success(request, "ToDo item has been rejected successfully.")
        return redirect('todo_list')

    return render(request, 'immigration/reject_todo.html', {
        'todo': todo,
    })


@login_required
def queue_info(request):
    user = request.user
    if user.is_superuser:
        boots = Boot.objects.all()
        interviews = Interview.objects.exclude(status__in=["waiting", "completed"]).order_by('application__interview_queue_number')
    else:
        boots = Boot.objects.filter(post_location=user.officerprofile.post_location)
        interviews = Interview.objects.exclude(status__in=["waiting", "completed", "canceled"]).filter(application__post_location=user.officerprofile.post_location).order_by('application__interview_queue_number')

    if request.method == 'POST':
        interview_id = request.POST.get('interview_id')
        interview = get_object_or_404(Interview, id=interview_id)
        interview.status = 'in_progress'
        interview.save()
        messages.success(request, 'Interview started successfully.')
        return redirect(f'/immigration/interview/{interview_id}')

    return render(request, 'immigration/queue_info.html', {
        'boots': boots,
        'interviews': interviews,
    })

@login_required
def fetch_interview_queue(request):
    boots = Boot.objects.all()
    interviews = Interview.objects.exclude(status__in=["waiting", "completed", "canceled"]).order_by('application__interview_queue_number')
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
