from django.db import migrations
import datetime


def purge_future_sunday_holidays(apps, schema_editor):
    """
    One-time cleanup: delete AttendanceRecord rows for FUTURE dates that
    were auto-created as 'holiday' rows by ensure_sunday_holidays before
    the date-cap fix landed.

    Match criteria (all must hold):
        date > today
        status == 'holiday'
        source == 'admin'

    The companion fix in attendance/utils.py:ensure_sunday_holidays caps
    `date_to` at today, so no NEW future Sunday holiday rows can be
    auto-created from this point onwards. This migration only removes the
    stale rows already in the DB. It is safe to run on every deploy —
    a re-run on a clean DB simply matches zero rows.

    A reverse_code is intentionally not provided: re-creating future
    Sunday holiday rows is exactly the bug this migration is fixing, so
    rolling back would resurrect the bug. `noop_reverse` lets `migrate`
    rewind to an earlier migration without erroring while still leaving
    the cleaned-up rows deleted.
    """
    AttendanceRecord = apps.get_model('attendance', 'AttendanceRecord')
    today = datetime.date.today()
    AttendanceRecord.objects.filter(
        date__gt=today,
        status='holiday',
        source='admin',
    ).delete()


def noop_reverse(apps, schema_editor):
    """No reverse — see purge_future_sunday_holidays docstring."""
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('attendance', '0002_extend_status_choices'),
    ]

    operations = [
        migrations.RunPython(purge_future_sunday_holidays, noop_reverse),
    ]
