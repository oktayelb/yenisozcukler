from django.contrib import admin
from django.urls import path, include
from decouple import config

urlpatterns = [
    path(config('ADMIN_PATH'), admin.site.urls),
    path('', include('core.urls')), # Connects to core/urls.py
]







