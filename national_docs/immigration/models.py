# immigration/models.py
from django.db import models
from django.contrib.auth.models import User
from docs.models import Application

class Fulfiller(models.Model):
    application = models.OneToOneField(Application, on_delete=models.CASCADE, null=True, related_name='fulfiller')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    location = models.CharField(max_length=255, null=True)
    action = models.ForeignKey(User, on_delete=models.CASCADE, null=True, related_name='fulfillers')
    schedule = models.DateField(null=True)
    priority = models.CharField(max_length=50, null=True)
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