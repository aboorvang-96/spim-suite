from django.db import models
from django.conf import settings

class Client(models.Model):
    name       = models.CharField(max_length=200)
    email      = models.EmailField(blank=True)
    phone      = models.CharField(max_length=30, blank=True)
    company    = models.CharField(max_length=200, blank=True)
    address    = models.TextField(blank=True)
    website    = models.URLField(blank=True)
    notes      = models.TextField(blank=True)
    added_by   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='clients')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
