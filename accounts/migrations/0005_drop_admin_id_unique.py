from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_alter_user_admin_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='admin_id',
            field=models.CharField(blank=True, db_index=True, max_length=20, null=True),
        ),
    ]
