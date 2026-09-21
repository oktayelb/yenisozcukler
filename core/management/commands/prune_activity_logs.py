# core/management/commands/prune_activity_logs.py
"""Saklama süresini aşan aktivite loglarını siler.

Writer thread bunu zaten saatte bir kendiliğinden yapar
(`ACTIVITY_LOG_RETENTION_DAYS`); bu komut elle ya da cron'dan çalıştırmak
içindir.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.logger import setting
from core.models import ActivityLog

# Tek seferde silinecek satır sayısı: uzun bir DELETE ile SQLite'ı kilitlemeyelim.
_CHUNK = 2000


class Command(BaseCommand):
    help = 'Belirtilen günden eski aktivite loglarını siler.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=None,
            help='Kaç günden eski kayıtlar silinsin (varsayılan: ACTIVITY_LOG_RETENTION_DAYS).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Silme, sadece kaç kayıt silineceğini yaz.',
        )

    def handle(self, *args, **options):
        verbose = options['verbosity'] > 0
        days = options['days']
        if days is None:
            days = setting('ACTIVITY_LOG_RETENTION_DAYS')

        if not days:
            if verbose:
                self.stdout.write('Saklama süresi kapalı (0); hiçbir kayıt silinmedi.')
            return

        cutoff = timezone.now() - timedelta(days=days)
        old = ActivityLog.objects.filter(timestamp__lt=cutoff)

        if options['dry_run']:
            if verbose:
                self.stdout.write(f'{days} günden eski {old.count()} kayıt silinecekti.')
            return

        deleted = 0
        while True:
            ids = list(old.values_list('id', flat=True)[:_CHUNK])
            if not ids:
                break
            count, _ = ActivityLog.objects.filter(id__in=ids).delete()
            deleted += count
            if len(ids) < _CHUNK:
                break

        if verbose:
            self.stdout.write(self.style.SUCCESS(
                f'{days} günden eski {deleted} kayıt silindi.'
            ))
