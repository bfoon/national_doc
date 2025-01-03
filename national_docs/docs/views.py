from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import (NationalIDApplication,
                     UploadedDocument, Application,
                     ResidentPermitApplication,
                     WorkPermitApplication, Profile, ChatMessage, ExtendOrPrint,
                     Certification, BirthRegistration, MarriageDetails,
    DeathDetails, CharacterCertificate, AcademicCertificate,
    CertificationAttachment)
from django.core.files.storage import FileSystemStorage
from immigration.models import PostLocation, Fulfiller, FAQ, OfficerProfile
from finance.models import Token, TokenLog, UserRisk
from django.db import transaction
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from django.contrib.auth.models import User
from .models import Profile
from django.db import IntegrityError
from django.views.decorators.csrf import csrf_exempt
import json
from django.db.models import Q, Count
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import random
from twilio.rest import Client
from django.conf import settings
from django.core.mail import send_mail
from datetime import timedelta
import datetime
from django.http import JsonResponse, HttpResponseForbidden
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View


def landing_page(request):
    return render(request, 'docs/landing_page.html')

def login_page(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Log the user in
            login(request, user)

            # Redirect based on user group or superuser status
            if user.is_superuser:
                return redirect('dashboard')  # Superuser dashboard URL
            elif user.groups.filter(name__in=['immigration', 'police', 'tax', 'admin']).exists():
                return redirect('immigration_dashboard')  # Immigration dashboard URL
            elif user.groups.filter(name__in=['sysadmin']):
                return redirect('officer_profiles')
            elif user.groups.filter(name__in=['registrar']):
                return redirect('certificate_request')
            else:
                return redirect('dashboard')  # Default dashboard URL for other users

        else:
            # Add an error message and re-render the login page
            messages.warning(request, 'Invalid username or password')

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

@login_required
def dashboard(request):
    # National ID Application
    try:
        national_id_application = NationalIDApplication.objects.filter(application__user=request.user).latest('created_at')
        is_expired = national_id_application.application.status == 'complete' and national_id_application.application.is_expired()

        if is_expired:
            national_id_status = 'Not Applied'
            national_id_application_date = False
            national_id_application_exists = False
        else:
            national_id_status = national_id_application.application.status
            national_id_application_date = national_id_application.created_at
            national_id_application_exists = True
    except NationalIDApplication.DoesNotExist:
        national_id_status = 'Not Applied'
        national_id_application_exists = False
        national_id_application_date = False

    # Resident Permit Application
    try:
        resident_permit_application = ResidentPermitApplication.objects.filter(application__user=request.user).latest('created_at')
        resident_permit_status = resident_permit_application.application.status
        resident_permit_application_date = resident_permit_application.created_at
        resident_permit_application_exists = True
    except ResidentPermitApplication.DoesNotExist:
        resident_permit_status = 'Not Applied'
        resident_permit_application_exists = False
        resident_permit_application_date = False

    # Work Permit Application
    try:
        work_permit_application = WorkPermitApplication.objects.filter(application__user=request.user).latest('created_at')
        work_permit_status = work_permit_application.application.status
        work_permit_application_date = work_permit_application.created_at
        work_permit_application_exists = True
    except WorkPermitApplication.DoesNotExist:
        work_permit_status = 'Not Applied'
        work_permit_application_exists = False
        work_permit_application_date = False

    return render(request, 'docs/dashboard.html', {
        'national_id_status': national_id_status,
        'national_id_application_date': national_id_application_date,
        'national_id_application_exists': national_id_application_exists,
        'national_id_application': national_id_application if national_id_application_exists else None,

        'resident_permit_status': resident_permit_status,
        'resident_permit_application_date': resident_permit_application_date,
        'resident_permit_application_exists': resident_permit_application_exists,
        'resident_permit_application': resident_permit_application if resident_permit_application_exists else None,

        'work_permit_status': work_permit_status,
        'work_permit_application_date': work_permit_application_date,
        'work_permit_application_exists': work_permit_application_exists,
        'work_permit_application': work_permit_application if work_permit_application_exists else None,
    })

@login_required
def profile_view(request):
    try:
        # Fetch the appropriate profile
        profile = get_object_or_404(Profile, user=request.user)
    except:
        profile = get_object_or_404(OfficerProfile, user=request.user)

    # Check if the user belongs to any of the special groups
    user_groups = request.user.groups.values_list('name', flat=True)
    belongs_to_special_group = any(group in ['immigration', 'police', 'tax', 'registrar'] for group in user_groups)

    # Redirect to the appropriate URL if the user belongs to a special group
    if belongs_to_special_group:
        special_group_urls = {
            'immigration': '/immigration/dashboard/',
            'police': '/police/dashboard/',
            'tax': '/tax/dashboard/',
            'registrar': '/police/certificate_request/',
        }
        for group in user_groups:
            if group in special_group_urls:
                return redirect(special_group_urls[group])

    # Render the profile page for non-special group users
    return render(request, 'docs/profile.html', {
        'profile': profile,
        'belongs_to_special_group': belongs_to_special_group,
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
        try:
            profile = get_object_or_404(Profile, user=user)
        except:
            profile = get_object_or_404(OfficerProfile, user=user)

        profile.phone = phone
        profile.save()

        messages.success(request, 'Profile updated successfully!')
        return redirect('/profile')

    else:
        try:
            profile = get_object_or_404(Profile, user=request.user)
        except:
            profile = get_object_or_404(OfficerProfile, user=request.user)

        return render(request, 'docs/edit_profile.html', {
            'user': request.user,
            'profile': profile,
        })


@login_required
def send_edit_profile_otp(request):
    """Generates and sends an OTP via SMS or falls back to email if SMS fails."""
    user = request.user

    # Phone number and email setup
    phone_number = f"+220{user.profile.phone}" if user.profile.phone else None
    email = user.email

    if not phone_number and not email:
        messages.error(request, "No phone number or email associated with your profile.")
        return redirect('profile')

    # Generate a random 6-digit OTP
    otp = str(random.randint(100000, 999999))

    # Save OTP in session for verification
    request.session['otp'] = otp
    request.session['otp_phone_number'] = phone_number
    request.session['otp_email'] = email
    request.session['otp_attempts'] = 0
    request.session['otp_timestamp'] = timezone.now().strftime("%Y-%m-%d %H:%M:%S.%f%z")

    # Twilio credentials
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    twilio_number = settings.TWILIO_PHONE_NUMBER  # Normal SMS number, not WhatsApp

    client = Client(account_sid, auth_token)

    # Try sending OTP via SMS
    try:
        if phone_number:
            client.messages.create(
                from_=twilio_number,
                to=phone_number,
                body=f'Your OTP code to edit your profile is: {otp}. This code will expire in 5 minutes.'
            )
            messages.success(request, 'OTP sent successfully via SMS.')
            return redirect('verify_edit_profile_otp')
    except Exception as sms_error:
        # Fallback to email if SMS fails
        if email:
            try:
                subject = "Your OTP for Profile Edit"
                message = f"Your OTP code to edit your profile is: {otp}. This code will expire in 5 minutes."
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])
                messages.warning(request, 'SMS failed. OTP sent via email.')
                return redirect('verify_edit_profile_otp')
            except Exception as email_error:
                messages.warning(request, f"Failed to send OTP via email: {email_error}")
                return redirect('profile')

        # If both SMS and email fail
        messages.error(request, f"Failed to send OTP via SMS: {sms_error}")
        return redirect('/profile')

@login_required
def verify_edit_profile_otp(request):
    """Verifies the OTP before allowing profile editing with a 3-attempt limit and 3-minute expiry."""
    max_attempts = 3  # Maximum number of attempts allowed
    otp_expiry_time = 3  # OTP expiry time in minutes

    # Initialize or fetch the attempt count and timestamp from session
    if 'otp_attempts' not in request.session:
        request.session['otp_attempts'] = 0

    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        saved_otp = request.session.get('otp')
        otp_timestamp_str = request.session.get('otp_timestamp')  # OTP generation time as string

        # Check if OTP or timestamp is missing
        if not saved_otp or not otp_timestamp_str:
            messages.warning(request, "OTP has expired. Please request a new one.")
            return redirect('/profile')

        # Convert the stored timestamp string back to a timezone-aware datetime object
        otp_timestamp = datetime.datetime.strptime(otp_timestamp_str, "%Y-%m-%d %H:%M:%S.%f%z")

        # Check if the OTP has expired
        if timezone.now() > otp_timestamp + timedelta(minutes=otp_expiry_time):
            messages.warning(request, "OTP has expired. Please request a new one.")
            # Clear expired OTP and session attempts
            request.session.pop('otp', None)
            request.session.pop('otp_attempts', None)
            request.session.pop('otp_timestamp', None)
            return redirect('/profile')

        # Check if the user has exceeded the maximum attempts
        if request.session['otp_attempts'] >= max_attempts:
            messages.warning(request, "You've exceeded the maximum number of OTP attempts.")

            # Send security email to user
            subject = "Suspicious Activity on Your Profile"
            message = f"""
            Dear {request.user.get_full_name()},

            We noticed multiple failed attempts to edit your profile information. If this was not you, 
            please take immediate action to secure your account.

            Contact our support team if you suspect any unauthorized activity.

            Regards,  
            The Gambia Immigration Office  
            """
            recipient_email = request.user.email
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [recipient_email])

            # Clear OTP and attempt count from session
            request.session.pop('otp', None)
            request.session.pop('otp_attempts', None)
            request.session.pop('otp_timestamp', None)
            return redirect('/profile')

        # Verify the entered OTP
        if entered_otp == saved_otp:
            # OTP verified successfully
            request.session.pop('otp', None)
            request.session.pop('otp_attempts', None)
            request.session.pop('otp_timestamp', None)
            messages.success(request, "OTP verified successfully.")
            return redirect('edit_profile')
        else:
            # Increment attempt count and display error
            request.session['otp_attempts'] += 1
            remaining_attempts = max_attempts - request.session['otp_attempts']
            messages.warning(request, f"Invalid OTP. {remaining_attempts} attempt(s) remaining.")

    return render(request, 'docs/verify_edit_profile_otp.html')

@login_required
@transaction.atomic
def apply_national_id(request):
    # Check if the user has an ongoing application
    existing_application = Application.objects.filter(user=request.user, status__in=['pending', 'processing', 'waiting',
                                                                                     'interview']).exists()

    if existing_application:
        messages.warning(request,
                         "You already have an ongoing application. Please complete or cancel it before applying for another service.")
        return redirect('dashboard')

    # Check if the user's account is marked as risky
    risk, created = UserRisk.objects.get_or_create(user=request.user)
    if risk.is_risky:
        messages.error(request,
                       "Your account is marked as risky due to multiple failed attempts. Please resolve this before proceeding.")
        return redirect('dashboard')

    # Check if there is a verification log for this user
    verification_log_exists = TokenLog.objects.filter(token__user=request.user, activity='Token verified').exists()
    if not verification_log_exists:
        messages.error(request, "You need to verify your payment token before proceeding with the application.")
        return redirect('dashboard')

    # Prevent foreign nationals from applying for a National ID
    nationality = getattr(request.user.profile, 'nationality', None)
    if nationality and nationality.lower() == 'foreigner':
        messages.warning(request, "Foreign nationals cannot apply for a National ID.")
        return redirect('dashboard')

    # Get available post locations for the dropdown
    post_locations = PostLocation.objects.all()

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
            post_location_id = request.POST.get('post-location')  # Get selected post location
            post_location = get_object_or_404(PostLocation, id=post_location_id)  # Fetch post location

            # Create the Application atomically
            application = Application.objects.create(
                user=request.user,
                application_type='new',
                status='pending',
                post_location=post_location  # Save selected post location
            )

            # Create the National ID Application
            national_id_application = NationalIDApplication.objects.create(
                application=application,
                full_name=full_name,
                date_of_birth=date_of_birth,
                place_of_birth=place_of_birth,
                gender=gender,
                address=address,
                phone_number=phone,
                email=email,
                birth_certificate=birth_certificate,
                passport_photo=passport_photo,
            )

            # Create the Fulfiller instance
            Fulfiller.objects.create(
                application=application,
                location=post_location,  # Assuming you want to link it to the same post location
                action=request.user,  # Assuming the user submitting is the one taking action
                status='open',  # Default status for the fulfiller
                progress=0  # Default progress
            )
            # Try to retrieve the token, checking if it's not already used
            token = Token.objects.select_for_update().get(user=request.user, is_used=False)

            # Mark the token as verified
            token.is_used = True
            token.save()
            messages.success(request, "Your National ID application has been submitted.")
            return redirect('dashboard')

        except Exception as e:
            # Rollback if any exception occurs
            transaction.set_rollback(True)
            messages.warning(request, "An error occurred while processing your application. Please try again.")
            return render(request, 'docs/apply_national_id.html', {'post_locations': post_locations})

    return render(request, 'docs/apply_national_id.html', {'post_locations': post_locations})

@login_required
def apply_resident_permit(request):
    # Fetch the user's profile
    profile = get_object_or_404(Profile, user=request.user)

    # Nationals cannot apply for resident permits
    if profile.nationality == 'national':
        messages.warning(request, "Nationals cannot apply for a resident permit.")
        return redirect('dashboard')

        # Check if the user has an ongoing application
    existing_application = Application.objects.filter(user=request.user, status__in=['pending', 'processing', 'waiting',
                                                                                     'interview']).exists()

    if existing_application:
        messages.warning(request,
                         "You already have an ongoing application. Please complete or cancel it before applying for another service.")
        return redirect('dashboard')

    # Check if the user's account is marked as risky
    risk, created = UserRisk.objects.get_or_create(user=request.user)
    if risk.is_risky:
        messages.error(request,
                       "Your account is marked as risky due to multiple failed attempts. Please resolve this before proceeding.")
        return redirect('dashboard')

    # Check if there is a verification log for this user
    verification_log_exists = TokenLog.objects.filter(token__user=request.user, activity='Token verified').exists()
    if not verification_log_exists:
        messages.error(request, "You need to verify your payment token before proceeding with the application.")
        return redirect('dashboard')

    # Get available post locations
    post_locations = PostLocation.objects.all()

    if request.method == 'POST':
        # Start atomic transaction
        with transaction.atomic():
            try:
                full_name = request.POST.get('full-name')
                date_of_birth = request.POST.get('date-of-birth')
                nationality = request.POST.get('nationality')
                passport_number = request.POST.get('passport-number')
                date_of_entry = request.POST.get('date-of-entry')
                purpose_of_stay = request.POST.get('purpose-of-stay')
                address = request.POST.get('address')
                email = request.POST.get('email')
                phone = request.POST.get('phone')
                passport_photo = request.FILES.get('passport-photo')
                resident_permit_document = request.FILES.get('resident-permit-document')
                post_location_id = request.POST.get('post-location')  # Get selected post location

                # Fetch the post location object
                post_location = get_object_or_404(PostLocation, id=post_location_id)

                # Create the Application atomically
                application = Application.objects.create(
                    user=request.user,
                    application_type='new',
                    status='pending',
                    post_location=post_location  # Save selected post location
                )

                # Create the Resident Permit Application
                resident_permit_application = ResidentPermitApplication.objects.create(
                    application=application,
                    full_name=full_name,
                    date_of_birth=date_of_birth,
                    nationality=nationality,
                    passport_number=passport_number,
                    date_of_entry=date_of_entry,
                    purpose_of_stay=purpose_of_stay,
                    address=address,
                    phone_number=phone,
                    email=email,
                    passport_photo=passport_photo,
                    resident_permit_document=resident_permit_document,
                )

                # Create the Fulfiller instance
                Fulfiller.objects.create(
                    application=application,
                    location=post_location,  # Link to the post location
                    action=request.user,  # Assuming the user submitting is the one taking action
                    status='open',  # Default status for the fulfiller
                    progress=0  # Default progress
                )
                # Try to retrieve the token, checking if it's not already used
                token = Token.objects.select_for_update().get(user=request.user, is_used=False)

                # Mark the token as verified
                token.is_used = True
                token.save()
                messages.success(request, "Your Resident Permit application has been submitted.")
                return redirect('dashboard')

            except Exception as e:
                # If any error occurs, rollback the transaction
                transaction.set_rollback(True)
                messages.error(request, f"An error occurred: {str(e)}. Please try again.")
                return render(request, 'docs/apply_resident_permit.html', {'post_locations': post_locations})

    # Render the form with post locations available for selection
    return render(request, 'docs/apply_resident_permit.html', {'post_locations': post_locations})

@login_required
@transaction.atomic
def apply_work_permit(request):
    profile = get_object_or_404(Profile, user=request.user)

    if profile.nationality == 'national':
        messages.warning(request, "Nationals cannot apply for a work permit.")
        return redirect('dashboard')

    existing_application = Application.objects.filter(user=request.user, status__in=['pending', 'processing', 'waiting', 'interview']).exists()

    if existing_application:
        messages.warning(request, "You already have an ongoing application. Please complete or cancel it before applying for another service.")
        return redirect('dashboard')

    # Check if the user's account is marked as risky
    risk, created = UserRisk.objects.get_or_create(user=request.user)
    if risk.is_risky:
        messages.error(request,
                        "Your account is marked as risky due to multiple failed attempts. Please resolve this before proceeding.")
        return redirect('dashboard')

    # Check if there is a verification log for this user
    verification_log_exists = TokenLog.objects.filter(token__user=request.user, activity='Token verified').exists()
    if not verification_log_exists:
        messages.error(request, "You need to verify your payment token before proceeding with the application.")
        return redirect('dashboard')

    if request.method == 'POST':
        try:
            full_name = request.POST.get('full_name')
            date_of_birth = request.POST.get('date_of_birth')
            nationality = request.POST.get('nationality')
            address = request.POST.get('address')
            phone = request.POST.get('phone')
            job_title = request.POST.get('job_title')
            work_contract = request.FILES.get('work_contract')
            passport_photo = request.FILES.get('passport_photo')
            post_location_id = request.POST.get('post_location')  # Get selected post location

            # Fetch the post location object
            post_location = get_object_or_404(PostLocation, id=post_location_id)

            # Create the Application atomically
            application = Application.objects.create(
                user=request.user,
                application_type='new',
                status='pending',
                post_location=post_location  # Save selected post location
            )

            # Create the Work Permit Application
            work_permit_application = WorkPermitApplication.objects.create(
                application=application,
                full_name=full_name,
                date_of_birth=date_of_birth,
                nationality=nationality,
                address=address,
                phone_number=phone,
                job_title=job_title,
                work_contract=work_contract,
                passport_photo=passport_photo,
            )

            # Create the Fulfiller instance
            Fulfiller.objects.create(
                application=application,
                location=post_location,  # Link to the post location
                action=request.user,  # Assuming the user submitting is the one taking action
                status='open',  # Default status for the fulfiller
                progress=0  # Default progress
            )
            # Try to retrieve the token, checking if it's not already used
            token = Token.objects.select_for_update().get(user=request.user, is_used=False)

            # Mark the token as verified
            token.is_used = True
            token.save()
            messages.success(request, "Your Work Permit application has been submitted.")
            return redirect('dashboard')

        except Exception as e:
            # If any error occurs, rollback the transaction
            transaction.set_rollback(True)
            messages.error(request, f"An error occurred while processing your application: {str(e)}. Please try again.")
            return render(request, 'docs/apply_work_permit.html')

    # Render the form with post locations available for selection
    post_locations = PostLocation.objects.all()
    return render(request, 'docs/apply_work_permit.html', {'post_locations': post_locations})

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
        # Fetch the NationalIDApplication for the user
        application = Application.objects.get(id=id, user=request.user)

        # Only allow document upload if the status is "waiting"
        if application.status != 'waiting':
            return render(request, 'docs/error.html', {
                'message': 'You can only upload documents when the application is waiting for more information.'
            })

        if request.method == 'POST':
            # Ensure document_file is included in the request
            document_type = request.POST.get('document_type')
            document_file = request.FILES.get('document_file')

            if not document_file:
                messages.error(request, 'Please upload a document.')
                return redirect('upload_document', id=id)

            # Create the document linked to the application
            UploadedDocument.objects.create(
                application=application,  # Link to the base Application model
                document_type=document_type,
                document_file=document_file,
            )

            messages.success(request, 'Document uploaded successfully.')
            return redirect('dashboard')  # Redirect after successful upload

        # Fetch uploaded documents for this application
        uploaded_documents = UploadedDocument.objects.filter(application=application)

        return render(request, 'docs/upload_document.html', {
            'application': application,
            'uploaded_documents': uploaded_documents
        })

    except NationalIDApplication.DoesNotExist:
        return render(request, 'docs/error.html', {'message': 'Application not found.'})

@login_required
def apply_extend_or_reprint(request, application_id):
    application = get_object_or_404(Application, id=application_id, user=request.user)

    if request.method == 'POST':
        state = request.POST.get('state')
        reason = request.POST.get('reason')
        upload = request.FILES.get('upload')

        # Validate state
        if state not in ['reprint', 'extend']:
            messages.error(request, "Invalid request type. Please select 'Re-Print' or 'Extend'.")
            return redirect('apply_extend_or_reprint', application_id=application.id)

        # Create ExtendOrPrint instance
        extend_or_reprint_request = ExtendOrPrint.objects.create(
            application=application,
            state=state,
            reason=reason,
            upload=upload
        )

        messages.success(request, f"Your {state.capitalize()} request has been submitted successfully.")
        return redirect('dashboard', application_id=application.id)

    return render(request, 'docs/apply_extend_or_reprint.html', {'application': application})

@login_required
@csrf_exempt
def chat_with_support(request):
    support_user = User.objects.filter(is_staff=True).first()  # Assuming the first staff user is support

    if request.method == 'POST':
        data = json.loads(request.body)
        message_text = data.get('message')
        if message_text and support_user:
            ChatMessage.objects.create(sender=request.user, recipient=support_user, message=message_text)
            return JsonResponse({'status': 'success'})
        return JsonResponse({'status': 'error', 'message': 'Failed to send message.'})

    # Fetch only unread chat history
    messages = ChatMessage.objects.filter(
        (Q(sender=request.user, recipient=support_user) |
         Q(sender=support_user, recipient=request.user)),
        is_read=False  # Exclude read messages
    ).order_by('timestamp')

    chat_data = [
        {
            'sender': msg.sender.username,
            'message': msg.message,
            'timestamp': msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        }
        for msg in messages
    ]

    return JsonResponse({'messages': chat_data})

@login_required
def faq_list(request):
    query = request.GET.get('q', '')
    faqs = FAQ.objects.filter(question__icontains=query) if query else FAQ.objects.all()

    # Paginate the FAQ list
    paginator = Paginator(faqs, 5)  # Show 5 FAQs per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'faqs': page_obj,
        'query': query,
    }
    return render(request, 'docs/faq_list.html', context)

@login_required
def manage_appointments(request):
    return render(request, 'docs/manage_appointments.html')


@csrf_exempt
def verify_token(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format."}, status=400)

        token_value = data.get("token")
        ip_address = get_client_ip(request)

        if not token_value:
            return JsonResponse({"error": "Token is required"}, status=400)

        # Get or create the user risk object
        risk, created = UserRisk.objects.get_or_create(user=request.user)

        # Check if account is marked as risky before proceeding
        if risk.is_risky:
            return JsonResponse({"error": "Account is marked as risky due to multiple failed attempts."}, status=403)

        try:
            with transaction.atomic():
                # Try to retrieve the token, checking if it's not already used
                token = Token.objects.select_for_update().get(token=token_value, is_used=False)

                # Create a log for successful verification
                TokenLog.objects.create(token=token, ip_address=ip_address, activity="Token verified")

                # Return success response
                return JsonResponse({"success": True, "token": token.token, "amount": token.amount})

        except Token.DoesNotExist:
            # Log failed attempt if the token is invalid or already used
            TokenLog.objects.create(token=None, ip_address=ip_address,
                                    activity=f"Failed attempt with token {token_value}")

            # Increment failed attempts and mark account as risky if necessary
            risk.increment_failed_attempts()

            # If account reaches the threshold, mark it as risky
            if risk.is_risky:
                return JsonResponse({"error": "Account is marked as risky due to multiple failed attempts."},
                                    status=403)

            return JsonResponse({"error": "Invalid or already used token."}, status=404)

    return HttpResponseForbidden("Invalid request method.")

def get_client_ip(request):
    """Helper function to get the client's IP address."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip

class CertificationView(LoginRequiredMixin, ListView):
    model = Certification
    template_name = 'docs/certificate_request.html'
    context_object_name = 'certifications'
    paginate_by = 5

    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('search', '')
        status_filter = self.request.GET.get('status', '')

        if search_query:
            queryset = queryset.filter(applicant_name__icontains=search_query)

        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)

        return queryset.order_by('-submission_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get the queryset
        queryset = self.get_queryset()

        # Get current page number
        page = self.request.GET.get('page', 1)
        paginator = Paginator(queryset, self.paginate_by)

        try:
            certifications = paginator.page(page)
        except PageNotAnInteger:
            certifications = paginator.page(1)
        except EmptyPage:
            certifications = paginator.page(paginator.num_pages)

        # Calculate visible page range
        page_number = certifications.number
        total_pages = paginator.num_pages

        # Show 2 pages before and after the current page
        page_range = range(max(page_number - 2, 1), min(page_number + 3, total_pages + 1))

        # Get statistics
        stats = Certification.objects.aggregate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='approved')),
            pending=Count('id', filter=Q(status='pending')),
            rejected=Count('id', filter=Q(status='rejected'))
        )

        # Calculate percentages
        if stats['total'] > 0:
            stats['approved_percentage'] = round((stats['approved'] / stats['total']) * 100, 1)
            stats['rejected_percentage'] = round((stats['rejected'] / stats['total']) * 100, 1)
        else:
            stats['approved_percentage'] = 0
            stats['rejected_percentage'] = 0

        # Get all query parameters for maintaining filters in pagination
        query_params = self.request.GET.copy()
        if 'page' in query_params:
            del query_params['page']

        context.update({
            'stats': stats,
            'search_query': self.request.GET.get('search', ''),
            'status_filter': self.request.GET.get('status', ''),
            'certificate_types': Certification.CERTIFICATE_TYPES,
            'attachment_types': CertificationAttachment.ATTACHMENT_TYPES,
            'certifications': certifications,
            'page_range': page_range,
            'query_params': query_params.urlencode(),
            'total_pages': total_pages,
            'start_index': certifications.start_index(),
            'end_index': certifications.end_index(),
            'total_count': paginator.count,
        })
        return context

@login_required
def create_certification(request):
    if request.method == 'POST':
        cert_type = request.POST.get('certificate_type')

        try:
            # Create base certification
            certification = Certification.objects.create(
                certificate_type=cert_type,
                applicant_name=request.POST.get('applicant_name'),
                applicant_email=request.POST.get('applicant_email'),
                applicant_phone=request.POST.get('applicant_phone'),
                purpose=request.POST.get('purpose'),
                submitted_by=request.user
            )

            # Handle specific certificate type details
            if cert_type == 'birth':
                BirthRegistration.objects.create(
                    certification=certification,
                    date_of_birth=request.POST.get('date_of_birth'),
                    place_of_birth=request.POST.get('place_of_birth'),
                    time_of_birth=request.POST.get('time_of_birth'),
                    father_name=request.POST.get('father_name'),
                    mother_name=request.POST.get('mother_name'),
                    sex=request.POST.get('sex')
                )
            elif cert_type == 'marriage':
                MarriageDetails.objects.create(
                    certification=certification,
                    # Spouse Information
                    spouse1_name=request.POST.get('spouse1_name'),
                    spouse2_name=request.POST.get('spouse2_name'),
                    marriage_date=request.POST.get('marriage_date'),
                    marriage_place=request.POST.get('marriage_place'),
                    marriage_type=request.POST.get('marriage_type'),
                    marriage_status=request.POST.get('marriage_status'),

                    # Witness Information
                    witness1_name=request.POST.get('witness1_name'),
                    witness2_name=request.POST.get('witness2_name'),

                    # Additional Information
                    officiant_name=request.POST.get('officiant_name', ''),
                    ceremony_place=request.POST.get('ceremony_place', ''),
                    remarks=request.POST.get('remarks', '')
                )
            elif cert_type == 'death':
                DeathDetails.objects.create(
                    certification=certification,
                    full_name=request.POST.get('full_name'),
                    date_of_death=request.POST.get('date_of_death'),
                    place_of_death=request.POST.get('place_of_death'),
                    cause_of_death=request.POST.get('cause_of_death')
                )

            # Handle file attachments
            for file in request.FILES.getlist('attachments'):
                CertificationAttachment.objects.create(
                    certification=certification,
                    file=file,
                    attachment_type=request.POST.get('attachment_type')
                )

            messages.success(request, 'Certificate request submitted successfully!')
            return redirect('docs:certificate_list')

        except Exception as e:
            messages.error(request, f'Error submitting certificate request: {str(e)}')
            return redirect('docs:certificate_list')

    return render(request, 'certifications/certificate_form.html')

class CertificationDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        certification = Certification.objects.get(pk=pk)
        specific_details = None

        if certification.certificate_type == 'birth':
            specific_details = certification.birth_registration
        elif certification.certificate_type == 'marriage':
            specific_details = certification.marriage_details
        elif certification.certificate_type == 'death':
            specific_details = certification.death_details

        context = {
            'certification': certification,
            'specific_details': specific_details,
            'attachments': certification.attachments.all()
        }
        return render(request, 'certificates/certification_detail.html', context)

def download_certificate(request, certificate_id):
    # Add logic for generating and downloading certificate
    return redirect(f'/immigration/certificate/print/{certificate_id}/', )


def track_certificate(request, pk):
    # Add logic for tracking certificate status
    pass


def appeal_certificate(request, pk):
    # Add logic for handling certificate appeals
    pass


def update_certification_status(request, pk):
    if request.method == 'POST' and request.user.is_staff:
        certification = Certification.objects.get(pk=pk)
        new_status = request.POST.get('status')
        if new_status in dict(Certification.STATUS_CHOICES):
            certification.status = new_status
            certification.approved_by = request.user if new_status == 'approved' else None
            certification.save()
            messages.success(request, f'Certificate status updated to {new_status}')
        return redirect('docs:certificate_detail', pk=pk)