from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import (NationalIDApplication,
                     UploadedDocument, Application,
                     ResidentPermitApplication, WorkPermitApplication)
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.http import JsonResponse

def landing_page(request):
    return render(request, 'docs/landing_page.html')

def login_page(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Log the user in and redirect to the dashboard
            login(request, user)
            return redirect('dashboard')  # Change this to the name of your dashboard URL
        else:
            # Add an error message and re-render the login page
            messages.error(request, 'Invalid username or password')

    return render(request, 'docs/login_page.html')

def logout_view(request):
    logout(request)  # This will log out the user
    return redirect('landing_page')  # Redirect to the landing page after logout

@login_required  # Ensure only authenticated users can access this view
@login_required
def dashboard(request):
    # Get the National ID application for the user, if it exists
    try:
        national_id_application = NationalIDApplication.objects.get(application__user=request.user)

        # Check if the application is expired
        is_expired = national_id_application.application.status == 'complete' and national_id_application.application.is_expired()

        if is_expired:
            status = 'Not Applied'
            applicatiion_date = False
            application_exists = False
        else:
            status = national_id_application.application.status
            applicatiion_date = national_id_application.created_at
            application_exists = True
    except NationalIDApplication.DoesNotExist:
        # If no application exists
        status = 'Not Applied'
        application_exists = False
        applicatiion_date = False

    return render(request, 'docs/dashboard.html', {
        'status': status,
        'applicatiion_date': applicatiion_date,
        'application_exists': application_exists,
        'national_id_application': national_id_application if application_exists else None,
    })


# Apply for National ID
@login_required
@transaction.atomic
def apply_national_id(request):
    # Check if the user has an ongoing application
    existing_application = Application.objects.filter(user=request.user, status__in=['pending', 'processing', 'waiting', 'interview']).exists()

    if existing_application:
        messages.warning(request, "You already have an ongoing application. Please complete or cancel it before applying for another service.")
        return redirect('dashboard')

    if request.method == 'POST':
        try:
            full_name = request.POST.get('full_name')
            date_of_birth = request.POST.get('date_of_birth')
            place_of_birth = request.POST.get('place_of_birth')
            gender = request.POST.get('gender')
            address = request.POST.get('address')
            phone = request.POST.get('phone')
            email = request.POST.get('email')
            birth_certificate = request.FILES.get('birth_certificate')
            passport_photo = request.FILES.get('passport_photo')

            # Create the Application and National ID Application atomically
            application = Application.objects.create(
                user=request.user,
                application_type='new',
                status='pending',
            )

            NationalIDApplication.objects.create(
                application=application,
                full_name=full_name,
                date_of_birth=date_of_birth,
                place_of_birth=place_of_birth,
                gender=gender,
                address=address,
                phone=phone,
                email=email,
                birth_certificate=birth_certificate,
                passport_photo=passport_photo,
            )

            return redirect('dashboard')
        except Exception as e:
            # Handle exception and roll back transaction
            transaction.set_rollback(True)
            messages.error(request, "An error occurred while processing your application. Please try again.")
            return render(request, 'docs/apply_national_id.html')

    return render(request, 'docs/apply_national_id.html')


# View National ID Application
@login_required
def view_national_id(request, id):
    national_id_application = get_object_or_404(NationalIDApplication, id=id, application__user=request.user)
    return render(request, 'docs/view_national_id.html', {'application': national_id_application})


# Apply for Resident Permit
@login_required
@transaction.atomic
def apply_resident_permit(request):
    existing_application = Application.objects.filter(user=request.user, status__in=['pending', 'processing', 'waiting', 'interview']).exists()

    if existing_application:
        messages.warning(request, "You already have an ongoing application. Please complete or cancel it before applying for another service.")
        return redirect('dashboard')

    if request.method == 'POST':
        try:
            full_name = request.POST.get('full_name')
            date_of_birth = request.POST.get('date_of_birth')
            nationality = request.POST.get('nationality')
            address = request.POST.get('address')
            passport_photo = request.FILES.get('passport_photo')
            resident_permit_document = request.FILES.get('resident_permit_document')

            # Create the Application and Resident Permit Application atomically
            application = Application.objects.create(
                user=request.user,
                application_type='new',
                status='pending',
            )

            ResidentPermitApplication.objects.create(
                application=application,
                full_name=full_name,
                date_of_birth=date_of_birth,
                nationality=nationality,
                address=address,
                passport_photo=passport_photo,
                resident_permit_document=resident_permit_document,
            )

            return redirect('dashboard')
        except Exception as e:
            transaction.set_rollback(True)
            messages.error(request, "An error occurred while processing your application. Please try again.")
            return render(request, 'docs/apply_resident_permit.html')

    return render(request, 'docs/apply_resident_permit.html')


# View Resident Permit Application
@login_required
def view_resident_permit(request, id):
    resident_permit_application = get_object_or_404(ResidentPermitApplication, id=id, application__user=request.user)
    return render(request, 'docs/view_resident_permit.html', {'application': resident_permit_application})


# Apply for Work Permit
@login_required
@transaction.atomic
def apply_work_permit(request):
    existing_application = Application.objects.filter(user=request.user, status__in=['pending', 'processing', 'waiting', 'interview']).exists()

    if existing_application:
        messages.warning(request, "You already have an ongoing application. Please complete or cancel it before applying for another service.")
        return redirect('dashboard')

    if request.method == 'POST':
        try:
            full_name = request.POST.get('full_name')
            date_of_birth = request.POST.get('date_of_birth')
            nationality = request.POST.get('nationality')
            address = request.POST.get('address')
            job_title = request.POST.get('job_title')
            work_contract = request.FILES.get('work_contract')
            passport_photo = request.FILES.get('passport_photo')

            # Create the Application and Work Permit Application atomically
            application = Application.objects.create(
                user=request.user,
                application_type='new',
                status='pending',
            )

            WorkPermitApplication.objects.create(
                application=application,
                full_name=full_name,
                date_of_birth=date_of_birth,
                nationality=nationality,
                address=address,
                job_title=job_title,
                work_contract=work_contract,
                passport_photo=passport_photo,
            )

            return redirect('dashboard')
        except Exception as e:
            transaction.set_rollback(True)
            messages.error(request, "An error occurred while processing your application. Please try again.")
            return render(request, 'docs/apply_work_permit.html')

    return render(request, 'docs/apply_work_permit.html')


# View Work Permit Application
@login_required
def view_work_permit(request, id):
    work_permit_application = get_object_or_404(WorkPermitApplication, id=id, application__user=request.user)
    return render(request, 'docs/view_work_permit.html', {'application': work_permit_application})

@login_required
def fetch_application_details(request):
    application_id = request.GET.get('application_id')
    application_type = request.GET.get('application_type')

    application = get_object_or_404(Application, id=application_id, user=request.user)
    allow_cancel = application.status in ['pending', 'waiting']
    immigration_note = None

    if application.status == 'waiting':
        immigration_note = "Your application is waiting for more information. Please upload the required documents."

    if application_type == 'National ID Card':
        app_details = application.national_id_applications.first()
    elif application_type == 'Resident Permit':
        app_details = application.resident_permit_applications.first()
    elif application_type == 'Work Permit':
        app_details = application.work_permit_applications.first()

    html = render(request, 'docs/application_details.html', {
        'application': app_details,
        'application_type': application_type
    }).content.decode('utf-8')

    return JsonResponse({
        'html': html,
        'immigration_note': immigration_note,
        'allow_cancel': allow_cancel
    })


@login_required
def cancel_application(request):
    application_id = request.GET.get('application_id')
    application = get_object_or_404(Application, id=application_id, user=request.user)

    if application.status in ['pending', 'waiting']:
        application.status = 'cancelled'
        application.save()
        return JsonResponse({'success': True})

    return JsonResponse({'error': 'Application cannot be cancelled.'}, status=400)

@login_required
def upload_document(request, id):
    try:
        # Fetch the application
        application = NationalIDApplication.objects.get(id=id, application__user=request.user)

        # Only allow document upload if the status is "waiting"
        if application.application.status != 'waiting':
            return render(request, 'error.html', {'message': 'You can only upload documents when the application is waiting for more information.'})

        if request.method == 'POST':
            document_type = request.POST.get('document_type')
            document_file = request.FILES.get('document_file')

            # Create the document linked to the application
            UploadedDocument.objects.create(
                application=application.application,  # Link to base Application model
                document_type=document_type,
                document_file=document_file,
            )
            return redirect('dashboard')  # Redirect after successful upload

        # Fetch uploaded documents for this application
        uploaded_documents = UploadedDocument.objects.filter(application=application.application)

        return render(request, 'docs/upload_document.html', {
            'application': application,
            'uploaded_documents': uploaded_documents
        })

    except NationalIDApplication.DoesNotExist:
        return render(request, 'error.html', {'message': 'Application not found.'})
