from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0004_jobrole_employee_job_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='mobile_app_password',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
    ]
