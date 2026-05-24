"""
Migration: Task 4 + Task 5 + Task 2 schema additions.

- Employee gets: level, mobile, branch (CharFields, blank-able)
- SalaryUpdate gets: is_payslip_generated, payslip_generated_at, payslip_generated_by
- New model: SalaryStructure (admin_id, job_role, level, base_salary,
  food_allowance, ot_allowance, notes)

All additive — no data backfill required.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0007_employee_mobile_auth_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='level',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='employee',
            name='mobile',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='employee',
            name='branch',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='salaryupdate',
            name='is_payslip_generated',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='salaryupdate',
            name='payslip_generated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='salaryupdate',
            name='payslip_generated_by',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='payslips_generated', to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name='SalaryStructure',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('admin_id', models.CharField(db_index=True, default='PENDING', max_length=20)),
                ('level', models.CharField(max_length=20)),
                ('base_salary', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('food_allowance', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('ot_allowance', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('notes', models.CharField(blank=True, default='', max_length=250)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('job_role', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='salary_structures', to='employees.jobrole',
                )),
            ],
            options={
                'verbose_name': 'Salary Structure',
                'verbose_name_plural': 'Salary Structures',
                'ordering': ['job_role__name', 'level'],
                'unique_together': {('admin_id', 'job_role', 'level')},
            },
        ),
    ]
