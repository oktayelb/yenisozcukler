from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_word_slug'),
    ]

    operations = [
        migrations.AlterField(
            model_name='comment',
            name='score',
            field=models.IntegerField(default=0, db_index=True),
        ),
        migrations.AddIndex(
            model_name='comment',
            index=models.Index(fields=['word', 'timestamp'], name='core_commen_word_id_timestamp_idx'),
        ),
    ]
