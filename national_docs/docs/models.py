import uuid
from django.db import models
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils.crypto import get_random_string
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

class Application(models.Model):
    APPLICATION_TYPE_CHOICES = [
        ('new', 'New Application'),
        ('extension', 'Extension'),
        ('lost', 'Lost ID'),
    ]

    APPLICATION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('waiting', 'Waiting'),
        ('interview', 'Interview'),
        ('completed', 'Completed'),
        ('canceled', 'Canceled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    application_type = models.CharField(max_length=50, choices=APPLICATION_TYPE_CHOICES)
    application_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=50, choices=APPLICATION_STATUS_CHOICES, default='pending')
    interview_slot = models.ForeignKey('immigration.InterviewSlot', on_delete=models.SET_NULL, null=True, blank=True)
    interview_queue_number = models.IntegerField(null=True, blank=True)
    post_location = models.ForeignKey('immigration.PostLocation', on_delete=models.SET_NULL,
                                      null=True, blank=True)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.token:  # Ensure token is set if not already
            self.token = uuid.uuid4()

        retries = 5  # Limit retries to avoid infinite loops
        for _ in range(retries):
            try:
                with transaction.atomic():
                    super().save(*args, **kwargs)
                break  # Exit loop if save is successful
            except IntegrityError as e:
                # Check if the error is due to a duplicate token
                if 'duplicate key value violates unique constraint' in str(e):
                    # Generate a new token and retry
                    self.token = uuid.uuid4()
                else:
                    # If the IntegrityError is due to a different reason, raise it
                    raise
        else:
            # Log or handle failure after retries, if necessary
            raise IntegrityError("Unable to assign a unique token after multiple attempts.")

    def __str__(self):
        return f"Application {self.id} - {self.application_type} for {self.user.username}"

    def get_service_type(self):
        """Get the type of service based on the related models."""
        if self.national_id_applications.exists():
            return "National ID"
        elif self.resident_permit_applications.exists():
            return "Resident Permit"
        elif self.work_permit_applications.exists():
            return "Work Permit"
        elif self.drivers_license_applications.exists():
            return "Driver's License"
        elif self.tin_applications.exists():
            return "TIN"
        return "Unknown Service"


class Certification(models.Model):
    CERTIFICATE_TYPES = [
        ('birth', 'Birth Certificate'),
        ('character', 'Certificate of Character'),
        ('marriage', 'Marriage Certificate'),
        ('death', 'Death Certificate'),
        ('academic', 'Academic Certificate'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    certificate_type = models.CharField(max_length=20, choices=CERTIFICATE_TYPES)
    applicant_name = models.CharField(max_length=255)
    applicant_email = models.EmailField()
    applicant_phone = models.CharField(max_length=20)
    purpose = models.TextField()
    submission_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='certifications_submitted')
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='certifications_approved', null=True, blank=True
    )
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_certificate_type_display()} - {self.applicant_name}"

class CertificationAttachment(models.Model):
    ATTACHMENT_TYPES = [
            ('hospital_record', 'Hospital Record'),
            ('id_proof', 'ID Proof'),
            ('other', 'Other'),
    ]

    certification = models.ForeignKey(Certification, on_delete=models.CASCADE, related_name='attachments')
    attachment_type = models.CharField(max_length=20, choices=ATTACHMENT_TYPES)
    file = models.FileField(upload_to='documents/certification_attachments/')
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.get_attachment_type_display()} for {self.certification}"


class BirthRegistration(models.Model):
    certification = models.OneToOneField(Certification, on_delete=models.CASCADE, related_name='birth_registration')
    date_of_birth = models.DateField()
    place_of_birth = models.CharField(max_length=255)
    time_of_birth = models.TimeField()
    father_name = models.CharField(max_length=255)
    mother_name = models.CharField(max_length=255)
    sex = models.CharField(max_length=10)
    birth_registration_number = models.CharField(max_length=50, unique=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.birth_registration_number:
            # Generate a unique birth registration number
            dob_str = self.date_of_birth.strftime('%Y%m%d')  # e.g., '19900315'
            initials = ''.join([word[0].upper() for word in self.place_of_birth.split()[:2]])  # e.g., 'NY'
            random_suffix = get_random_string(6, '0123456789')  # e.g., '4527'
            self.birth_registration_number = f"{dob_str}-{initials}-{random_suffix}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Birth Registration for {self.father_name} and {self.mother_name}'s child"

class MarriageDetails(models.Model):
    certification = models.OneToOneField(Certification, on_delete=models.CASCADE, related_name='marriage_details')
    spouse1_name = models.CharField(max_length=255)
    spouse2_name = models.CharField(max_length=255)
    marriage_date = models.DateField()
    marriage_registration_number = models.CharField(max_length=50, unique=True, editable=False)

    def __str__(self):
        return f"Marriage Certificate for {self.spouse1_name} and {self.spouse2_name}"

class DeathDetails(models.Model):
    certification = models.OneToOneField(Certification, on_delete=models.CASCADE, related_name='death_details')
    full_name = models.CharField(max_length=255)
    date_of_death = models.DateField()
    place_of_death = models.CharField(max_length=255)
    cause_of_death = models.TextField()

    def __str__(self):
        return f"Death Certificate for {self.full_name}"

class CharacterCertificate(models.Model):
    certification = models.OneToOneField(Certification, on_delete=models.CASCADE, related_name='character_certificate')
    full_name = models.CharField(max_length=255)
    good_moral_character = models.TextField()

    def __str__(self):
        return f"Certificate of Character for {self.full_name}"

class AcademicCertificate(models.Model):
    certification = models.OneToOneField(Certification, on_delete=models.CASCADE, related_name='academic_certificate')
    full_name = models.CharField(max_length=255)
    course = models.CharField(max_length=255)
    date_of_completion = models.DateField()

    def __str__(self):
        return f"Academic Certificate for {self.full_name} in {self.course}"


class NationalIDApplication(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, null=True, related_name='national_id_applications')
    full_name = models.CharField(max_length=255)
    date_of_birth = models.DateField()
    place_of_birth = models.CharField(max_length=255)
    gender = models.CharField(max_length=10, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')])
    address = models.TextField()
    phone_number = models.CharField(max_length=15)
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
    purpose_of_stay = models.CharField(max_length=255, null=True)
    phone_number = models.CharField(max_length=255, null=True)
    address = models.TextField()
    email = models.CharField(max_length=255, null=True)
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
    phone_number = models.CharField(max_length=255, null=True)
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

class ExtendOrPrint(models.Model):
    STATE_CHOICES = [
        ('reprint', 'Re-Print'),
        ('extend', 'Extend'),
    ]

    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        null=True,
        related_name='extend_or_print_requests'
    )
    state = models.CharField(
        max_length=10,
        choices=STATE_CHOICES,
        null=True,
        blank=True,
        help_text="Specify if this is a re-print or extension request."
    )
    reason = models.TextField(
        null=True,
        blank=True,
        help_text="Provide the reason for the request (e.g., lost document or expired document)."
    )
    upload = models.FileField(
        upload_to='documents/extend/',
        blank=True,
        null=True,
        help_text="Upload any supporting documents, if applicable."
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="The date and time when the request was created.")
    updated_at = models.DateTimeField(auto_now=True, help_text="The date and time when the request was last updated.")

    def __str__(self):
        return f"{self.get_state_display()} request for {self.application}"

    class Meta:
        verbose_name = "Extend or Print Request"
        verbose_name_plural = "Extend or Print Requests"
        ordering = ['-created_at']

class UploadedDocument(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, null=True, related_name='documents')
    document_type = models.CharField(max_length=100)
    document_file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Document {self.document_type} for {self.application.user.username}"

class ChatMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_messages")
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    response_type = models.CharField(max_length=50, choices=[
        ('general', 'General'),
        ('technical', 'Technical Support'),
        ('inquiry', 'Information Inquiry'),
        ('urgent', 'Urgent Matter')
    ], null=True, blank=True)
    is_urgent = models.BooleanField(default=False)
    requires_follow_up = models.BooleanField(default=False)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='replies',  on_delete=models.SET_NULL)

    def __str__(self):
        return f"Message from {self.sender} to {self.recipient} - {self.timestamp}"

