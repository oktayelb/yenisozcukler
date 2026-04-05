"""
Remove challenge models from core app state.
The actual database tables are kept and managed by the challenge app.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_remove_challengecomment_comment_and_more'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='ChallengeCommentVote'),
                migrations.DeleteModel(name='ChallengeComment'),
                migrations.DeleteModel(name='TranslationChallenge'),
            ],
            database_operations=[],
        ),
    ]
