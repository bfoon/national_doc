from django.contrib import admin
from .models import *

admin.site.register(Token)
admin.site.register(TokenLog)
admin.site.register(UserRisk)