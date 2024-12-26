# immigration/models.py
from django.db import models
from django.contrib.auth.models import User, Group
from docs.models import Application, ChatMessage
from django.utils import timezone
from django.utils.text import slugify


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
        return f"Interview Slot on {self.date_time} at {self.location}"

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

class FAQCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    slug = models.SlugField(unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "FAQ Category"
        verbose_name_plural = "FAQ Categories"
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class FAQ(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]

    # Basic Fields
    question = models.CharField(max_length=255)
    answer = models.TextField()
    slug = models.SlugField(unique=True, editable=False)

    # Categorization
    category = models.ForeignKey(
        FAQCategory,
        on_delete=models.SET_NULL,
        null=True,
        related_name='faqs'
    )
    tags = models.CharField(
        max_length=255,
        blank=True,
        help_text="Comma-separated tags"
    )
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='low'
    )

    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_faqs'
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='updated_faqs'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    view_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"
        ordering = ['-priority', '-updated_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['priority', '-updated_at']),
        ]

    def __str__(self):
        return self.question

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.question)[:50]
        super().save(*args, **kwargs)

    def increment_view_count(self):
        """Increment the view count of the FAQ"""
        self.view_count += 1
        self.save(update_fields=['view_count'])

    @property
    def tag_list(self):
        """Return list of tags"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',')]
        return []

    @property
    def is_recently_updated(self):
        """Check if FAQ was updated in the last 7 days"""
        from django.utils import timezone
        from datetime import timedelta
        return self.updated_at >= timezone.now() - timedelta(days=7)

    @classmethod
    def get_popular_faqs(cls, limit=5):
        """Get most viewed FAQs"""
        return cls.objects.filter(is_active=True).order_by('-view_count')[:limit]

    @classmethod
    def search(cls, query):
        """Search FAQs by question, answer, or tags"""
        return cls.objects.filter(
            models.Q(question__icontains=query) |
            models.Q(answer__icontains=query) |
            models.Q(tags__icontains=query),
            is_active=True
        ).distinct()


class CallNote(models.Model):
    # User related to the call note
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='call_notes')

    # Customer information (optional)
    customer = models.CharField(max_length=255, blank=True)

    # Type of the call (e.g., 'Sales', 'Support', etc.)
    CALL_TYPE_CHOICES = [
        ('general', 'General Inquiry'),
        ('support', 'Technical Support'),
        ('inquiry', 'Complaint'),
        ('followup', 'Follow Up')
    ]
    call_type = models.CharField(max_length=255, choices=CALL_TYPE_CHOICES, blank=True)

    # Priority level of the call (e.g., 'High', 'Medium', 'Low')
    PRIORITY_CHOICES = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low')
    ]
    priority = models.CharField(max_length=255, choices=PRIORITY_CHOICES, blank=True)

    # Detailed note about the call
    note = models.TextField()

    # Follow-up flag and follow-up date
    followup = models.BooleanField(default=False, db_index=True)
    followup_date = models.DateTimeField(null=True, blank=True)

    # Completion status of the call note
    completed = models.BooleanField(default=False)

    # Timestamp when the call note was created
    created_at = models.DateTimeField(auto_now_add=True)

    # Meta class to set the verbose name and ordering
    class Meta:
        verbose_name = "Call Note"
        verbose_name_plural = "Call Notes"
        ordering = ['-created_at']

    def __str__(self):
        return f"Call Note by {self.user.get_full_name()} on {self.created_at.strftime('%Y-%m-%d %H:%M')} - {self.call_type.title()} ({self.priority.title()})"

    def is_followup_due(self):
        """Returns whether the follow-up is overdue."""
        if self.followup and self.followup_date and timezone.now() > self.followup_date:
            return True
        return False

    def mark_completed(self):
        """Marks the call note as completed."""
        self.completed = True
        self.save()

    # Optional: Custom manager for filtering completed or followup-related notes
    @classmethod
    def get_pending_followups(cls):
        """Returns all call notes that are due for follow-up."""
        return cls.objects.filter(followup=True, followup_date__lte=timezone.now(), completed=False)

class MessageNote(models.Model):
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='created_notes',
        help_text="The user who created the note."
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='received_notes'
    )
    chat = models.ForeignKey(
        ChatMessage,
        on_delete=models.CASCADE,
        null=True,
        related_name='notes',
        db_index=True,
        help_text="Associated chat message."
    )
    note = models.TextField(help_text="Details of the note.")
    title = models.CharField(max_length=255, blank=True, help_text="Title of the note (optional).")
    important = models.BooleanField(default=False, db_index=True, help_text="Mark as important.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Message Note"
        verbose_name_plural = "Message Notes"
        ordering = ['-created_at']

    def __str__(self):
        title_part = f" - {self.title}" if self.title else ""
        importance = " (Important)" if self.important else ""
        return f"Note by {self.created_by.get_full_name()} on {self.created_at.strftime('%Y-%m-%d %H:%M')}{title_part}{importance}"

    @property
    def is_important(self):
        return self.important

# For taking follow up notes on call notes.
class FollowUpNote(models.Model):
    call_note = models.ForeignKey(
        'CallNote',
        on_delete=models.CASCADE,
        related_name='follow_up_notes',  # Updated related_name for clarity
        help_text="The call note this follow-up note is related to."
    )
    note = models.TextField(
        help_text="Detailed content of the follow-up note."
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='follow_up_notes',  # Updated related_name to reflect user-created notes
        help_text="The user who created this follow-up note."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when this follow-up note was created."
    )

    class Meta:
        ordering = ['-created_at']  # Ensures notes are ordered by the latest first
        verbose_name = "Follow-Up Note"
        verbose_name_plural = "Follow-Up Notes"

    def __str__(self):
        return f"Follow-Up Note by {self.created_by} on {self.created_at:%Y-%m-%d}"

