from django.contrib import admin
from .models import *

admin.site.register(NationalIDApplication)
admin.site.register(UploadedDocument)
admin.site.register(Application)
admin.site.register(ResidentPermitApplication)
admin.site.register(WorkPermitApplication)
admin.site.register(DriversLicenseApplication)
admin.site.register(TINApplication)
admin.site.register(Profile)
admin.site.register(ExtendOrPrint)
@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'recipient', 'message', 'timestamp', 'is_read')
    list_filter = ('is_read', 'timestamp')
    search_fields = ('sender__username', 'recipient__username', 'message')
