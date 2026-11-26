from django.db import migrations


def flag_bot_only_paths(apps, schema_editor):
    ActivityLog = apps.get_model('logs', 'ActivityLog')
    ActivityLog.objects.filter(
        path__in=['/robots.txt', '/sitemap.xml'], is_bot=False,
    ).update(is_bot=True)


class Migration(migrations.Migration):

    dependencies = [
        ('logs', '0002_bannedip'),
    ]

    operations = [
        migrations.RunPython(flag_bot_only_paths, migrations.RunPython.noop),
    ]
