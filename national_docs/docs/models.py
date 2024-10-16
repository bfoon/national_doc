from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    date_of_birth = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=50, null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

# @receiver(post_save, sender=User)
# def create_user_profile(sender, instance, created, **kwargs):
#     if created:
#         Profile.objects.create(user=instance)
#
#
# @receiver(post_save, sender=User)
# def save_user_profile(sender, instance, **kwargs):
#     instance.profile.save()

class InterviewSlot(models.Model):
    date_time = models.DateTimeField(unique=True)  # Date and time of the interview slot
    max_interviewees = models.IntegerField(default=10)  # Maximum number of interviews allowed in this slot
    current_interviewees = models.IntegerField(default=0)  # Track how many have been assigned

    def has_available_slots(self):
        """Returns True if this slot has available spots."""
        return self.current_interviewees < self.max_interviewees

    def __str__(self):
        return f"Interview Slot: {self.date_time} - {self.current_interviewees}/{self.max_interviewees} filled"

class Application(models.Model):
    APPLICATION_TYPE_CHOICES = [
        ('new', 'New Application'),
        ('extension', 'Extension'),
    ]

    APPLICATION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('waiting', 'Waiting'),
        ('interview', 'Interview'),
        ('completed', 'Completed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    application_type = models.CharField(max_length=50, choices=APPLICATION_TYPE_CHOICES)
    application_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=50, choices=APPLICATION_STATUS_CHOICES, default='pending')
    interview_slot = models.ForeignKey(InterviewSlot, on_delete=models.SET_NULL, null=True, blank=True)
    interview_queue_number = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"Application {self.id} - {self.application_type} for {self.user.username}"

    def get_service_type(self):
        """Get the type of service based on the related models."""
        if hasattr(self, 'national_id_applications'):
            return "National ID"
        elif hasattr(self, 'resident_permit_applications'):
            return "Resident Permit"
        elif hasattr(self, 'work_permit_applications'):
            return "Work Permit"
        elif hasattr(self, 'drivers_license_applications'):
            return "Driver's License"
        elif hasattr(self, 'tin_applications'):
            return "TIN"
        return "Unknown Service"

class NationalIDApplication(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, null=True, related_name='national_id_applications')
    full_name = models.CharField(max_length=255)
    date_of_birth = models.DateField()
    place_of_birth = models.CharField(max_length=255)
    gender = models.CharField(max_length=10, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')])
    address = models.TextField()
    phone = models.CharField(max_length=15)
    email = models.EmailField()
    birth_certificate = models.FileField(upload_to='documents/birth_certificates/')
    passport_photo = models.FileField(upload_to='documents/passport_photos/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"National ID Application for {self.application.user.username}"

class ResidentPermitApplication(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, null=True, related_name='resident_permit_applications')
    full_name = models.CharField(max_length=255)
    date_of_birth = models.DateField()
    nationality = models.CharField(max_length=255)
    date_of_entry = models.CharField(max_length=255, null=True)
    passport_number = models.CharField(max_length=255, null=True)
    purpose_of_Stay = models.CharField(max_length=255, null=True)
    phone_number = models.CharField(max_length=255, null=True)
    address = models.TextField()
    passport_photo = models.FileField(null=True, upload_to='documents/passport_photos/')
    resident_permit_document = models.FileField(null=True, upload_to='documents/resident_permits/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Resident Permit Application for {self.application.user.username}"

class WorkPermitApplication(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, null=True, related_name='work_permit_applications')
    full_name = models.CharField(max_length=255)
    date_of_birth = models.DateField()
    nationality = models.CharField(max_length=255)
    address = models.TextField()
    job_title = models.CharField(max_length=255)
    work_contract = models.FileField(upload_to='documents/work_contracts/')
    passport_photo = models.FileField(upload_to='documents/passport_photos/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Work Permit Application for {self.application.user.id}"

class DriversLicenseApplication(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, null=True, related_name='drivers_license_applications')
    full_name = models.CharField(max_length=255)
    date_of_birth = models.DateField()
    address = models.TextField()
    license_number = models.CharField(max_length=50)
    expiry_date = models.DateField()
    passport_photo = models.FileField(upload_to='documents/passport_photos/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Driver's License Application for {self.application.user.username}"

class TINApplication(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, null=True, related_name='tin_applications')
    full_name = models.CharField(max_length=255)
    date_of_birth = models.DateField()
    nationality = models.CharField(max_length=255)
    address = models.TextField()
    tin_number = models.CharField(max_length=15, unique=True)
    passport_photo = models.FileField(upload_to='documents/passport_photos/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"TIN Application for {self.application.user.username}"


class UploadedDocument(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, null=True, related_name='documents')
    document_type = models.CharField(max_length=100)
    document_file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Document {self.document_type} for {self.application.user.username}"