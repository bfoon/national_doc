from django.shortcuts import render, redirect
from docs.models import Application, UploadedDocument
from .models import Fulfiller
from django.contrib.auth.models import User
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
            fulfiller.location = location
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

            messages.success(request, 'Fulfiller details updated successfully.')
        except Exception as e:
            messages.error(request, f"Error updating fulfiller details: {e}")

        return redirect('fulfiller_detail', id=fulfiller.id)

    # Get the list of users for the action dropdown
    users = User.objects.all()

    return render(request, 'immigration/fulfiller_detail.html', {
        'fulfiller': fulfiller,
        'application': application,
        'doc_uploads': doc_uploads,  # Pass the documents to the template (False if none)
        'users': users,
    })
