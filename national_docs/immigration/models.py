# immigration/models.py
from django.db import models
from django.contrib.auth.models import User, Group
from docs.models import Application


class PostLocation(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField()
    city = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    district = models.CharField(max_length=100)
    settlement = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class OfficerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    phone = models.CharField(max_length=50, null=True)
    # email = models.CharField(max_length=1000, null=True)
    officer_batch_number = models.CharField(max_length=100, unique=True)
    post_location = models.ForeignKey(PostLocation, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        full_name = self.user.get_full_name() or self.user.username
        return f"{full_name} ({self.officer_batch_number})"

    def get_full_name(self):
        return f"{self.user.first_name} {self.user.last_name}"

    class Meta:
        verbose_name = "Officer Profile"
        verbose_name_plural = "Officer Profiles"

class Fulfiller(models.Model):
    application = models.OneToOneField(Application, on_delete=models.CASCADE, null=True, related_name='fulfiller')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    location = models.ForeignKey(PostLocation, on_delete=models.CASCADE, null=True, related_name='fulfillers')
    action = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    schedule = models.DateField(null=True)
    priority = models.CharField(max_length=50, null=True, default='low')
    status = models.CharField(max_length=50, choices=[('open', 'Open'), ('closed', 'Closed')], default='open')
    progress = models.IntegerField(default=0)

    def __str__(self):
        return f"Fulfiller for Application {self.application.id}"


class Note(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='notes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # The user who added the note
    message = models.TextField()  # The actual note/message
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp of when the note was created

    def __str__(self):
        return f"Note for Application {self.application.id} by {self.user.username}"

class InterviewSlot(models.Model):
    date_time = models.DateTimeField()  # Date and time of the interview slot
    max_interviewees = models.IntegerField(default=10)  # Maximum number of interviews allowed
    current_interviewees = models.IntegerField(default=0)  # Track how many have been assigned
    location = models.ForeignKey(PostLocation, on_delete=models.SET_NULL, null=True)  # Link to Post Location
    is_available = models.BooleanField(default=True)  # Whether the slot is available or not

    def __str__(self):
        return f"Interview Slot on {self.date_time} at {self.location.name}"

    def check_availability(self):
        # Update availability status based on current interviewees count
        self.is_available = self.current_interviewees < self.max_interviewees
        self.save()


class Interview(models.Model):
    """
    Represents an interview conducted as part of the application process.
    Tracks the details of the interview, including status, date, interviewer, etc.
    """
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('postponed', 'Postponed'),
        ('in_progress', 'In Progress'),
        ('waiting', 'Waiting Approval'),
    ]

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='interviews')
    interviewer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)  # The interviewer conducting the interview
    date_created = models.DateTimeField(auto_now_add=True)  # Date and time of the interview
    duration = models.IntegerField(default=0)  # Duration of the interview in minutes
    questionnaire = models.TextField(null=True, blank=True)  # Questionnaire responses
    notes = models.TextField(null=True, blank=True)  # Interview notes
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='scheduled')
    boot = models.ForeignKey('Boot', on_delete=models.SET_NULL, null=True, blank=True, related_name='interviews')
    def __str__(self):
        return f"Interview for {self.application.user.username} on {self.date_created}"

    class Meta:
        verbose_name = "Interview"
        verbose_name_plural = "Interviews"
        ordering = ['-date_created']  # To order interviews by most recent date_created by default

class ToDo(models.Model):
    STATUS_CHOICES = [
        (0, 'Pending'),
        (1, 'Approved'),
    ]

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='todos')
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE, null=True, blank=True, related_name='todos')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True,  related_name='todos')  # The user assigned the task
    status = models.IntegerField(choices=STATUS_CHOICES, default=0)  # 0 by default, 1 if approved
    approver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_todos')  # User who approves the task
    rejection_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"To-Do for {self.application} by {self.user}"

class Boot(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_boots')
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, related_name='boots')
    post_location = models.ForeignKey('immigration.PostLocation', on_delete=models.SET_NULL, null=True, blank=True, related_name='boots')

    def __str__(self):
        return self.name

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)  # To track if the notification has been read
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']  # Order notifications by newest first

    def __str__(self):
        return f'Notification for {self.user.username}: {self.message}'

class FAQ(models.Model):
    question = models.CharField(max_length=255)
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"
        ordering = ['-created_at']

    def __str__(self):
        return self.question

class CallNote(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='call_notes')
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Call Note"
        verbose_name_plural = "Call Notes"
        ordering = ['-created_at']

    def __str__(self):
        return f"Call Note by {self.user.get_full_name()} on {self.created_at.strftime('%Y-%m-%d %H:%M')}"