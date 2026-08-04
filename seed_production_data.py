import os
import sys
import django
import random
import datetime
import calendar
from decimal import Decimal

# Set up Django environment
sys.path.append(r'E:\Freelancing\SPIM Suite')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum
from branches.models import Branch, LocationSite
from employees.models import JobRole, Employee, BankDetail, PFDetail, SalaryUpdate
from attendance.models import AttendanceRecord
from categories.models import IncomeCategory, ExpenseCategory
from income.models import Income
from finance.models import Category as FinanceCategory, Transaction as FinanceTransaction
from employees.views import _compute_attendance_earnings

User = get_user_model()

@transaction.atomic
def seed():
    print("Clearing existing data...")
    AttendanceRecord.objects.all().delete()
    SalaryUpdate.objects.all().delete()
    BankDetail.objects.all().delete()
    PFDetail.objects.all().delete()
    Employee.objects.all().delete()
    JobRole.objects.all().delete()
    FinanceTransaction.objects.all().delete()
    Income.objects.all().delete()
    Branch.objects.all().delete()
    LocationSite.objects.all().delete()
    FinanceCategory.objects.all().delete()
    IncomeCategory.objects.all().delete()
    ExpenseCategory.objects.all().delete()

    print("Fetching/creating admin users...")
    # Org 1 Super Admin and Admins
    super_admin_org1, _ = User.objects.get_or_create(
        email='super_admin_org1@test.com',
        defaults={
            'username': 'super_admin_org1',
            'full_name': 'Org1 Super Admin',
            'role': 'admin',
            'admin_id': 'ADMORG1',
            'is_staff': True,
        }
    )
    super_admin_org1.set_password('Password123!')
    super_admin_org1.save()

    admins_org1_data = [
        ('admin1_org1@test.com', 'admin1_org1', 'Org1 Admin 1'),
        ('admin2_org1@test.com', 'admin2_org1', 'Org1 Admin 2'),
        ('admin3_org1@test.com', 'admin3_org1', 'Org1 Admin 3'),
    ]
    admins_org1 = []
    for email, username, full_name in admins_org1_data:
        adm, _ = User.objects.get_or_create(
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
        adm.set_password('Password123!')
        adm.save()
        admins_org1.append(adm)

    # Org 2 Super Admin and Admin
    super_admin_org2, _ = User.objects.get_or_create(
        email='super_admin_org2@test.com',
        defaults={
            'username': 'super_admin_org2',
            'full_name': 'Org2 Super Admin',
            'role': 'admin',
            'admin_id': 'ADMORG2',
            'is_staff': True,
        }
    )
    super_admin_org2.set_password('Password123!')
    super_admin_org2.save()

    admin1_org2, _ = User.objects.get_or_create(
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
    admin1_org2.set_password('Password123!')
    admin1_org2.save()

    org1_creators = [super_admin_org1] + admins_org1
    org2_creators = [super_admin_org2, admin1_org2]

    print("Seeding branches...")
    branch_names_org1 = ["Giga HQ", "Mega Site Alpha", "Delta Factory"]
    branches_org1 = []
    for idx, name in enumerate(branch_names_org1):
        branch = Branch.objects.create(
            name=name,
            admin_id='ADMORG1',
            code=f'BR-{idx+1:03d}',
            location=f'Location of {name}',
            manager=f'Manager of {name}',
            created_by=super_admin_org1,
        )
        branches_org1.append(branch)
        LocationSite.objects.create(
            admin_id='ADMORG1',
            name=name,
            created_by=super_admin_org1
        )

    branch_org2 = Branch.objects.create(
        name="Org2 Branch A",
        admin_id='ADMORG2',
        code='BR-O2A',
        location='Location A in Org 2',
        manager='Manager A in Org 2',
        created_by=super_admin_org2,
    )
    LocationSite.objects.create(
        admin_id='ADMORG2',
        name="Org2 Branch A",
        created_by=super_admin_org2
    )

    print("Seeding job roles...")
    job_roles_org1_data = [
        ("Software Engineer", "monthly", 80000.00),
        ("Site Supervisor", "monthly", 55000.00),
        ("Field Engineer", "daily", 1500.00),
        ("Admin Assistant", "monthly", 40000.00),
        ("HR Manager", "monthly", 65000.00),
        ("Security Officer", "daily", 900.00),
        ("HR Assistant", "monthly", 43000.00),
    ]
    job_roles_org1 = {}
    for name, salary_type, base_salary in job_roles_org1_data:
        jr = JobRole.objects.create(
            admin_id='ADMORG1',
            name=name,
            salary_type=salary_type,
            base_salary=Decimal(base_salary)
        )
        job_roles_org1[name] = jr

    jr_org2_a = JobRole.objects.create(
        admin_id='ADMORG2',
        name="Org2 JobRole A",
        salary_type='monthly',
        base_salary=Decimal(50000.00)
    )
    jr_org2_b = JobRole.objects.create(
        admin_id='ADMORG2',
        name="Org2 JobRole B",
        salary_type='daily',
        base_salary=Decimal(1200.00)
    )

    print("Seeding employee profiles (24 Org 1 + 3 Org 2)...")
    emp_org1_data = [
        ("John Doe", "Software Engineer", "Engineering", "Giga HQ", 85000, 5000, "2023-01-15"),
        ("Jane Smith", "Software Engineer", "Engineering", "Giga HQ", 82000, 4500, "2023-03-10"),
        ("Bob Johnson", "Site Supervisor", "Operations", "Mega Site Alpha", 55000, 3000, "2024-02-01"),
        ("Alice Brown", "Field Engineer", "Operations", "Mega Site Alpha", 45000, 2000, "2024-05-15"),
        ("Charlie Davis", "Field Engineer", "Operations", "Delta Factory", 48000, 2200, "2024-06-01"),
        ("Diana Evans", "Admin Assistant", "Admin", "Giga HQ", 40000, 1500, "2024-08-20"),
        ("Ethan Foster", "HR Manager", "HR", "Giga HQ", 65000, 4000, "2023-11-01"),
        ("Fiona Green", "Security Officer", "Security", "Delta Factory", 27000, 1000, "2025-01-10"),
        ("George Harris", "Site Supervisor", "Operations", "Delta Factory", 52000, 2800, "2024-04-10"),
        ("Hannah Jackson", "Software Engineer", "Engineering", "Giga HQ", 90000, 5500, "2022-10-01"),
        ("Ian Kelly", "Field Engineer", "Operations", "Mega Site Alpha", 49000, 2300, "2024-07-15"),
        ("Julia Lewis", "Admin Assistant", "Admin", "Giga HQ", 42000, 1800, "2024-09-01"),
        ("Kevin Miller", "Security Officer", "Security", "Mega Site Alpha", 28000, 1100, "2025-02-01"),
        ("Laura Nelson", "Field Engineer", "Operations", "Delta Factory", 51000, 2500, "2024-03-01"),
        ("Mike Owen", "Software Engineer", "Engineering", "Giga HQ", 78000, 4800, "2023-06-15"),
        ("Nancy Perez", "HR Manager", "HR", "Giga HQ", 60000, 3500, "2024-10-15"),
        ("Oscar Quincy", "Site Supervisor", "Operations", "Mega Site Alpha", 54000, 2900, "2024-11-12"),
        ("Patricia Ross", "Admin Assistant", "Admin", "Mega Site Alpha", 41000, 1600, "2024-12-05"),
        ("Samuel Taylor", "Security Officer", "Security", "Giga HQ", 30000, 1200, "2025-03-01"),
        ("Theresa Underwood", "Field Engineer", "Operations", "Delta Factory", 46000, 2100, "2024-05-20"),
        ("Victor Vance", "Software Engineer", "Engineering", "Giga HQ", 88000, 5200, "2023-08-01"),
        ("Wendy Williams", "Site Supervisor", "Operations", "Delta Factory", 53000, 2700, "2024-07-01"),
        ("Xavier Xavier", "Field Engineer", "Operations", "Mega Site Alpha", 47000, 2100, "2024-08-15"),
        ("Yvonne Young", "HR Assistant", "HR", "Giga HQ", 43000, 1700, "2025-01-20"),
    ]

    employees_org1 = []
    for idx, (name, role_name, dept, loc, salary, allowance, join_date) in enumerate(emp_org1_data):
        creator = org1_creators[idx % len(org1_creators)]
        emp = Employee.objects.create(
            admin_id='ADMORG1',
            name=name,
            employee_id=f'EMP-{100+idx:03d}',
            mobile_app_password='password123',
            designation=role_name,
            department=dept,
            location=loc,
            site=loc,
            base_salary=Decimal(salary),
            fixed_allowance=Decimal(allowance),
            joining_date=datetime.datetime.strptime(join_date, "%Y-%m-%d").date(),
            status='active',
            job_role=job_roles_org1[role_name],
            created_by=creator,
        )
        employees_org1.append(emp)

        # Bank details
        BankDetail.objects.create(
            employee=emp,
            bank_name='Test Business Bank',
            account_holder=name,
            account_number=f'999888000{idx:02d}',
            ifsc_code='TBBK0001234',
            branch='Central Branch',
            status='verified',
            modified_by=creator,
        )

        # PF details
        PFDetail.objects.create(
            employee=emp,
            pf_number=f'MH/BAN/0000{idx:02d}/000/0000123',
            uan_number=f'1009998887{idx:02d}',
            esic_number=f'31000099998887{idx:02d}',
            status='added',
            employee_contribution=Decimal(1800.00),
            employer_contribution=Decimal(1800.00),
            joining_date=emp.joining_date,
            modified_by=creator,
        )

    emp_org2_data = [
        ("Org2 Employee 1", "Org2 JobRole A", "General", "Org2 Branch A", 50000, 2000, "2025-01-01", jr_org2_a),
        ("Org2 Employee 2", "Org2 JobRole A", "General", "Org2 Branch A", 45000, 1500, "2025-02-01", jr_org2_a),
        ("Org2 Employee 3", "Org2 JobRole B", "Operations", "Org2 Branch A", 36000, 1000, "2025-03-01", jr_org2_b),
    ]
    employees_org2 = []
    for idx, (name, role_name, dept, loc, salary, allowance, join_date, job_role) in enumerate(emp_org2_data):
        creator = org2_creators[idx % len(org2_creators)]
        emp = Employee.objects.create(
            admin_id='ADMORG2',
            name=name,
            employee_id=f'EMP-O2-{idx+1:02d}',
            mobile_app_password='password123',
            designation=role_name,
            department=dept,
            location=loc,
            site=loc,
            base_salary=Decimal(salary),
            fixed_allowance=Decimal(allowance),
            joining_date=datetime.datetime.strptime(join_date, "%Y-%m-%d").date(),
            status='active',
            job_role=job_role,
            created_by=creator,
        )
        employees_org2.append(emp)

        # Bank details
        BankDetail.objects.create(
            employee=emp,
            bank_name='Org2 Bank',
            account_holder=name,
            account_number=f'8888000{idx:02d}',
            ifsc_code='ORGBK000123',
            branch='Main Branch',
            status='verified',
            modified_by=creator,
        )

        # PF details
        PFDetail.objects.create(
            employee=emp,
            pf_number=f'PF-O2-{idx:02d}',
            status='added',
            joining_date=emp.joining_date,
            modified_by=creator,
        )

    print("Seeding attendance records (April 1 to May 21)...")
    start_date = datetime.date(2026, 4, 1)
    end_date = datetime.date(2026, 5, 21)
    delta = end_date - start_date
    num_days = delta.days + 1

    # Seed random generator for realistic variation
    random.seed(12345)

    total_att_records = 0
    # Org 1 Attendance
    for emp in employees_org1:
        creator_pool = org1_creators
        for i in range(num_days):
            curr_date = start_date + datetime.timedelta(days=i)
            # Sunday check
            if curr_date.weekday() == 6: # Sunday
                status = 'leave'
            else:
                # Weekdays: Present (86%), Half Day (6%), Leave (5%), No Week Off (3%)
                r = random.random()
                if r < 0.86:
                    status = 'present'
                elif r < 0.92:
                    status = 'half_day'
                elif r < 0.97:
                    status = 'leave'
                else:
                    status = 'no_week_off'
            
            creator = creator_pool[total_att_records % len(creator_pool)]
            AttendanceRecord.objects.create(
                employee=emp,
                date=curr_date,
                admin_id='ADMORG1',
                status=status,
                source='admin',
                created_by=creator,
            )
            total_att_records += 1

    # Org 2 Attendance
    for emp in employees_org2:
        creator_pool = org2_creators
        for i in range(num_days):
            curr_date = start_date + datetime.timedelta(days=i)
            # Sunday check
            if curr_date.weekday() == 6: # Sunday
                status = 'leave'
            else:
                # Weekdays: Present (90%), Half Day (4%), Leave (4%), No Week Off (2%)
                r = random.random()
                if r < 0.90:
                    status = 'present'
                elif r < 0.94:
                    status = 'half_day'
                elif r < 0.98:
                    status = 'leave'
                else:
                    status = 'no_week_off'
            
            creator = creator_pool[total_att_records % len(creator_pool)]
            AttendanceRecord.objects.create(
                employee=emp,
                date=curr_date,
                admin_id='ADMORG2',
                status=status,
                source='admin',
                created_by=creator,
            )
            total_att_records += 1

    print("Seeding financial and income categories...")
    # Org 1 Finance categories (finance.models.Category)
    finance_inc_cats = ["Client Project Billings", "Retainer Fees", "Product Sales", "Interest Income"]
    finance_exp_cats = ["Office Rent", "Employee Salaries", "Utilities", "Office Supplies", "Travel Expenses", "Subcontractors", "Operational Expenses", "Branch Expenses"]
    
    f_cats = {}
    for name in finance_inc_cats:
        cat = FinanceCategory.objects.create(
            admin_id='ADMORG1',
            name=name,
            type='income',
            color='#10b981',
            created_by=super_admin_org1,
        )
        f_cats[('income', name)] = cat

    for name in finance_exp_cats:
        cat = FinanceCategory.objects.create(
            admin_id='ADMORG1',
            name=name,
            type='expense',
            color='#ef4444',
            created_by=super_admin_org1,
        )
        f_cats[('expense', name)] = cat

    # Org 1 categories app Categories (categories.models)
    income_cats_org1 = ["Project Billings", "Product Support", "Advisory Services"]
    expense_cats_org1 = ["Office Maintenance", "Employee Payroll", "Broadband & Phone", "Software Licenses", "Business Travel"]
    
    inc_cats_map = {}
    for name in income_cats_org1:
        cat = IncomeCategory.objects.create(
            name=name,
            created_by=super_admin_org1,
            color='#10b981'
        )
        inc_cats_map[name] = cat
        
    exp_cats_map = {}
    for name in expense_cats_org1:
        cat = ExpenseCategory.objects.create(
            name=name,
            created_by=super_admin_org1,
            color='#ef4444'
        )
        exp_cats_map[name] = cat

    # Org 2 Categories
    cat_inc_o2 = FinanceCategory.objects.create(
        admin_id='ADMORG2', name="Org2 Income Cat", type='income', color='#10b981', created_by=super_admin_org2
    )
    cat_exp_o2 = FinanceCategory.objects.create(
        admin_id='ADMORG2', name="Org2 Expense Cat", type='expense', color='#ef4444', created_by=super_admin_org2
    )

    print("Seeding income tracker data...")
    # Org 1 Incomes
    income_items_org1 = [
        ("Acme Corp Project Milestone 1", 250000.00, "Project Billings", "Client Project Billings", "2026-04-05", "Giga HQ", "bank_transfer", "Acme Corp"),
        ("Globex Retainer Fee April", 75000.00, "Project Billings", "Retainer Fees", "2026-04-15", "Mega Site Alpha", "bank_transfer", "Globex"),
        ("Initech Consulting Fee", 120000.00, "Advisory Services", "Client Project Billings", "2026-04-25", "Delta Factory", "bank_transfer", "Initech"),
        ("Acme Corp Project Milestone 2", 300000.00, "Project Billings", "Client Project Billings", "2026-05-05", "Giga HQ", "bank_transfer", "Acme Corp"),
        ("Hooli Retainer Fee May", 185000.00, "Project Billings", "Retainer Fees", "2026-05-15", "Mega Site Alpha", "bank_transfer", "Hooli Inc"),
    ]

    for idx, (title, amt, inc_cat_name, fin_cat_name, date_str, site, mode, pay_by) in enumerate(income_items_org1):
        creator = org1_creators[idx % len(org1_creators)]
        t_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        branch = branches_org1[idx % len(branches_org1)]
        
        # 1. Create in Income model (for dashboard & reports)
        Income.objects.create(
            user=creator,
            admin_id='ADMORG1',
            title=title,
            amount=Decimal(amt),
            category=inc_cats_map[inc_cat_name],
            date=t_date,
            source='Direct Client Deposit',
            description=f'Income record for {title}',
            payment_mode=mode,
            location_site=site,
            payment_by=pay_by
        )

        # 2. Create in FinanceTransaction model (for Transactions list)
        FinanceTransaction.objects.create(
            user=creator,
            type='income',
            category=f_cats[('income', fin_cat_name)],
            amount=Decimal(amt),
            description=title,
            date=t_date,
            payment_mode='bank',
            branch=branch,
            admin_id='ADMORG1',
            created_by=creator,
        )

    # Org 2 Incomes
    # Create an Income Category for Org 2
    inc_cat_org2 = IncomeCategory.objects.create(
        name="Org2 Income Category",
        created_by=super_admin_org2,
        color='#10b981'
    )
    income_items_org2 = [
        ("Org2 Milestone A", 60000.00, "2026-04-10"),
        ("Org2 Milestone B", 80000.00, "2026-05-10"),
    ]
    for idx, (title, amt, date_str) in enumerate(income_items_org2):
        creator = org2_creators[idx % len(org2_creators)]
        t_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        Income.objects.create(
            user=creator,
            admin_id='ADMORG2',
            title=title,
            amount=Decimal(amt),
            category=inc_cat_org2,
            date=t_date,
            source='Client Payment',
            description=title,
            payment_mode='cash',
            location_site='Org2 Branch A',
            payment_by='Client Org2'
        )
        FinanceTransaction.objects.create(
            user=creator,
            type='income',
            category=cat_inc_o2,
            amount=Decimal(amt),
            description=title,
            date=t_date,
            payment_mode='cash',
            branch=branch_org2,
            admin_id='ADMORG2',
            created_by=creator,
        )

    print("Seeding operational expenses...")
    # Org 1 Expenses
    expense_items_org1 = [
        ("Giga HQ May Rent", 50000.00, "Office Rent", "2026-05-01", "Giga HQ", "bank"),
        ("Delta Factory Power Bill", 15000.00, "Utilities", "2026-05-02", "Delta Factory", "bank"),
        ("Mega Site Alpha Stationery", 5000.00, "Office Supplies", "2026-05-03", "Mega Site Alpha", "cash"),
        ("HR Recruitment Tour", 12000.00, "Travel Expenses", "2026-05-04", "Giga HQ", "upi"),
        ("Safety Audit Fees", 35000.00, "Subcontractors", "2026-05-05", "Mega Site Alpha", "bank"),
        ("General Office Maintenance", 8000.00, "Operational Expenses", "2026-05-06", "Giga HQ", "cash"),
        ("Safety gear purchase", 22000.00, "Branch Expenses", "2026-05-07", "Delta Factory", "bank"),
    ]
    for idx, (desc, amt, cat_name, date_str, site, mode) in enumerate(expense_items_org1):
        creator = org1_creators[idx % len(org1_creators)]
        t_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        branch = next(b for b in branches_org1 if b.name == site)
        FinanceTransaction.objects.create(
            user=creator,
            type='expense',
            category=f_cats[('expense', cat_name)],
            amount=Decimal(amt),
            description=desc,
            date=t_date,
            payment_mode=mode,
            branch=branch,
            admin_id='ADMORG1',
            created_by=creator,
        )

    # Org 2 Expenses
    expense_items_org2 = [
        ("Org2 Rent", 10000.00, "2026-05-01"),
        ("Org2 Power Bill", 3000.00, "2026-05-02"),
    ]
    for idx, (desc, amt, date_str) in enumerate(expense_items_org2):
        creator = org2_creators[idx % len(org2_creators)]
        t_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        FinanceTransaction.objects.create(
            user=creator,
            type='expense',
            category=cat_exp_o2,
            amount=Decimal(amt),
            description=desc,
            date=t_date,
            payment_mode='cash',
            branch=branch_org2,
            admin_id='ADMORG2',
            created_by=creator,
        )

    print("Processing and paying out April 2026 salary/payroll programmatically...")
    april_payroll_date = datetime.date(2026, 4, 1)
    
    # 1. Org 1 Payroll Payouts
    org1_payroll_total = Decimal('0.00')
    for idx, emp in enumerate(employees_org1):
        creator = org1_creators[idx % len(org1_creators)]
        
        # Calculate prorated base salary from attendance record
        payable_base = _compute_attendance_earnings(emp, april_payroll_date, emp.base_salary)
        
        # Add some OT, advance, deductions to test proration and deductions edge cases
        ot = Decimal('0.00')
        ded = Decimal('0.00')
        adv = Decimal('0.00')
        
        if idx % 3 == 0:
            ot = Decimal('2000.00')
            ded = Decimal('500.00')
            adv = Decimal('1000.00')
            
        net_pay = payable_base + ot - adv - ded
        org1_payroll_total += net_pay
        
        # Create SalaryUpdate record
        SalaryUpdate.objects.create(
            admin_id='ADMORG1',
            employee=emp,
            month=april_payroll_date,
            basic_salary=emp.base_salary,
            extra_allowance=emp.fixed_allowance,
            ot_allowance=ot,
            advance_pay=adv,
            total_deduction=ded,
            net_pay=net_pay,
            pf_employee_snapshot=Decimal('1800.00'),
            pf_employer_snapshot=Decimal('1800.00'),
            created_by=creator
        )

        # Create corresponding expense transaction to pay out
        branch = next(b for b in branches_org1 if b.name == emp.site)
        FinanceTransaction.objects.create(
            user=creator,
            type='expense',
            category=f_cats[('expense', 'Employee Salaries')],
            amount=net_pay,
            description=f"Salary Payout - {emp.name} (April 2026)",
            date=datetime.date(2026, 4, 30),
            payment_mode='bank',
            branch=branch,
            admin_id='ADMORG1',
            created_by=creator,
        )

    # 2. Org 2 Payroll Payouts
    org2_payroll_total = Decimal('0.00')
    for idx, emp in enumerate(employees_org2):
        creator = org2_creators[idx % len(org2_creators)]
        payable_base = _compute_attendance_earnings(emp, april_payroll_date, emp.base_salary)
        net_pay = payable_base
        org2_payroll_total += net_pay
        
        # Create SalaryUpdate
        SalaryUpdate.objects.create(
            admin_id='ADMORG2',
            employee=emp,
            month=april_payroll_date,
            basic_salary=emp.base_salary,
            extra_allowance=emp.fixed_allowance,
            net_pay=net_pay,
            created_by=creator
        )
        
        # Create expense transaction
        FinanceTransaction.objects.create(
            user=creator,
            type='expense',
            category=cat_exp_o2,
            amount=net_pay,
            description=f"Salary Payout - {emp.name} (April 2026)",
            date=datetime.date(2026, 4, 30),
            payment_mode='cash',
            branch=branch_org2,
            admin_id='ADMORG2',
            created_by=creator,
        )

    print("Data seeding and payroll processing completed successfully!")
    print("\n--- SEED VERIFICATION METRICS ---")
    print(f"Total Employees: Org 1 = {len(employees_org1)}, Org 2 = {len(employees_org2)}")
    print(f"Total Attendance Records Created: {total_att_records}")
    print(f"Org 1 Salary Payout Total (April 2026): Rs.{org1_payroll_total:.2f}")
    print(f"Org 2 Salary Payout Total (April 2026): Rs.{org2_payroll_total:.2f}")

    # Compute total income/expense in DB for both orgs
    o1_inc = Income.objects.filter(admin_id='ADMORG1').aggregate(s=Sum('amount'))['s'] or 0
    o1_exp = FinanceTransaction.objects.filter(admin_id='ADMORG1', type='expense').aggregate(s=Sum('amount'))['s'] or 0
    print(f"Org 1 Total Income (DB): Rs.{o1_inc:.2f}")
    print(f"Org 1 Total Expense (DB): Rs.{o1_exp:.2f}")
    print(f"Org 1 Balance: Rs.{(o1_inc - o1_exp):.2f}")

    o2_inc = Income.objects.filter(admin_id='ADMORG2').aggregate(s=Sum('amount'))['s'] or 0
    o2_exp = FinanceTransaction.objects.filter(admin_id='ADMORG2', type='expense').aggregate(s=Sum('amount'))['s'] or 0
    print(f"Org 2 Total Income (DB): Rs.{o2_inc:.2f}")
    print(f"Org 2 Total Expense (DB): Rs.{o2_exp:.2f}")
    print(f"Org 2 Balance: Rs.{(o2_inc - o2_exp):.2f}")

if __name__ == '__main__':
    seed()
