from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import (NationalIDApplication,
                     UploadedDocument, Application,
                     ResidentPermitApplication, WorkPermitApplication, Profile)
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from django.contrib.auth.models import User
from .models import Profile
from django.db import IntegrityError

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

@transaction.atomic  # Atomic transaction to ensure rollback if something goes wrong
def register(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        date_of_birth = request.POST.get('dateOfBirth')
        nationality = request.POST.get('nationality')
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirmPassword')

        # Validate email format
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Invalid email address.')
            return redirect('register')

        # Ensure passwords match
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect('register')

        try:
            # Begin atomic transaction
            with transaction.atomic():
                # Check if the user already exists before creating
                if User.objects.filter(username=username).exists():
                    messages.error(request, "Username already exists.")
                    return redirect('register')

                # Create the user
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    email=email,
                    first_name=first_name,
                    last_name=last_name
                )

                # Check if the profile already exists for the user before creating
                if not Profile.objects.filter(user=user).exists():
                    # Create and save the profile
                    Profile.objects.create(
                        user=user,
                        date_of_birth=date_of_birth,
                        nationality=nationality
                    )
                else:
                    messages.error(request, "Profile already exists for this user.")
                    return redirect('register')

            # Automatically log the user in after registration
            login(request, user)
            messages.success(request, 'Registration successful! You are now logged in.')
            return redirect('/dashboard')

        except IntegrityError as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect('register')

    return render(request, 'docs/registration.html')

def logout_view(request):
    logout(request)  # This will log out the user
    return redirect('landing_page')  # Redirect to the landing page after logout

# Dashboard View
@login_required
def dashboard(request):
    try:
        national_id_application = NationalIDApplication.objects.get(application__user=request.user)
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
        status = 'Not Applied'
        application_exists = False
        applicatiion_date = False

    return render(request, 'docs/dashboard.html', {
        'status': status,
        'applicatiion_date': applicatiion_date,
        'application_exists': application_exists,
        'national_id_application': national_id_application if application_exists else None,
    })

@login_required
def profile_view(request):
    # Get the user's profile
    profile = get_object_or_404(Profile, user=request.user)

    return render(request, 'docs/profile.html', {
        'profile': profile
    })

@login_required
def edit_profile(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')

        # Validate email format
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Invalid email address.')
            return redirect('/edit_profile')

        # Update user info
        user = request.user
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.save()

        # Update profile phone number
        profile, created = Profile.objects.get_or_create(user=user)
        profile.phone = phone
        profile.save()

        messages.success(request, 'Profile updated successfully!')
        return redirect('/profile')

    else:
        profile, created = Profile.objects.get_or_create(user=request.user)
        return render(request, 'docs/edit_profile.html', {
            'user': request.user,
            'profile': profile,
        })

@login_required
@transaction.atomic
def apply_national_id(request):
    # Check if the user has an ongoing application
    existing_application = Application.objects.filter(user=request.user, status__in=['pending', 'processing', 'waiting', 'interview']).exists()

    if existing_application:
        messages.warning(request, "You already have an ongoing application. Please complete or cancel it before applying for another service.")
        return redirect('dashboard')

    # Prevent foreign nationals from applying for a National ID
    if request.user.profile.nationality.lower() == 'foreigner':
        messages.warning(request, "Foreign nationals cannot apply for a National ID.")
        return redirect('dashboard')

    if request.method == 'POST':
        try:
            full_name = request.POST.get('full-name')
            date_of_birth = request.POST.get('date-of-birth')
            place_of_birth = request.POST.get('place-of-birth')
            gender = request.POST.get('gender')
            address = request.POST.get('address')
            phone = request.POST.get('phone')
            email = request.POST.get('email')
            birth_certificate = request.FILES.get('birth-certificate')
            passport_photo = request.FILES.get('passport-photo')

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

            messages.success(request, "Your National ID application has been submitted.")
            return redirect('dashboard')

        except Exception as e:
            transaction.set_rollback(True)
            messages.error(request, "An error occurred while processing your application. Please try again.")
            return render(request, 'docs/apply_national_id.html')

    return render(request, 'docs/apply_national_id.html')


# Apply for Resident Permit
@login_required
@transaction.atomic
def apply_resident_permit(request):
    profile = Profile.objects.get(user=request.user)

    if profile.nationality == 'national':
        messages.warning(request, "Nationals cannot apply for a resident permit.")
        return redirect('dashboard')

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


# Apply for Work Permit
@login_required
@transaction.atomic
def apply_work_permit(request):
    profile = Profile.objects.get(user=request.user)

    if profile.nationality == 'national':
        messages.warning(request, "Nationals cannot apply for a work permit.")
        return redirect('dashboard')

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
