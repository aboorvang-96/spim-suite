"""
SPIM Lite mobile API support models.

MobileAuthToken: opaque bearer token issued to an authenticated employee
on successful /api/mobile/login/. The token itself is the secret and is
treated like a session id. Tokens have no expiry by default; revoke by
deleting the row (e.g. on password reset). Each device login creates a
new token row (multi-device support).
"""
import secrets
from django.db import models
from employees.models import Employee


def _new_token():
    # 256 bits of entropy -> 43-char urlsafe string
    return secrets.token_urlsafe(32)


class MobileAuthToken(models.Model):
    employee    = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='mobile_tokens',
    )
    key         = models.CharField(max_length=64, unique=True, default=_new_token, db_index=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    last_used   = models.DateTimeField(auto_now=True)
    device_info = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Token({self.employee_id})"
