from django.apps import AppConfig


class AttendanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'attendance'

    def ready(self):
        # Register the AttendanceRecord post_save signal that mirrors
        # earnings into finance.Transaction as salary_attendance rows.
        from . import signals  # noqa: F401
