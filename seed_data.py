import os
import django
import random
import datetime
from decimal import Decimal

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction
from branches.models import Branch, LocationSite
from employees.models import JobRole, Employee, BankDetail, PFDetail, SalaryUpdate
from attendance.models import AttendanceRecord
from categories.models import IncomeCategory, ExpenseCategory
from income.models import Income
from finance.models import Category as FinanceCategory, Transaction as FinanceTransaction

User = get_user_model()

@transaction.atomic
def seed():
    print("Starting database seeding...")

    # ==========================================
    # 1. CREATE USER ACCOUNTS
    # ==========================================
    print("Creating admin users...")
    
    # Org 1 Users (admin_id: ADMORG1)
    super_admin_org1, created = User.objects.get_or_create(
        email='super_admin_org1@test.com',
        defaults={
            'username': 'super_admin_org1',
            'full_name': 'Org1 Super Admin',
            'role': 'admin',
            'admin_id': 'ADMORG1',
            'is_staff': True,
        }
    )
    if created or not super_admin_org1.check_password('Password123!'):
        super_admin_org1.set_password('Password123!')
        super_admin_org1.save()

    admins_org1_data = [
        ('admin1_org1@test.com', 'admin1_org1', 'Org1 Admin 1'),
        ('admin2_org1@test.com', 'admin2_org1', 'Org1 Admin 2'),
        ('admin3_org1@test.com', 'admin3_org1', 'Org1 Admin 3'),
    ]
    
    admins_org1 = []
    for email, username, full_name in admins_org1_data:
        adm, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': username,
                'full_name': full_name,
                'role': 'admin',
                'admin_id': 'ADMORG1',
                'parent_admin': super_admin_org1,
                'is_staff': True,
            }
        )
        if created or not adm.check_password('Password123!'):
            adm.set_password('Password123!')
            adm.save()
        admins_org1.append(adm)

    # Org 2 Users (admin_id: ADMORG2) - Isolation Testing
    super_admin_org2, created = User.objects.get_or_create(
        email='super_admin_org2@test.com',
        defaults={
            'username': 'super_admin_org2',
            'full_name': 'Org2 Super Admin',
            'role': 'admin',
            'admin_id': 'ADMORG2',
            'is_staff': True,
        }
    )
    if created or not super_admin_org2.check_password('Password123!'):
        super_admin_org2.set_password('Password123!')
        super_admin_org2.save()

    admin1_org2, created = User.objects.get_or_create(
        email='admin1_org2@test.com',
        defaults={
            'username': 'admin1_org2',
            'full_name': 'Org2 Admin 1',
            'role': 'admin',
            'admin_id': 'ADMORG2',
            'parent_admin': super_admin_org2,
            'is_staff': True,
        }
    )
    if created or not admin1_org2.check_password('Password123!'):
        admin1_org2.set_password('Password123!')
        admin1_org2.save()

    # ==========================================
    # 2. CREATE BRANCHES & LOCATION SITES
    # ==========================================
    print("Creating branches and sites...")
    
    # Org 1 Branches
    branch_names_org1 = ["Giga HQ", "Mega Site Alpha", "Delta Factory"]
    branches_org1 = []
    for idx, name in enumerate(branch_names_org1):
        branch, created = Branch.objects.get_or_create(
            name=name,
            admin_id='ADMORG1',
            defaults={
                'code': f'BR-{idx+1:03d}',
                'location': f'Location of {name}',
                'manager': f'Manager of {name}',
                'created_by': super_admin_org1,
            }
        )
        branches_org1.append(branch)
        
        # Centralized registry LocationSite
        LocationSite.objects.get_or_create(
            admin_id='ADMORG1',
            name=name,
            defaults={'created_by': super_admin_org1}
        )

    # Org 2 Branch
    branch_org2, created = Branch.objects.get_or_create(
        name="Org2 Branch A",
        admin_id='ADMORG2',
        defaults={
            'code': 'BR-O2A',
            'location': 'Location A in Org 2',
            'manager': 'Manager A in Org 2',
            'created_by': super_admin_org2,
        }
    )
    LocationSite.objects.get_or_create(
        admin_id='ADMORG2',
        name="Org2 Branch A",
        defaults={'created_by': super_admin_org2}
    )

    # ==========================================
    # 3. CREATE JOB ROLES & EMPLOYEES
    # ==========================================
    print("Creating job roles and employees...")
    
    # Org 1 Job Roles
    job_roles_org1_data = [
        ("Software Engineer", "monthly", 80000.00),
        ("Site Supervisor", "monthly", 55000.00),
        ("Field Engineer", "daily", 1500.00),  # Daily wage
        ("Admin Assistant", "monthly", 40000.00),
        ("HR Manager", "monthly", 65000.00),
        ("Security Officer", "daily", 900.00),   # Daily wage
    ]
    job_roles_org1 = {}
    for name, salary_type, base_salary in job_roles_org1_data:
        jr, created = JobRole.objects.get_or_create(
            admin_id='ADMORG1',
            name=name,
            defaults={
                'salary_type': salary_type,
                'base_salary': Decimal(base_salary)
            }
        )
        job_roles_org1[name] = jr

    # Org 2 Job Role
    jr_org2, created = JobRole.objects.get_or_create(
        admin_id='ADMORG2',
        name="Org2 JobRole A",
        defaults={
            'salary_type': 'monthly',
            'base_salary': Decimal(50000.00)
        }
    )

    # Org 1 Employees (Minimum 15 - let's create 16)
    employees_data = [
        ("John Doe", "Software Engineer", "Engineering", "Giga HQ", 80000, 5000, "2023-01-15"),
        ("Jane Smith", "Software Engineer", "Engineering", "Giga HQ", 75000, 4500, "2023-03-10"),
        ("Bob Johnson", "Site Supervisor", "Operations", "Mega Site Alpha", 55000, 3000, "2024-02-01"),
        ("Alice Brown", "Field Engineer", "Operations", "Mega Site Alpha", 45000, 2000, "2024-05-15"),
        ("Charlie Davis", "Field Engineer", "Operations", "Delta Factory", 48000, 2200, "2024-06-01"),
        ("Diana Evans", "Admin Assistant", "Admin", "Giga HQ", 40000, 1500, "2024-08-20"),
        ("Ethan Foster", "HR Manager", "HR", "Giga HQ", 65000, 4000, "2023-11-01"),
        ("Fiona Green", "Security Officer", "Security", "Delta Factory", 27000, 1000, "2025-01-10"),
        ("George Harris", "Site Supervisor", "Operations", "Delta Factory", 52000, 2800, "2024-04-10"),
        ("Hannah Jackson", "Software Engineer", "Engineering", "Giga HQ", 85000, 5500, "2022-10-01"),
        ("Ian Kelly", "Field Engineer", "Operations", "Mega Site Alpha", 49000, 2300, "2024-07-15"),
        ("Julia Lewis", "Admin Assistant", "Admin", "Giga HQ", 42000, 1800, "2024-09-01"),
        ("Kevin Miller", "Security Officer", "Security", "Mega Site Alpha", 28000, 1100, "2025-02-01"),
        ("Laura Nelson", "Field Engineer", "Operations", "Delta Factory", 51000, 2500, "2024-03-01"),
        ("Mike Owen", "Software Engineer", "Engineering", "Giga HQ", 78000, 4800, "2023-06-15"),
        ("Nancy Perez", "HR Manager", "HR", "Giga HQ", 60000, 3500, "2024-10-15"),
    ]

    employees_org1 = []
    # Let's rotate creators among Org 1 admins to test shared-data validation behavior
    org1_creators = [super_admin_org1] + admins_org1

    for idx, (name, role_name, dept, loc, salary, allowance, join_date) in enumerate(employees_data):
        creator = org1_creators[idx % len(org1_creators)]
        
        emp, created = Employee.objects.get_or_create(
            admin_id='ADMORG1',
            name=name,
            defaults={
                'employee_id': f'EMP-{100+idx:03d}',
                'mobile_app_password': 'password123',
                'designation': role_name,
                'department': dept,
                'location': loc,
                'site': loc,
                'base_salary': Decimal(salary),
                'fixed_allowance': Decimal(allowance),
                'joining_date': datetime.datetime.strptime(join_date, "%Y-%m-%d").date(),
                'status': 'active',
                'job_role': job_roles_org1[role_name],
                'created_by': creator,
            }
        )
        employees_org1.append(emp)

        # OneToOne Bank details
        BankDetail.objects.get_or_create(
            employee=emp,
            defaults={
                'bank_name': 'Test Business Bank',
                'account_holder': name,
                'account_number': f'999888000{idx:02d}',
                'ifsc_code': 'TBBK0001234',
                'branch': 'Central Branch',
                'status': 'verified',
                'modified_by': creator,
            }
        )

        # OneToOne PF details
        PFDetail.objects.get_or_create(
            employee=emp,
            defaults={
                'pf_number': f'MH/BAN/0000{idx:02d}/000/0000123',
                'uan_number': f'1009998887{idx:02d}',
                'esic_number': f'31000099998887{idx:02d}',
                'status': 'added',
                'employee_contribution': Decimal(1800.00),
                'employer_contribution': Decimal(1800.00),
                'joining_date': emp.joining_date,
                'modified_by': creator,
            }
        )

    # Org 2 Employees
    employees_org2 = []
    for idx in range(2):
        emp, created = Employee.objects.get_or_create(
            admin_id='ADMORG2',
            name=f"Org2 Employee {idx+1}",
            defaults={
                'employee_id': f'EMP-O2-{idx+1:02d}',
                'designation': 'Staff',
                'department': 'General',
                'location': 'Org2 Branch A',
                'site': 'Org2 Branch A',
                'base_salary': Decimal(35000),
                'joining_date': datetime.date(2025, 1, 1),
                'status': 'active',
                'job_role': jr_org2,
                'created_by': super_admin_org2,
            }
        )
        employees_org2.append(emp)
        BankDetail.objects.get_or_create(
            employee=emp,
            defaults={
                'bank_name': 'Org2 Bank',
                'account_holder': emp.name,
                'account_number': f'8888000{idx:02d}',
                'ifsc_code': 'ORGBK000123',
                'status': 'verified',
            }
        )
        PFDetail.objects.get_or_create(
            employee=emp,
            defaults={
                'pf_number': f'PF-O2-{idx:02d}',
                'status': 'added',
            }
        )

    # ==========================================
    # 4. CREATE ATTENDANCE RECORDS (April 26 -> May 21)
    # ==========================================
    print("Creating realistic attendance records (April 26 to May 21)...")
    
    start_date = datetime.date(2026, 4, 26)
    end_date = datetime.date(2026, 5, 21)
    delta = end_date - start_date
    
    # Let's seed random generator for reproducibility, but with variation
    random.seed(42)

    total_rec_count = 0
    # Org 1 attendance
    for emp in employees_org1:
        for i in range(delta.days + 1):
            curr_date = start_date + datetime.timedelta(days=i)
            # Sunday check
            if curr_date.weekday() == 6: # Sunday
                # Sunday off
                status = 'leave'
                remark = 'Sunday weekly off'
            else:
                # Weekdays: Present (88%), Half Day (5%), Leave (4%), Absent (3%)
                r = random.random()
                if r < 0.88:
                    status = 'present'
                    remark = 'On time'
                elif r < 0.93:
                    status = 'half_day'
                    remark = 'Personal work / Half day'
                elif r < 0.97:
                    status = 'leave'
                    remark = 'Prior permission leave'
                else:
                    status = 'absent'
                    remark = 'Absent without notice'
            
            creator = org1_creators[total_rec_count % len(org1_creators)]
            AttendanceRecord.objects.get_or_create(
                employee=emp,
                date=curr_date,
                defaults={
                    'admin_id': 'ADMORG1',
                    'status': status,
                    'source': 'admin',
                    'created_by': creator,
                }
            )
            total_rec_count += 1

    # Org 2 attendance (perfect attendance just for contrast)
    for emp in employees_org2:
        for i in range(delta.days + 1):
            curr_date = start_date + datetime.timedelta(days=i)
            AttendanceRecord.objects.get_or_create(
                employee=emp,
                date=curr_date,
                defaults={
                    'admin_id': 'ADMORG2',
                    'status': 'present',
                    'source': 'admin',
                    'created_by': super_admin_org2,
                }
            )

    # ==========================================
    # 5. CREATE CATEGORIES
    # ==========================================
    print("Creating categories...")
    
    # Org 1 Categories - finance app (Category)
    finance_inc_cats = ["Client Project Billings", "Retainer Fees", "Product Sales", "Interest Income"]
    finance_exp_cats = ["Office Rent", "Employee Salaries", "Utilities", "Office Supplies", "Travel Expenses", "Subcontractors"]
    
    f_cats = {}
    for name in finance_inc_cats:
        cat, created = FinanceCategory.objects.get_or_create(
            admin_id='ADMORG1',
            name=name,
            type='income',
            defaults={
                'color': '#10b981',
                'created_by': super_admin_org1,
            }
        )
        f_cats[('income', name)] = cat

    for name in finance_exp_cats:
        cat, created = FinanceCategory.objects.get_or_create(
            admin_id='ADMORG1',
            name=name,
            type='expense',
            defaults={
                'color': '#ef4444',
                'created_by': super_admin_org1,
            }
        )
        f_cats[('expense', name)] = cat

    # Org 1 Categories - categories app (IncomeCategory, ExpenseCategory)
    income_cats_org1 = ["Project Billings", "Product Support", "Advisory Services"]
    expense_cats_org1 = ["Office Maintenance", "Employee Payroll", "Broadband & Phone", "Software Licenses", "Business Travel"]
    
    inc_cats_map = {}
    for name in income_cats_org1:
        cat, created = IncomeCategory.objects.get_or_create(
            name=name,
            created_by=super_admin_org1,
            defaults={'color': '#10b981'}
        )
        inc_cats_map[name] = cat
        
    exp_cats_map = {}
    for name in expense_cats_org1:
        cat, created = ExpenseCategory.objects.get_or_create(
            name=name,
            created_by=super_admin_org1,
            defaults={'color': '#ef4444'}
        )
        exp_cats_map[name] = cat

    # Org 2 Categories
    cat_inc_o2, _ = FinanceCategory.objects.get_or_create(
        admin_id='ADMORG2', name="Org2 Income Cat", type='income', created_by=super_admin_org2
    )
    cat_exp_o2, _ = FinanceCategory.objects.get_or_create(
        admin_id='ADMORG2', name="Org2 Expense Cat", type='expense', created_by=super_admin_org2
    )

    # ==========================================
    # 6. CREATE TRANSACTIONS AND INCOMES
    # ==========================================
    print("Creating financial transactions and income records...")
    
    # We will create various transactions from April 26 to May 21
    # Rotate creators and branches for variety
    modes = ['cash', 'bank', 'upi']
    
    # 1. Income Transactions
    income_items = [
        ("Acme Corp Milestones", 250000.00, "Client Project Billings"),
        ("Globex Retainer April", 75000.00, "Retainer Fees"),
        ("Initech Consulting Fees", 120000.00, "Client Project Billings"),
        ("Hardware Spares Sale", 15000.00, "Product Sales"),
        ("Hooli Inc Billing", 185000.00, "Client Project Billings"),
    ]
    
    for idx, (desc, amt, cat_name) in enumerate(income_items):
        creator = org1_creators[idx % len(org1_creators)]
        branch = branches_org1[idx % len(branches_org1)]
        
        t_date = start_date + datetime.timedelta(days=idx*4)
        FinanceTransaction.objects.create(
            user=creator,
            type='income',
            category=f_cats[('income', cat_name)],
            amount=Decimal(amt),
            description=desc,
            date=t_date,
            payment_mode=random.choice(modes),
            branch=branch,
            admin_id='ADMORG1',
            created_by=creator,
        )

    # 2. Expense Transactions (Rent, Utilities, Travel)
    expense_items = [
        ("Office Rent May", 45000.00, "Office Rent"),
        ("Internet and VoIP Services", 3500.00, "Utilities"),
        ("Electricity Bill Delta Factory", 12500.00, "Utilities"),
        ("Travel Reimbursements - Site Alpha Visit", 8200.00, "Travel Expenses"),
        ("Stationery & Refreshments HQ", 2500.00, "Office Supplies"),
        ("Subcontractor Safety Audit Fees", 35000.00, "Subcontractors"),
    ]
    
    for idx, (desc, amt, cat_name) in enumerate(expense_items):
        creator = org1_creators[(idx + 1) % len(org1_creators)]
        branch = branches_org1[(idx + 1) % len(branches_org1)]
        t_date = start_date + datetime.timedelta(days=idx*3 + 2)
        
        FinanceTransaction.objects.create(
            user=creator,
            type='expense',
            category=f_cats[('expense', cat_name)],
            amount=Decimal(amt),
            description=desc,
            date=t_date,
            payment_mode=random.choice(modes),
            branch=branch,
            admin_id='ADMORG1',
            created_by=creator,
        )

    # 3. Income Records (income app - separate tracker)
    income_tracker_items = [
        ("Direct Consultation - Site Setup", 35000.00, "Advisory Services"),
        ("System Integration Service Fees", 62000.00, "Project Billings"),
        ("Hardware Setup Support Alpha", 18000.00, "Product Support"),
    ]
    for idx, (title, amt, cat_name) in enumerate(income_tracker_items):
        creator = org1_creators[(idx + 2) % len(org1_creators)]
        t_date = start_date + datetime.timedelta(days=idx*5 + 1)
        
        Income.objects.create(
            user=creator,
            admin_id='ADMORG1',
            title=title,
            amount=Decimal(amt),
            category=inc_cats_map[cat_name],
            date=t_date,
            source='Direct Client Deposit',
            description=f'Income record for {title}',
            payment_mode='bank_transfer',
            location_site=branches_org1[idx % len(branches_org1)].name,
            payment_by='Client Inc.'
        )

    # Org 2 Transactions
    FinanceTransaction.objects.create(
        user=super_admin_org2,
        type='income',
        category=cat_inc_o2,
        amount=Decimal(25000.00),
        description="Org2 Income Description",
        date=datetime.date(2026, 5, 1),
        payment_mode='cash',
        branch=branch_org2,
        admin_id='ADMORG2',
        created_by=super_admin_org2,
    )
    FinanceTransaction.objects.create(
        user=super_admin_org2,
        type='expense',
        category=cat_exp_o2,
        amount=Decimal(5000.00),
        description="Org2 Expense Description",
        date=datetime.date(2026, 5, 2),
        payment_mode='cash',
        branch=branch_org2,
        admin_id='ADMORG2',
        created_by=super_admin_org2,
    )

    print("Database seeding completed successfully!")

if __name__ == '__main__':
    seed()
