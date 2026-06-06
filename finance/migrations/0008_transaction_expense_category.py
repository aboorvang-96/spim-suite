# Generated manually for Income/Expense restructure.
# Adds a fixed-choice expense_category field to the Transaction model.
# Choices: Food / Fuel / Ticket / Travel / Other. Used by the new
# site-grouped Expense detail panel and its Add/Edit modal. Distinct from
# the flexible `category` FK so existing category data is preserved.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0007_transaction_income_source_source_account'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='expense_category',
            field=models.CharField(
                blank=True,
                choices=[
                    ('food',   'Food'),
                    ('fuel',   'Fuel'),
                    ('ticket', 'Ticket'),
                    ('travel', 'Travel'),
                    ('other',  'Other/Misc'),
                ],
                default='',
                max_length=20,
            ),
        ),
    ]
