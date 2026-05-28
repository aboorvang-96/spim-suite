from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_drop_admin_id_unique'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[
                    ('super_admin', 'Super Admin'),
                    ('admin', 'Admin'),
                    ('user', 'User'),
                ],
                default='user',
                max_length=20,
            ),
        ),
    ]
