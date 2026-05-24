"""
Seed SPIM Suite test credentials for Organization 1 (admin_id = ADMORG1).

Run from project root with the venv active:
    python seed_org1_logins.py

Creates / refreshes:
  1 Super Admin   super_admin_org1@test.com  / Password123!
  3 Linked Admins admin1_org1@test.com       / Password123!
                  admin2_org1@test.com       / Password123!
                  admin3_org1@test.com       / Password123!

All four users share admin_id='ADMORG1'. Linked admins have parent_admin set
to the super admin. Safe to re-run: existing rows are updated (password reset,
role corrected) rather than duplicated.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import User  # noqa: E402

ADMIN_ID = 'ADMORG1'
PASSWORD = 'Password123!'

SUPER = {
    'email':     'super_admin_org1@test.com',
    'username':  'super_admin_org1',
    'full_name': 'Super Admin Org1',
}

LINKED = [
    {'email': 'admin1_org1@test.com', 'username': 'admin1_org1', 'full_name': 'Admin One Org1'},
    {'email': 'admin2_org1@test.com', 'username': 'admin2_org1', 'full_name': 'Admin Two Org1'},
    {'email': 'admin3_org1@test.com', 'username': 'admin3_org1', 'full_name': 'Admin Three Org1'},
]


def upsert_user(email, username, full_name, role, admin_id, parent=None, is_super=False):
    user, created = User.objects.get_or_create(
        email=email,
        defaults={'username': username},
    )
    user.username     = username
    user.full_name    = full_name
    user.role         = role
    user.admin_id     = admin_id
    user.parent_admin = parent
    user.is_active    = True
    user.is_staff     = is_super
    user.is_superuser = is_super
    user.set_password(PASSWORD)
    user.save()
    return user, created


def main():
    super_user, created = upsert_user(
        SUPER['email'], SUPER['username'], SUPER['full_name'],
        role='admin', admin_id=ADMIN_ID, parent=None, is_super=True,
    )
    print(f"[{'CREATED' if created else 'UPDATED'}] Super Admin: {super_user.email}")

    for spec in LINKED:
        u, was_created = upsert_user(
            spec['email'], spec['username'], spec['full_name'],
            role='admin', admin_id=ADMIN_ID, parent=super_user, is_super=False,
        )
        print(f"[{'CREATED' if was_created else 'UPDATED'}] Linked Admin: {u.email}")

    print("\nAll users share admin_id =", ADMIN_ID)
    print("Password for every account:", PASSWORD)


if __name__ == '__main__':
    main()
