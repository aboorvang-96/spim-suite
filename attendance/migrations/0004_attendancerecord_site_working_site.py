# Generated manually for SPIM Lite Site/Working Site sync.
# Adds two CharFields to AttendanceRecord:
#   * site         — site the employee actually worked from on this date
#   * working_site — granular field-level "working site" for the day
# Both writable from SPIM Lite (and from the Suite admin save flow).
# Existing rows are left with empty defaults.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0003_purge_future_sunday_holidays'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendancerecord',
            name='site',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
        migrations.AddField(
            model_name='attendancerecord',
            name='working_site',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
    ]
