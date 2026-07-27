"""
Attendance ↔ Projects integration fields.

Adds:
  * AttendanceRecord.machine       — nullable FK to projects.MachineLocation
                                     (SET_NULL on delete, so pruning a
                                     machine in Projects doesn't cascade
                                     away historical attendance rows).
  * AttendanceRecord.work_details  — free-text field for the work performed.

Both fields default to blank / NULL on existing rows. No data migration
needed — legacy attendance keeps working exactly as before; the new
columns start empty and are opt-in on the desktop UI.

The `working_site` CharField from migration 0004 is intentionally left
untouched. The Suite UI stops surfacing it, but SPIM Lite mobile still
writes to it, so the column must remain for mobile compatibility.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0006_purge_auto_sunday_holidays'),
        ('projects',   '0010_tighten_nullable_fks'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendancerecord',
            name='machine',
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='attendance_entries',
                to='projects.machinelocation',
            ),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='work_details',
            field=models.TextField(blank=True, default=''),
        ),
    ]
