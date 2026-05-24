import secrets
from django import forms
from django.contrib.auth import authenticate
from .models import User


ACCOUNT_TYPE_CHOICES = (
    ('super_admin', 'Super Admin'),
    ('admin', 'Admin'),
)


def _generate_admin_id():
    """Generate a unique organization tenant id (ADM + 6 hex chars)."""
    for _ in range(10):
        candidate = 'ADM' + secrets.token_hex(3).upper()
        if not User.objects.filter(admin_id=candidate, parent_admin__isnull=True).exists():
            return candidate
    # fallback widening to 8 chars (collision after 10 retries is astronomically unlikely)
    return 'ADM' + secrets.token_hex(4).upper()


class LoginForm(forms.Form):
    account_type = forms.ChoiceField(
        choices=ACCOUNT_TYPE_CHOICES,
        initial='super_admin',
        widget=forms.RadioSelect,
    )
    email    = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        email = self.cleaned_data.get('email')
        pwd   = self.cleaned_data.get('password')
        account_type = self.cleaned_data.get('account_type')
        if email and pwd:
            self.user = authenticate(username=email, password=pwd)
            if not self.user:
                raise forms.ValidationError("Invalid email or password.")
            if not self.user.is_active:
                raise forms.ValidationError("This account has been deactivated.")
            # Validate selected login type matches the actual account type.
            if account_type == 'super_admin' and not self.user.is_super_admin:
                raise forms.ValidationError("This account is not a Super Admin. Please select 'Admin'.")
            if account_type == 'admin' and not self.user.is_linked_admin:
                raise forms.ValidationError("This account is a Super Admin. Please select 'Super Admin'.")
        return self.cleaned_data

    def get_user(self):
        return self.user


class RegisterForm(forms.ModelForm):
    account_type = forms.ChoiceField(
        choices=ACCOUNT_TYPE_CHOICES,
        initial='super_admin',
        widget=forms.RadioSelect,
    )
    org_code  = forms.CharField(required=False, max_length=20,
                                help_text="Required for Admin: the Super Admin's organization code.")
    password  = forms.CharField(widget=forms.PasswordInput, min_length=8)
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm password")

    class Meta:
        model  = User
        fields = ['full_name', 'username', 'email']

    def clean_username(self):
        u = self.cleaned_data['username']
        if User.objects.filter(username=u).exists():
            raise forms.ValidationError("Username already taken.")
        return u

    def clean_email(self):
        e = self.cleaned_data['email']
        if User.objects.filter(email=e).exists():
            raise forms.ValidationError("Email already registered.")
        return e

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")

        account_type = cleaned.get('account_type')
        org_code = (cleaned.get('org_code') or '').strip().upper()

        if account_type == 'admin':
            if not org_code:
                self.add_error('org_code', "Organization code is required to register as Admin.")
            else:
                # Super Admin = admin role + admin_id set + no parent_admin
                super_admin = User.objects.filter(
                    admin_id=org_code,
                    role='admin',
                    parent_admin__isnull=True,
                ).first()
                if not super_admin:
                    self.add_error('org_code', "Invalid organization code. No Super Admin found for this code.")
                else:
                    self._linked_super_admin = super_admin
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        # Both Super Admin and linked Admin share the same role/permission scope.
        user.role = 'admin'
        account_type = self.cleaned_data.get('account_type')
        if account_type == 'super_admin':
            user.admin_id = _generate_admin_id()
            user.parent_admin = None
        else:
            super_admin = getattr(self, '_linked_super_admin', None)
            # clean() guarantees super_admin exists when account_type == 'admin'
            user.admin_id = super_admin.admin_id
            user.parent_admin = super_admin
        if commit:
            user.save()
        return user
