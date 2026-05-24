from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0008_role_level_salary_and_payslip_lock'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmployeeLevel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('admin_id', models.CharField(db_index=True, default='PENDING', max_length=20)),
                ('name', models.CharField(max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Employee Level',
                'verbose_name_plural': 'Employee Levels',
                'ordering': ['name'],
                'unique_together': {('admin_id', 'name')},
            },
        ),
    ]
