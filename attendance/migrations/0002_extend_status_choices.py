from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Extend AttendanceRecord.STATUS_CHOICES with 'holiday', 'week_off', and
    'no_week_off' to support the new payroll rules (Sundays excluded,
    earned-week-off validation, capped paid days). This is a choices-only
    AlterField — the underlying CharField column structure is unchanged, so
    existing rows (present / absent / half_day / leave) are preserved.
    """

    dependencies = [
        ('attendance', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attendancerecord',
            name='status',
            field=models.CharField(
                max_length=20,
                default='present',
                choices=[
                    ('present', 'Present'),
                    ('absent', 'Absent'),
                    ('half_day', 'Half Day'),
                    ('leave', 'Leave'),
                    ('holiday', 'Holiday'),
                    ('week_off', 'Week Off'),
                    ('no_week_off', 'No Week Off'),
                ],
            ),
        ),
    ]
