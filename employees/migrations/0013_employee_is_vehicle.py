from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Schema migration: add the `is_vehicle` flag to Employee.

    Vehicles are stored as Employee rows (registration number in `name`) and
    are surfaced in a dedicated "Vehicles" section across Employee Master,
    Salary Management, and Attendance Registry. This flag drives that visual
    split only — no salary/attendance business logic branches on it.

    All existing rows default to False. The data backfill that flips known
    vehicle rows to True lives in the follow-up migration 0014.

    Deliberately hand-written to contain ONLY the is_vehicle AddField.
    `makemigrations` also wants to emit unrelated AutoField -> BigAutoField
    alterations on employeelevel/salarystructure ids (DEFAULT_AUTO_FIELD drift
    predating this task); those are intentionally excluded to keep this change
    surgical and within scope.
    """

    dependencies = [
        ('employees', '0012_employee_salary_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='is_vehicle',
            field=models.BooleanField(default=False, db_index=True),
        ),
    ]
