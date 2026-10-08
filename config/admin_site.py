from django.contrib import admin
from django.shortcuts import redirect


class AdminSiteWithoutLoginForm(admin.AdminSite):
    def login(self, request, extra_context=None):
        return redirect('/')
