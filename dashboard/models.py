from django.db import models

class CompanySettings(models.Model):
    name           = models.CharField(max_length=200)
    logo           = models.ImageField(upload_to='company/', null=True, blank=True)
    gst_number     = models.CharField(max_length=50, blank=True)
    address        = models.TextField(blank=True)
    contact_number = models.CharField(max_length=20, blank=True)
    email          = models.EmailField(blank=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Company Settings"
        verbose_name_plural = "Company Settings"

    def __str__(self):
        return self.name

    @classmethod
    def get_settings(cls):
        return cls.objects.first()
