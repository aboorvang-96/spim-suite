from django.db import models
from django.conf import settings
from employees.models import Employee
from accounts.date_utils import validate_not_future

class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
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

    # Site / Working Site per attendance record. Distinct from the Employee
    # model's `site` field (which is the employee's home site) — this is the
    # site they actually worked from on this specific date, plus the
    # "working site" (granular field-level location) that can vary daily.
    # Both writable from SPIM Lite when employee marks attendance.
    site         = models.CharField(max_length=150, blank=True, default='')
    working_site = models.CharField(max_length=200, blank=True, default='')

    # Remarks persisted per (employee, date). Locked once saved with a
    # non-empty value — editing requires an explicit unlock so a bulk save
    # can't silently wipe an earlier note.
    remarks         = models.CharField(max_length=500, blank=True, default='')
    remarks_locked  = models.BooleanField(default=False)

    # Optional link to the machine the employee worked on that day, plus the
    # free-text work description. When both are set on save, the attendance
    # write also upserts a projects.WorkLog so the Projects module tree stays
    # in sync (see attendance.services.apply_worklog_sideeffect).
    machine = models.ForeignKey(
        'projects.MachineLocation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='attendance_entries',
    )
    work_details = models.TextField(blank=True, default='')

    # Explicit Client/Site link chosen by the admin in the attendance table
    # (2026-07 Client/Site column). `site_ref` — not `site` — because the
    # `site` CharField above is written by SPIM Lite and must keep its name.
    # UX-only for the admin view; the WorkLog side-effect still derives its
    # site from machine.site. JSON payload keys are clientId / siteId.
    client = models.ForeignKey(
        'projects.ProjectClient',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='attendance_entries',
    )
    site_ref = models.ForeignKey(
        'projects.Site',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='attendance_entries',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ('employee', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.employee.name} - {self.date} - {self.status}"

    def clean(self):
        super().clean()
        validate_not_future(self.date, "Attendance date")

    def save(self, *args, **kwargs):
        # Guard direct .create()/.save() (bulk endpoint uses update_or_create).
        validate_not_future(self.date, "Attendance date")
        super().save(*args, **kwargs)
