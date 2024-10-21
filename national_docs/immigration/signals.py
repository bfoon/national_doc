# # immigration/signals.py
# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from docs.models import Application
# from .models import Fulfiller
#
# @receiver(post_save, sender=Application)
# def create_fulfiller_for_application(sender, instance, created, **kwargs):
#     if created:
#         Fulfiller.objects.create(application=instance)
