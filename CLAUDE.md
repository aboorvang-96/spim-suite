# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FinanceHub (Finsight Business Finance) is a Django 4.2-based business finance management system with multi-tenant support. It handles projects, clients, invoices, income/expense tracking, employee salary management, and financial reporting.

**Tech Stack:**
- Django 4.2.11
- MySQL (utf8mb4)
- python-decouple for environment config
- django-widget-tweaks for form rendering
- Pillow for image handling
- python-dateutil for date calculations

## Environment Setup

1. **Python virtual environment**: Located at `.venv/` (already created)
2. **Database**: MySQL required - database name `expense_manager`
3. **Configuration**: `.env` file contains:
   - `SECRET_KEY`
   - `DEBUG`
   - `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`

## Common Development Commands

```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
# or
source .venv/bin/activate  # Linux/Mac

# Run development server
python manage.py runserver
# OR use the provided batch file:
run_server.bat

# Database operations
python manage.py makemigrations [app_name]  # Create migrations for specific app
python manage.py migrate                      # Apply all migrations
python manage.py makemigrations accounts finance projects clients invoices dashboard reports employees income categories branches
python manage.py createsuperuser             # Create admin user

# Collect static files
python manage.py collectstatic

# Check for issues
python manage.py check

# View SQL for a query (in Django shell)
python manage.py shell
>>> from django.db import connection
>>> print(connection.queries)
```

**Note:** The project currently has no test suite. Tests can be added using Django's built-in test framework in `tests.py` files within each app.

## Architecture & Code Structure

### Multi-Tenant Design

All models include an `admin_id` field (CharField, indexed) to segregate data between different admin users/companies. This creates a multi-tenant system where:
- Each user with role='admin' gets a unique `admin_id` (format: ADMxxxxx)
- All queries must filter by `admin_id` to isolate tenant data
- `User.parent_admin` allows linking users to an admin

**Example filtering pattern:**
```python
Transaction.objects.filter(admin_id=request.user.admin_id)
```

### Apps & Their Purposes

| App | Purpose |
|-----|---------|
| `accounts` | Authentication, custom User model (email/username), login/register, forgot password |
| `dashboard` | Main dashboard, company settings, balance overview, charts |
| `finance` | Categories (income/expense), Transactions model |
| `projects` | Projects and Tasks (to-do tracking) |
| `clients` | Client management |
| `invoices` | Invoice generation, InvoiceItem line items, status tracking |
| `employees` | Employee records, bank details, PF details, salary history/payslips |
| `reports` | Financial reporting views |
| `income` | Separate income tracking (distinct from finance?) |
| `categories` | Category management (potential duplication with finance) |
| `branches` | Branch management |
| `core` | Utility/core functions |

### Key Models

**User (accounts):**
- Custom user using `AbstractBaseUser` + `PermissionsMixin`
- `USERNAME_FIELD = 'email'`, `REQUIRED_FIELDS = ['username']`
- Roles: 'admin' or 'user'
- Auto-generated `admin_id` for admin users

**CompanySettings (dashboard):**
- Singleton-like model per admin_id
- Stores company name, logo, GST, address, contact info

**Transaction (finance):**
- Income/expense tracking with category, payment mode, receipt attachment
- Created/modified by user tracking

**Invoice/InvoiceItem (invoices):**
- Invoice with line items, tax calculation, status workflow
- Properties: `subtotal`, `tax_amount`, `total`

**Project/Task (projects):**
- Projects with status, budget, client optional
- Tasks with priority, status (todo/in_progress/done), assignment

**Employee/BankDetail/PFDetail/SalaryUpdate (employees):**
- Comprehensive employee management
- OneToOne relations for bank and PF details
- SalaryUpdate as historical record/payslip source

### Important Conventions

1. **Admin ID Filtering**: Always filter querysets by `admin_id` in views
2. **User ForeignKeys**: Use `settings.AUTH_USER_MODEL` for all user references
3. **Created/Modified Tracking**: Most models have:
   - `created_by` (FK to User, SET_NULL on delete)
   - `modified_by` (FK to User, SET_NULL on delete)
   - `created_at` (auto_now_add)
   - `updated_at` (auto_now)
4. **DecimalFields**: Use for all monetary amounts (max_digits=12, decimal_places=2 typical)
5. **Image/File Uploads**: Use `MEDIA_URL`/`MEDIA_ROOT`; upload_to subdirectories: 'avatars/', 'company/', 'receipts/'
6. **Role-based Access**:
   - `@login_required` for authenticated access
   - `@admin_required` decorator (accounts/views.py) for admin-only views
7. **Template Structure**: `templates/<app_name>/<template>.html`; base template at `templates/base.html`
8. **Static Files**: `static/` directory; use `{% load static %}`; collect to `staticfiles/`
9. **URL Namespacing**: Each app uses its own namespace (e.g., 'dashboard:index')

### Template Rendering

Uses `django-widget-tweaks` for form field customization in templates:
```django
{% load widget_tweaks %}
{{ form.field|add_class:"form-control" }}
```

### Database Configuration

Settings in `config/settings.py`:
- MySQL backend with `utf8mb4` charset
- `OPTIONS: {'charset': 'utf8mb4'}`
- Media and static file serving configured
- Time zone: `Asia/Kolkata`
- Currency: `₹` (INR)

## Important Files to Know

- `config/settings.py` - Django settings, database, templates, static/media
- `config/urls.py` - Main URL routing, includes all app URLs
- `manage.py` - Django management script
- `.env` - Environment variables (DB credentials, SECRET_KEY, DEBUG)
- `templates/base.html` - Base template all others extend

## Development Workflow

1. Make model changes in appropriate app's `models.py`
2. Run `python manage.py makemigrations [app]`
3. Run `python manage.py migrate`
4. Update views/forms/templates as needed
5. Test manually (no automated tests)
6. Use `@login_required` and `@admin_required` appropriately
7. Ensure all queries filter by `admin_id` for security

## Migration History Snapshot

Recent work involved a "backup before desktop rebuild" (commit 5bb662b). Current branch: `backup_before_ui_rebuild`. Multiple model changes are staged across apps (accounts, clients, dashboard, employees, finance, invoices, projects, categories).

## Current State Notes

- Many `.pyc` files are modified (clean with `find . -name "*.pyc" -delete` if needed)
- `run_server.bat` provides easy Windows startup
- `SALARY_MANAGER_*.md` files contain documentation for the salary management feature
- No CI/CD pipeline detected (no GitHub Actions workflows)
- No pre-commit hooks configured (only sample hooks exist)
- No test suite present

## Potential Pitfalls

- Forgetting `admin_id` filter exposes all tenants' data
- Hard-coded paths - project assumes Windows path `E:\Freelancing\Finsight_Business_Finance`
- Missing `.env` values will cause startup failures
- Static files need `collectstatic` for production deployment
- Image uploads require `Pillow` and proper media serving

## Quick Reference

**Start development:** `run_server.bat` or `python manage.py runserver`
**Admin panel:** `/admin/`
**Login:** `/auth/login/`
**Dashboard:** `/dashboard/`
