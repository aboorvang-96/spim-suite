"""
Merge the retired 'absent' status into 'no_week_off'.

Both statuses already have identical pay treatment (weight 0.0 in
employees/views.py::_compute_attendance_earnings), so this is a
label-only consolidation — no payroll math changes.

One-way: reverse raises NotImplementedError. Rollback is the DB backup.
"""

from django.db import migrations, models


def _forward(apps, schema_editor):
    AttendanceRecord = apps.get_model('attendance', 'AttendanceRecord')
    updated = AttendanceRecord.objects.filter(status='absent').update(status='no_week_off')
    # Printed to stdout so the Railway deploy log shows the row count.
    print(f"[0009] Converted {updated} AttendanceRecord row(s) from 'absent' to 'no_week_off'.")


def _reverse(apps, schema_editor):
    raise NotImplementedError(
        "Migration 0009 is one-way; restore from DB backup to roll back."
    )


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        ('attendance', '0008_attendance_client_site'),
    ]

    operations = [
        migrations.RunPython(_forward, _reverse),
        migrations.AlterField(
            model_name='attendancerecord',
            name='status',
            field=models.CharField(
                choices=[
                    ('present', 'Present'),
                    ('half_day', 'Half Day'),
                    ('leave', 'Leave'),
                    ('holiday', 'Holiday'),
                    ('week_off', 'Week Off'),
                    ('no_week_off', 'No Week Off'),
                ],
                default='present',
                max_length=20,
            ),
        ),
    ]
