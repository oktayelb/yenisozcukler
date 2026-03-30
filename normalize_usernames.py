"""
One-time script to lowercase all existing usernames in the database.
Run with: python normalize_usernames.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User

users = User.objects.all()
changed = 0
skipped = 0

for user in users:
    lower = user.username.lower()
    if user.username != lower:
        if User.objects.filter(username=lower).exclude(pk=user.pk).exists():
            print(f"CONFLICT: '{user.username}' → '{lower}' already taken by another user. Skipping.")
            skipped += 1
        else:
            print(f"Renaming: '{user.username}' → '{lower}'")
            user.username = lower
            user.save(update_fields=['username'])
            changed += 1

print(f"\nDone. {changed} renamed, {skipped} skipped due to conflicts.")
