from django.db import migrations


CHALLENGE_TABLES = (
    'core_challengecommentvote',
    'core_challengecomment',
    'core_translationchallenge',
)


def drop_orphaned_challenge_schema(apps, schema_editor):
    if schema_editor.connection.vendor != 'sqlite':
        return

    cursor = schema_editor.connection.cursor()

    cursor.execute("PRAGMA table_info(notifications_notification)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'challenge_comment_id' in columns:
        cursor.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'index' AND tbl_name = 'notifications_notification' "
            "AND sql LIKE '%challenge_comment_id%'"
        )
        for (index_name,) in cursor.fetchall():
            cursor.execute(f'DROP INDEX IF EXISTS "{index_name}"')
        cursor.execute(
            'ALTER TABLE "notifications_notification" DROP COLUMN "challenge_comment_id"'
        )

    for table in CHALLENGE_TABLES:
        cursor.execute(f'DROP TABLE IF EXISTS "{table}"')


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0003_remove_notification_challenge_comment_and_more'),
    ]

    operations = [
        migrations.RunPython(drop_orphaned_challenge_schema, migrations.RunPython.noop),
    ]
