from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0005_employee_mobile_app_password'),
    ]

    operations = [
        migrations.AddField(
            model_name='salaryupdate',
            name='food_allowance',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='salaryupdate',
            name='food_usage',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
    ]
