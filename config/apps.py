from django.contrib.admin.apps import AdminConfig


class AdminWithoutLoginFormConfig(AdminConfig):
    default_site = 'config.admin_site.AdminSiteWithoutLoginForm'
