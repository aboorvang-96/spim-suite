from django.db import models
from django.conf import settings
from employees.models import Employee

class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('half_day', 'Half Day'),
        ('leave', 'Leave'),
        ('holiday', 'Holiday'),
        ('week_off', 'Week Off'),
        ('no_week_off', 'No Week Off'),
    ]
    SOURCE_CHOICES = [
        ('admin', 'Admin Portal'),
        ('employee', 'Employee Portal/Mobile')
    ]
    admin_id = models.CharField(max_length=20, db_index=True, default='PENDING')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='admin')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ('employee', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.employee.name} - {self.date} - {self.status}"
