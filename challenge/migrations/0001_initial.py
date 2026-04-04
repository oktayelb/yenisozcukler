"""
Take ownership of challenge models from core app.
Tables already exist in the database (core_translationchallenge, etc.).
New fields (timer_on, timer_started_at, etymology, example_sentence) are added,
and unique_together constraint on (user, challenge) for ChallengeComment.
"""
import datetime
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0019_remove_challenge_models'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Step 1: Create models in state, pointing to existing tables
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='TranslationChallenge',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('foreign_word', models.CharField(max_length=100)),
                        ('meaning', models.CharField(max_length=300)),
                        ('author', models.CharField(default='Anonim', max_length=50)),
                        ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                        ('status', models.CharField(choices=[('pending', 'Pending'), ('approved', 'Approved')], db_index=True, default='pending', max_length=10)),
                        ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True)),
                        ('user', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='challenges', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'ordering': ['-timestamp'],
                        'db_table': 'core_translationchallenge',
                    },
                ),
                migrations.CreateModel(
                    name='ChallengeComment',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('author', models.CharField(default='Anonim', max_length=50)),
                        ('suggested_word', models.CharField(max_length=30)),
                        ('explanation', models.CharField(blank=True, default='', max_length=300)),
                        ('timestamp', models.DateTimeField(auto_now_add=True)),
                        ('score', models.IntegerField(default=0)),
                        ('challenge', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='challenge.translationchallenge')),
                        ('user', models.ForeignKey(blank=True, db_index=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='challenge_comments', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'db_table': 'core_challengecomment',
                    },
                ),
                migrations.CreateModel(
                    name='ChallengeCommentVote',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                        ('value', models.SmallIntegerField(choices=[(1, 'Like'), (-1, 'Dislike')])),
                        ('timestamp', models.DateTimeField(auto_now_add=True)),
                        ('comment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='votes', to='challenge.challengecomment')),
                        ('user', models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, related_name='challenge_comment_votes', to=settings.AUTH_USER_MODEL)),
                    ],
                    options={
                        'unique_together': {('user', 'comment')},
                        'db_table': 'core_challengecommentvote',
                    },
                ),
            ],
            database_operations=[],
        ),

        # Step 2: Add new fields (these DO run on the database)
        migrations.AddField(
            model_name='translationchallenge',
            name='timer_on',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='translationchallenge',
            name='timer_started_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='challengecomment',
            name='etymology',
            field=models.CharField(blank=True, default='', max_length=300),
        ),
        migrations.AddField(
            model_name='challengecomment',
            name='example_sentence',
            field=models.CharField(blank=True, default='', max_length=300),
        ),
        migrations.AlterUniqueTogether(
            name='challengecomment',
            unique_together={('user', 'challenge')},
        ),
    ]
