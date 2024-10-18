from django.shortcuts import render, redirect
from docs.models import Application, UploadedDocument
from .models import Fulfiller,Note, PostLocation
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from django.shortcuts import render, get_object_or_404
from datetime import datetime
from datetime import date


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
    # Get all fulfillers for the logged-in user
    fulfillers = Fulfiller.objects.all()

    # Filtering logic
    if 'dateFrom' in request.GET and request.GET['dateFrom']:
        date_from = request.GET['dateFrom']
        fulfillers = fulfillers.filter(schedule__gte=date_from)

    if 'dateTo' in request.GET and request.GET['dateTo']:
        date_to = request.GET['dateTo']
        fulfillers = fulfillers.filter(schedule__lte=date_to)

    if 'priority' in request.GET and request.GET['priority']:
        priority = request.GET['priority']
        fulfillers = fulfillers.filter(priority=priority)

    if 'status' in request.GET and request.GET['status']:
        status = request.GET['status']
        fulfillers = fulfillers.filter(status=status)

    # Searching logic
    if 'search' in request.GET and request.GET['search']:
        search_query = request.GET['search']
        fulfillers = fulfillers.filter(title__icontains=search_query)

    # Pagination
    paginator = Paginator(fulfillers, 10)  # Show 10 fulfillers per page
    page_number = request.GET.get('page')
    fulfillers_page = paginator.get_page(page_number)

    return render(request, 'immigration/fulfillers_list.html', {
        'fulfillers': fulfillers_page,
    })

@login_required
def fulfiller_detail(request, id):
    fulfiller = get_object_or_404(Fulfiller, id=id)
    application = fulfiller.application
    doc_uploads = UploadedDocument.objects.filter(application=application)  # Fetch all documents related to the application
    notes = Note.objects.filter(application=application).order_by('-created_at')  # Fetch all notes for this application

    # Fetch all post locations for the dropdown
    post_locations = PostLocation.objects.all()

    # If no documents exist, set doc_uploads to None or False
    if not doc_uploads.exists():
        doc_uploads = False  # You can also use None here depending on your preference

    if request.method == 'POST':
        try:
            # Get data from POST request
            location = request.POST.get('location')
            action_user_id = request.POST.get('action')  # User selected in the dropdown
            schedule = request.POST.get('schedule')
            priority = request.POST.get('priority')
            status = request.POST.get('status')
            progress = request.POST.get('progress')
            message_to_requester = request.POST.get('message')  # Message to requester

            # Update the fulfiller details
            fulfiller.location_id = location
            if action_user_id:
                fulfiller.action = User.objects.get(id=action_user_id)  # Assign selected user
            fulfiller.schedule = schedule
            fulfiller.priority = priority
            fulfiller.status = status
            fulfiller.progress = progress
            fulfiller.save()

            # Update application status
            application_status = request.POST.get('state')
            application.status = application_status
            application.save()

            # Capture the message to the requester if provided
            if message_to_requester:
                Note.objects.create(
                    application=application,
                    user=request.user,
                    message=message_to_requester
                )

            messages.success(request, 'Fulfiller details and message updated successfully.')
        except Exception as e:
            messages.error(request, f"Error updating fulfiller details: {e}")

        return redirect('fulfiller_detail', id=fulfiller.id)

    # Get the list of users for the action dropdown
    users = User.objects.all()

    return render(request, 'immigration/fulfiller_detail.html', {
        'fulfiller': fulfiller,
        'application': application,
        'doc_uploads': doc_uploads,  # Pass the documents to the template (False if none)
        'post_locations': post_locations,  # Pass the post locations to the template
        'users': users,
        'notes': notes,  # Pass the notes to the template
    })

@login_required
def post_locations(request):
    locations_list = PostLocation.objects.all()
    paginator = Paginator(locations_list, 10)  # Show 10 locations per page
    page_number = request.GET.get('page')
    locations = paginator.get_page(page_number)

    return render(request, 'immigration/post_locations.html', {'locations': locations})

@login_required
def add_post_location(request):
    # Handle POST request to add a new post location
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
        messages.success(request, "Post location added successfully.")
        return redirect('post_locations')

    return render(request, 'immigration/add_post_location.html')

@login_required
def edit_post_location(request, id):
    # Fetch the specific post location to edit
    location = get_object_or_404(PostLocation, id=id)
    if request.method == 'POST':
        # Update the post location details
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
        return redirect('post_locations')

    return render(request, 'immigration/edit_post_location.html', {'location': location})

@login_required
def delete_post_location(request, id):
    location = get_object_or_404(PostLocation, id=id)
    location.delete()
    messages.success(request, "Post location deleted successfully.")
    return redirect('post_locations')

@login_required
def list_officer_users(request):
    # Get users in the Immigration, Police, and Tax officer groups
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
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role')  # Immigration, Police, or Tax officer

        # Check if the username already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
        else:
            # Create the user
            user = User.objects.create_user(username=username, email=email, password=password)

            # Try to get the group by name (role) instead of id
            try:
                group = Group.objects.get(name=role)
                user.groups.add(group)  # Add the user to the group
                user.save()
                messages.success(request, f'{role.capitalize()} user created successfully!')
                return redirect('list_officer_users')
            except Group.DoesNotExist:
                messages.error(request, f'Group "{role}" does not exist.')

    # Fetch groups based on their name
    groups = Group.objects.filter(name__in=['immigration', 'police', 'tax'])

    return render(request, 'immigration/create_user.html', {'groups': groups})

@login_required
def create_group(request):
    if request.method == 'POST':
        group_name = request.POST.get('group_name')

        if Group.objects.filter(name=group_name).exists():
            messages.error(request, 'Group already exists.')
        else:
            Group.objects.create(name=group_name)
            messages.success(request, f'Group "{group_name}" created successfully.')
            return redirect('list_officer_users')

    return render(request, 'immigration/create_group.html')

