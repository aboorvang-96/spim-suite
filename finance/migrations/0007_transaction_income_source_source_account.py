from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0006_transaction_location_site_transaction_payment_by_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='income_source',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AlterField(
            model_name='source',
            name='type',
            field=models.CharField(
                choices=[('credit', 'Credit Source'), ('income', 'Income Source'), ('account', 'Account')],
                max_length=10,
            ),
        ),
    ]
