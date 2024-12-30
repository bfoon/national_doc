from django.contrib import admin
from .models import *

# Register general models
admin.site.register(NationalIDApplication)
admin.site.register(UploadedDocument)
admin.site.register(Application)
admin.site.register(ResidentPermitApplication)
admin.site.register(WorkPermitApplication)
admin.site.register(DriversLicenseApplication)
admin.site.register(TINApplication)
admin.site.register(Profile)
admin.site.register(ExtendOrPrint)

# Register Certification and its related models
@admin.register(Certification)
class CertificationAdmin(admin.ModelAdmin):
    list_display = ('get_certificate_type_display', 'applicant_name', 'status', 'submission_date', 'submitted_by', 'approved_by')
    search_fields = ('applicant_name', 'applicant_email', 'applicant_phone', 'purpose')
    list_filter = ('certificate_type', 'status', 'submission_date')
    ordering = ('-submission_date',)
    list_select_related = ('submitted_by', 'approved_by')

@admin.register(CertificationAttachment)
class CertificationAttachmentAdmin(admin.ModelAdmin):
    list_display = ('certification', 'get_attachment_type_display', 'file', 'description')
    search_fields = ('description',)
    list_filter = ('attachment_type',)
    list_select_related = ('certification',)

@admin.register(BirthRegistration)
class BirthRegistrationAdmin(admin.ModelAdmin):
    list_display = ('certification', 'date_of_birth', 'place_of_birth', 'father_name', 'mother_name', 'birth_registration_number')
    search_fields = ('certification__applicant_name', 'birth_registration_number')
    list_filter = ('date_of_birth',)
    list_select_related = ('certification',)

@admin.register(MarriageDetails)
class MarriageDetailsAdmin(admin.ModelAdmin):
    list_display = ('certification', 'spouse1_name', 'spouse2_name', 'marriage_date', 'marriage_registration_number')
    search_fields = ('spouse1_name', 'spouse2_name', 'marriage_registration_number')
    list_filter = ('marriage_date',)
    list_select_related = ('certification',)

@admin.register(DeathDetails)
class DeathDetailsAdmin(admin.ModelAdmin):
    list_display = ('certification', 'full_name', 'date_of_death', 'place_of_death', 'cause_of_death')
    search_fields = ('full_name', 'place_of_death', 'cause_of_death')
    list_filter = ('date_of_death',)
    list_select_related = ('certification',)

@admin.register(CharacterCertificate)
class CharacterCertificateAdmin(admin.ModelAdmin):
    list_display = ('certification', 'full_name', 'good_moral_character')
    search_fields = ('full_name', 'good_moral_character')
    list_select_related = ('certification',)

@admin.register(AcademicCertificate)
class AcademicCertificateAdmin(admin.ModelAdmin):
    list_display = ('certification', 'full_name', 'course', 'date_of_completion')
    search_fields = ('full_name', 'course', 'date_of_completion')
    list_filter = ('date_of_completion',)
    list_select_related = ('certification',)