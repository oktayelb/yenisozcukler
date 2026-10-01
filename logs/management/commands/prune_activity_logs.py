# logs/management/commands/prune_activity_logs.py
"""Belirtilen günden eski aktivite loglarını siler.

Loglar kendiliğinden silinmez. Aynı işi admin'deki "Logları temizle"
sayfası da yapar; bu komut elle ya da cron'dan çalıştırmak içindir.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from logs.logger import prune_logs
from logs.models import ActivityLog


class Command(BaseCommand):
    help = 'Belirtilen günden eski aktivite loglarını siler.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            required=True,
            help='Kaç günden eski kayıtlar silinsin (0 = tümü).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Silme, sadece kaç kayıt silineceğini yaz.',
        )

    def handle(self, *args, **options):
        verbose = options['verbosity'] > 0
        days = options['days']
        if days < 0:
            raise CommandError('--days negatif olamaz.')

        if options['dry_run']:
            cutoff = timezone.now() - timedelta(days=days)
            count = ActivityLog.objects.filter(timestamp__lt=cutoff).count()
            if verbose:
                self.stdout.write(f'{days} günden eski {count} kayıt silinecekti.')
            return

        deleted, _ = prune_logs(days)

        if verbose:
            self.stdout.write(self.style.SUCCESS(
                f'{days} günden eski {deleted} kayıt silindi.'
            ))
