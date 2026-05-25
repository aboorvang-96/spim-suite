from django.db import models
from django.conf import settings


class LocationSite(models.Model):
    """Centralized location/site registry shared across all modules."""
    admin_id   = models.CharField(max_length=20, db_index=True, default='PENDING')
    name       = models.CharField(max_length=250)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='location_sites_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering        = ['name']
        unique_together = [('admin_id', 'name')]

    def __str__(self):
        return self.name


class Branch(models.Model):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, blank=True, null=True)
    location = models.CharField(max_length=200, blank=True, null=True)
    manager = models.CharField(max_length=150, blank=True, null=True)
    note = models.TextField(blank=True, null=True)

    admin_id    = models.CharField(max_length=20, db_index=True, default='PENDING')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Branches'
        ordering = ['name']

    def __str__(self):
        return self.name
