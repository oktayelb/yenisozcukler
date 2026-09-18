from django.contrib import admin
from django.urls import path, include
from decouple import config

urlpatterns = [
    path(config('ADMIN_PATH'), admin.site.urls),
    path('', include('accounts.urls')),
    path('', include('words.urls')),
    path('', include('notifications.urls')),
    path('', include('core.urls')), # en sonda: SPA catch-all'u içeriyor
]







 