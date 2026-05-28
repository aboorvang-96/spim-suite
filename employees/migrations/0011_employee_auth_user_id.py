from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0010_employee_salary_is_custom_override_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='auth_user_id',
            field=models.UUIDField(blank=True, db_index=True, null=True, unique=True),
        ),
    ]
