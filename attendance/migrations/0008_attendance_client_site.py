# Adds the explicit Client/Site link chosen by the admin in the attendance
# table (2026-07 Client/Site column). The FK is named `site_ref` — not `site`
# — because AttendanceRecord.site is an existing CharField written by SPIM
# Lite that must keep its name and column. Both FKs are nullable: old rows
# stay null, and neither is required to save attendance.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0010_tighten_nullable_fks'),
        ('attendance', '0007_attendance_machine_work_details'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendancerecord',
            name='client',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='attendance_entries',
                to='projects.projectclient',
            ),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='site_ref',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='attendance_entries',
                to='projects.site',
            ),
        ),
    ]
