
# FinanceHub — Corporate Finance & Project Hub

## Quick Start

### 1. Create MySQL Database
```sql
CREATE DATABASE expense_manager CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. Edit .env — set your MySQL password
```
DB_PASSWORD=your_mysql_password
```

### 3. Run setup scripts (in order)
```
python setup_financehub_backend.py
python setup_financehub_templates.py
```

### 4. Install, migrate, run
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations accounts finance projects clients invoices dashboard reports
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Visit: http://127.0.0.1:8000/

## Modules
- Auth (login / register / role-based redirect)
- Dashboard (balance, charts, recent transactions)
- Finance Tracker (income / expenses / categories)
- Projects & Tasks
- Client Directory
- Invoices & Payments
- Financial Reports (monthly + category charts)

## Roles
- Admin: full access to all data
- User: own data only
