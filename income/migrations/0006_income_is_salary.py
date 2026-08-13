from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('income', '0005_income_from_account_income_to_account_income_remarks'),
    ]

    operations = [
        migrations.AddField(
            model_name='income',
            name='is_salary',
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
