"""
Purge every AttendanceRecord that was auto-created by the (now-neutered)
`ensure_sunday_holidays` backfill.

Fingerprint of an auto-Sunday-Holiday row:
    status='holiday' AND source='admin' AND created_by IS NULL
    AND date falls on a Sunday.

These rows are what still cause today's row to appear as "Holiday 🔒"
in the Attendance page even though the backfill helper is now a no-op —
migration 0003 only purged FUTURE Sundays as of the day it ran, so any
Sunday that was "today" between then and the no-op landing is still in
the table.

Reverse: no-op — an auto-fill cannot be reconstructed from schema.
"""
from django.db import migrations


def purge_auto_sunday_holidays(apps, schema_editor):
    AttendanceRecord = apps.get_model('attendance', 'AttendanceRecord')
    # Django ORM week_day: 1 = Sunday.
    AttendanceRecord.objects.filter(
        status='holiday',
        source='admin',
        created_by__isnull=True,
        date__week_day=1,
    ).delete()


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0005_attendancerecord_remarks_and_lock'),
    ]

    operations = [
        migrations.RunPython(purge_auto_sunday_holidays, noop_reverse),
    ]
