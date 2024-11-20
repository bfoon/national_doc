from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.models import User
from immigration.models import OfficerProfile, PostLocation
from docs.models import Profile
from django.contrib import messages
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User


@login_required
def officer_profile_list(request):
    # Fetch officer and normal profiles
    officer_profiles = OfficerProfile.objects.select_related('user', 'post_location').all()
    user_profiles = Profile.objects.select_related('user').all()

    # Combine profiles in a single list
    combined_profiles = []
    for officer in officer_profiles:
        combined_profiles.append({
            'type': 'officer',
            'username': officer.user.username,
            'email': officer.user.email,
            'phone': officer.phone,
            'batch_number': officer.officer_batch_number,
            'post_location': officer.post_location,
            'profile_picture': officer.profile_picture,
            'id': officer.user.id  # Assuming 'id' for actions
        })

    for profile in user_profiles:
        combined_profiles.append({
            'type': 'user',
            'username': profile.user.username,
            'email': profile.user.email,
            'phone': profile.phone,
            'date_of_birth': profile.date_of_birth,
            'nationality': profile.nationality,
            'id': profile.user.id  # Assuming 'id' for actions
        })

    # Paginate profiles list
    paginator = Paginator(combined_profiles, 10)  # Show 10 profiles per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'system_admin/officer_profile_list.html', {'page_obj': page_obj})

@login_required
def view_profile(request, user_id):
    user = get_object_or_404(User, id=user_id)
    officer_profile = getattr(user, 'officerprofile', None)
    user_profile = getattr(user, 'profile', None)
    profile = officer_profile or user_profile

    return render(request, 'system_admin/view_profile.html', {'profile': profile})

@login_required
def edit_profile(request, user_id):
    user = get_object_or_404(User, id=user_id)
    officer_profile = getattr(user, 'officerprofile', None)
    user_profile = getattr(user, 'profile', None)
    profile = officer_profile or user_profile

    if request.method == 'POST':
        # Extract and assign data manually
        profile.user.username = request.POST.get('username')
        profile.user.email = request.POST.get('email')

        if officer_profile:
            profile.phone = request.POST.get('phone')
            profile.officer_batch_number = request.POST.get('officer_batch_number')
            profile.post_location_id = request.POST.get('post_location')
        elif user_profile:
            profile.phone = request.POST.get('phone')
            profile.date_of_birth = request.POST.get('date_of_birth')
            profile.nationality = request.POST.get('nationality')

        profile.user.save()
        profile.save()
        return redirect('officer_profile_list')

    return render(request, 'system_admin/edit_profile.html', {'profile': profile})

@login_required
def delete_profile(request, user_id):
    user = get_object_or_404(User, id=user_id)
    officer_profile = getattr(user, 'officerprofile', None)
    user_profile = getattr(user, 'profile', None)
    profile = officer_profile or user_profile

    if request.method == 'POST':  # Confirm deletion
        if profile:
            profile.delete()
        user.delete()  # Optionally delete the user as well, if appropriate
        return redirect('officer_profile_list')

    return render(request, 'system_admin/delete_profile.html', {'profile': profile})

@login_required
@transaction.atomic
def add_officer_profile(request):
    if request.method == 'POST':
        data = request.POST
        profile_picture = request.FILES.get('profile_picture')
        user_id = data.get('user_id')
        phone = data.get('phone')
        officer_batch_number = data.get('officer_batch_number')
        post_location_id = data.get('post_location_id')

        user = get_object_or_404(User, id=user_id)
        post_location = PostLocation.objects.get(id=post_location_id) if post_location_id else None

        # Create OfficerProfile
        OfficerProfile.objects.create(
            user=user,
            profile_picture=profile_picture,
            phone=phone,
            officer_batch_number=officer_batch_number,
            post_location=post_location,
        )
        messages.success(request, "Officer Profile created successfully!")
        return redirect('officer_profile_list')

    users = User.objects.all()
    post_locations = PostLocation.objects.all()
    return render(request, 'system_admin/add_officer_profile.html', {'users': users, 'post_locations': post_locations})

@login_required
def edit_officer_profile(request, pk):
    officer_profile = get_object_or_404(OfficerProfile, pk=pk)
    if request.method == 'POST':
        data = request.POST
        officer_profile.profile_picture = request.FILES.get('profile_picture', officer_profile.profile_picture)
        officer_profile.phone = data.get('phone')
        officer_profile.officer_batch_number = data.get('officer_batch_number')
        officer_profile.post_location_id = data.get('post_location_id')

        officer_profile.save()
        messages.success(request, "Officer Profile updated successfully!")
        return redirect('officer_profile_list')

    users = User.objects.all()
    post_locations = PostLocation.objects.all()
    return render(request, 'system_admin/edit_officer_profile.html', {
        'officer_profile': officer_profile,
        'users': users,
        'post_locations': post_locations,
    })


# List view
@login_required
def profile_list(request):
    profiles = Profile.objects.all()
    return render(request, 'system_admin/profile_list.html', {'profiles': profiles})


# Add view
@login_required
def add_profile(request):
    if request.method == 'POST':
        data = request.POST
        user_id = data.get('user_id')
        date_of_birth = data.get('date_of_birth')
        nationality = data.get('nationality')
        phone = data.get('phone')

        user = get_object_or_404(User, id=user_id)

        # Create Profile
        Profile.objects.create(
            user=user,
            date_of_birth=date_of_birth,
            nationality=nationality,
            phone=phone,
        )
        messages.success(request, "Profile created successfully!")
        return redirect('profile_list')

    users = User.objects.all()
    return render(request, 'system_admin/add_profile.html', {'users': users})


# Edit view
@login_required
def edit_profile(request, pk):
    profile = get_object_or_404(Profile, pk=pk)
    if request.method == 'POST':
        data = request.POST
        profile.date_of_birth = data.get('date_of_birth')
        profile.nationality = data.get('nationality')
        profile.phone = data.get('phone')
        profile.save()

        messages.success(request, "Profile updated successfully!")
        return redirect('profile_list')

    return render(request, 'system_admin/edit_profile.html', {'profile': profile})