from django.conf import settings
from django.db import models

class CompanySettings(models.Model):
    admin_id       = models.CharField(max_length=20, unique=True, db_index=True, default='PENDING')
    name           = models.CharField(max_length=200)
    logo           = models.ImageField(upload_to='company/', null=True, blank=True)
    gst_number     = models.CharField(max_length=50, blank=True)
    address        = models.TextField(blank=True)
    contact_number = models.CharField(max_length=20, blank=True)
    email          = models.EmailField(blank=True)
    modified_by    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='company_settings_modified')
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Company Settings"
        verbose_name_plural = "Company Settings"

    def __str__(self):
        return self.name

    @classmethod
    def get_settings(cls, admin_id):
        return cls.objects.filter(admin_id=admin_id).first()
