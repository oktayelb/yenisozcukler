from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('challenge', '0006_alter_challengecomment_etymology_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='challengecomment',
            name='score',
            field=models.IntegerField(default=0, db_index=True),
        ),
        migrations.AddIndex(
            model_name='challengecomment',
            index=models.Index(fields=['challenge', '-score', 'timestamp'], name='challenge_cc_challenge_score_idx'),
        ),
    ]
