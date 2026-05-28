from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

class UserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra):
        email = self.normalize_email(email)
        user  = self.model(email=email, username=username, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra):
        extra.setdefault('role', 'admin')
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        return self.create_user(email, username, password, **extra)

class User(AbstractBaseUser, PermissionsMixin):
    ROLES = (
        ('super_admin', 'Super Admin'),
        ('admin', 'Admin'),
        ('user', 'User'),
    )
    email       = models.EmailField(unique=True)
    username    = models.CharField(max_length=60, unique=True)
    full_name   = models.CharField(max_length=120, blank=True)
    role        = models.CharField(max_length=20, choices=ROLES, default='user')
    avatar      = models.ImageField(upload_to='avatars/', blank=True, null=True)
    is_active   = models.BooleanField(default=True)
    is_staff    = models.BooleanField(default=False)
    phone       = models.CharField(max_length=20, blank=True)
    # admin_id is the organization/tenant key. Super Admin owns a new admin_id;
    # linked Admins share the same admin_id (so it is NOT unique per user).
    admin_id    = models.CharField(max_length=20, null=True, blank=True, db_index=True)
    parent_admin = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='linked_users')
    theme       = models.CharField(max_length=15, default='light')
    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['username']
    objects = UserManager()

    def __str__(self):
        return self.full_name or self.username

    @property
    def is_admin(self):
        """Has admin permission scope (Super Admin or linked Admin)."""
        return self.role in ('admin', 'super_admin')

    @property
    def is_super_admin(self):
        """Super Admin owns the org (no parent). New rows store role='super_admin';
        legacy rows still detected via role='admin' + no parent + admin_id set."""
        if self.role == 'super_admin':
            return True
        return self.role == 'admin' and self.parent_admin_id is None and bool(self.admin_id)

    @property
    def is_linked_admin(self):
        """Admin linked under a Super Admin's organization dataset."""
        return self.role == 'admin' and self.parent_admin_id is not None

    @property
    def initials(self):
        parts = (self.full_name or self.username).split()
        return (parts[0][0] + (parts[1][0] if len(parts) > 1 else '')).upper()
