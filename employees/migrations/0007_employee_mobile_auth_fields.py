from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0006_salaryupdate_food_allowance_food_usage'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='employee_login_id',
            field=models.CharField(blank=True, db_index=True, default='', max_length=50),
        ),
        migrations.AddField(
            model_name='employee',
            name='employee_id_edit_count',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='employee',
            name='mobile_password_hash',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='employee',
            name='mobile_password_reset_required',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='employee',
            name='mobile_account_active',
            field=models.BooleanField(default=True),
        ),
    ]
