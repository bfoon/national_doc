import uuid
import random
import string
from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now

class Token(models.Model):
    token = models.CharField(max_length=6, unique=True, editable=False)  # 6-character unique token
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # Linked user
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # Associated amount
    created_at = models.DateTimeField(auto_now_add=True)  # Token creation time
    is_used = models.BooleanField(default=False)  # Token usage status
    service_completed_at = models.DateTimeField(null=True, blank=True)  # Service completion time

    def save(self, *args, **kwargs):
        if not self.token:  # Only generate if token is not set
            self.token = self.generate_token()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_token():
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))  # Generate a 6-character random string

    def mark_as_used(self):
        self.is_used = True
        self.service_completed_at = now()
        self.save()

    def __str__(self):
        return f"Token {self.token} - User {self.user.username}"

class TokenLog(models.Model):
    token = models.ForeignKey(Token, on_delete=models.CASCADE, related_name="logs")
    ip_address = models.GenericIPAddressField()  # User's IP address
    activity = models.TextField()  # Description of activity
    created_at = models.DateTimeField(auto_now_add=True)  # Log creation time

    def __str__(self):
        return f"Log for Token {self.token.token} - {self.ip_address}"

class UserRisk(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    failed_attempts = models.PositiveIntegerField(default=0)  # Failed token attempts
    is_risky = models.BooleanField(default=False)  # Risk status

    def increment_failed_attempts(self):
        self.failed_attempts += 1
        if self.failed_attempts >= 3:
            self.is_risky = True
        self.save()

    def reset_attempts(self):
        self.failed_attempts = 0
        self.is_risky = False
        self.save()

    def __str__(self):
        return f"Risk Status for {self.user.username}: {'Risky' if self.is_risky else 'Safe'}"
