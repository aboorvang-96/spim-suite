from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Add Employee.salary_type. Default is 'base_salary' so every existing
    employee row keeps the exact behaviour it has today — the payroll
    engine's Base Salary branch is unchanged. Setting the value to
    'daily_basis' on a row switches only the attendance-earnings formula
    (see employees.views._compute_attendance_breakdown); non-base
    fields (OT / Advance / Deductions / PF / Food) continue to flow
    through the same handlers unchanged.
    """

    dependencies = [
        ('employees', '0011_employee_auth_user_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='salary_type',
            field=models.CharField(
                max_length=20,
                default='base_salary',
                choices=[
                    ('base_salary', 'Base Salary'),
                    ('daily_basis', 'Daily Basis'),
                ],
            ),
        ),
    ]
