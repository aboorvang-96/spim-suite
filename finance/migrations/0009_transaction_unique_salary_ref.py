from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0008_transaction_expense_category'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='transaction',
            constraint=models.UniqueConstraint(
                fields=['admin_id', 'reference', 'type'],
                condition=Q(reference__startswith='SAL-'),
                name='unique_salary_transaction_ref',
            ),
        ),
    ]
