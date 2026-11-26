from django.urls import path

from . import ban_pass, views

urlpatterns = [
    path(ban_pass.PATH.lstrip('/'), views.ban_pass_view, name='ban_pass'),
]
