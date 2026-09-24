from django.urls import path
from . import views

urlpatterns = [
    path('api/login', views.login_view, name='login'),
    path('api/register', views.register_view, name='register'),
    path('api/logout', views.logout_view, name='logout'),
    path('api/profile', views.get_user_profile, name='get_user_profile'),
    path('api/password', views.change_password, name='change_password'),
    path('api/username', views.change_username, name='change_username'),
]
