from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0006_salaryupdate_food_allowance_food_usage'),
        ('projects', '0003_machinelocation_worklog'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkStatus',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('admin_id', models.CharField(db_index=True, default='PENDING', max_length=20)),
                ('name', models.CharField(max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='workstatus',
            unique_together={('admin_id', 'name')},
        ),
        migrations.AddField(
            model_name='worklog',
            name='employees',
            field=models.ManyToManyField(
                blank=True,
                related_name='work_logs',
                to='employees.employee',
            ),
        ),
    ]
