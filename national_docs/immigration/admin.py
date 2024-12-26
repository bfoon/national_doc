from django.contrib import admin
from .models import *

admin.site.register(Fulfiller)
admin.site.register(PostLocation)
admin.site.register(Note)
admin.site.register(OfficerProfile)
admin.site.register(InterviewSlot)
admin.site.register(Interview)
admin.site.register(ToDo)
admin.site.register(Notification)
admin.site.register(Boot)
admin.site.register(MessageNote)
admin.site.register(CallNote)
admin.site.register(FollowUpNote)

@admin.register(FAQCategory)
class FAQCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['slug', 'created_at', 'updated_at']


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ['question', 'category', 'priority', 'view_count', 'is_active', 'updated_at']
    list_filter = ['category', 'priority', 'is_active', 'created_at']
    search_fields = ['question', 'answer', 'tags']
    readonly_fields = ['slug', 'created_at', 'updated_at', 'view_count']
    autocomplete_fields = ['category']

    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)