from django.db import migrations, models
import api.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('employees', '0007_employee_mobile_auth_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='MobileAuthToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('key', models.CharField(db_index=True, default=api.models._new_token, max_length=64, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_used', models.DateTimeField(auto_now=True)),
                ('device_info', models.CharField(blank=True, default='', max_length=255)),
                ('employee', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='mobile_tokens', to='employees.employee')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
