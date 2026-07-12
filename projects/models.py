from django.db import models
from django.conf import settings




class Project(models.Model):
    STATUS = (('active','Active'),('on_hold','On Hold'),('completed','Completed'),('cancelled','Cancelled'))
    # Multi-tenant scoping. The DB column has existed (NOT NULL) since
    # migration 0002 (March 2026); the model declaration was lost in a
    # prior edit, leaving the model out of sync with the schema. Declaring
    # the field here restores that sync without altering the DB or
    # generating a new migration. All queries must filter by admin_id.
    admin_id    = models.CharField(max_length=20, db_index=True, default='PENDING')
    name        = models.CharField(max_length=200)
    client      = models.ForeignKey('clients.Client', on_delete=models.SET_NULL, null=True, blank=True, related_name='projects')
    owner       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_projects')
    status      = models.CharField(max_length=15, choices=STATUS, default='active')
    budget      = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    start_date  = models.DateField()
    due_date    = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    # Audit fields, also added by migration 0002. Declared here purely
    # to match the existing schema — without them, an INSERT from the
    # model layer fails because updated_at is NOT NULL in the DB.
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='projects_created')
    modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='projects_modified')
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def task_progress(self):
        total = self.tasks.count()
        if not total:
            return 0
        return int(self.tasks.filter(status='done').count() / total * 100)

class Task(models.Model):
    STATUS   = (('todo','To Do'),('in_progress','In Progress'),('done','Done'))
    PRIORITY = (('low','Low'),('medium','Medium'),('high','High'))
    # Same migration-0002 fields as Project — re-declared so the model
    # matches the schema. admin_id is set automatically server-side from
    # the task's parent project to keep tenancy consistent.
    admin_id    = models.CharField(max_length=20, db_index=True, default='PENDING')
    project     = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    title       = models.CharField(max_length=200)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    status      = models.CharField(max_length=15, choices=STATUS, default='todo')
    priority    = models.CharField(max_length=10, choices=PRIORITY, default='medium')
    due_date    = models.DateField(null=True, blank=True)
    notes       = models.TextField(blank=True)
    modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='tasks_modified')
    updated_at  = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


# ── Work Log Models (inside Projects module) ────────────────────────────────

class MachineLocation(models.Model):
    """
    Machine-number registry: per-tenant, local to this Work Log module only.
    Example names: G-606, WT-204, T-17
    NOT connected to global Site / Branch system.
    """
    admin_id   = models.CharField(max_length=20, db_index=True, default='PENDING')
    name       = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering        = ['name']
        unique_together = (('admin_id', 'name'),)

    def __str__(self):
        return self.name


class WorkStatus(models.Model):
    """Reusable work-detail type options (Painting, Cleaning, Inspection, etc.)."""
    admin_id   = models.CharField(max_length=20, db_index=True, default='PENDING')
    name       = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering        = ['name']
        unique_together = (('admin_id', 'name'),)

    def __str__(self):
        return self.name


class WorkLog(models.Model):
    """Daily machine work log entry."""
    admin_id     = models.CharField(max_length=20, db_index=True, default='PENDING')
    date         = models.DateField()
    location     = models.ForeignKey(
        MachineLocation, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='work_logs',
    )
    site         = models.CharField(max_length=150, blank=True, default='')
    work_details = models.TextField(blank=True, default='')
    tmp          = models.PositiveIntegerField(default=0, verbose_name='Total Man Power')
    company_name = models.CharField(max_length=150, blank=True, default='')  # kept for legacy data
    remarks      = models.CharField(max_length=250, blank=True, default='')
    employees    = models.ManyToManyField(
        'employees.Employee', blank=True, related_name='work_logs',
    )
    created_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='work_logs_created',
    )
    # Locked once an entry is saved for (machine + date). While locked,
    # save/edit/delete are blocked backend-side; the admin must call the
    # unlock endpoint before further changes.
    locked       = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        # DB-level guarantee that Daily Work Log and Work Summary always see
        # exactly one row per (tenant, date, machine). Kills the duplicate
        # window in every write path — admin upsert, mobile get_or_create,
        # legacy work_log_add — at the database instead of trusting each
        # caller to route through update_or_create.
        unique_together = (('admin_id', 'date', 'location'),)

    def __str__(self):
        loc = self.location.name if self.location else '—'
        return f"{self.date} — {loc}"
