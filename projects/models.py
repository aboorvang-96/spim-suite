from django.db import models
from django.conf import settings

class Project(models.Model):
    STATUS = (('active','Active'),('on_hold','On Hold'),('completed','Completed'),('cancelled','Cancelled'))
    name        = models.CharField(max_length=200)
    client      = models.ForeignKey('clients.Client', on_delete=models.SET_NULL, null=True, blank=True, related_name='projects')
    owner       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_projects')
    status      = models.CharField(max_length=15, choices=STATUS, default='active')
    budget      = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    start_date  = models.DateField()
    due_date    = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

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
    project     = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    title       = models.CharField(max_length=200)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    status      = models.CharField(max_length=15, choices=STATUS, default='todo')
    priority    = models.CharField(max_length=10, choices=PRIORITY, default='medium')
    due_date    = models.DateField(null=True, blank=True)
    notes       = models.TextField(blank=True)

    def __str__(self):
        return self.title
