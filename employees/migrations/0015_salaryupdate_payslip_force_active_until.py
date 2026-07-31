from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0014_backfill_vehicle_flag'),
    ]

    operations = [
        migrations.AddField(
            model_name='salaryupdate',
            name='payslip_force_active_until',
            field=models.DateField(
                blank=True,
                null=True,
                help_text=(
                    'If set and today <= this date, download stays green '
                    'regardless of the 15th rule'
                ),
            ),
        ),
    ]
