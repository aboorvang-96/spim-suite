import os
import django
import datetime
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from branches.models import Branch
from employees.models import Employee, SalaryUpdate
from attendance.models import AttendanceRecord
from finance.models import Transaction
from income.models import Income

# Views to test
from dashboard.views import index as dashboard_index
from branches.views import branch_list
from employees.views import employee_list, edit_employee, salary_dashboard
from finance.views import transaction_list
from income.views import income_list
from reports.views import reports_index

User = get_user_model()

def run_test():
    print("--- RUNTIME QA & MULTI-ADMIN SHARED-DATA VALIDATION ---")
    
    # 1. Fetch our test users
    try:
        sa_org1 = User.objects.get(email='super_admin_org1@test.com')
        a1_org1 = User.objects.get(email='admin1_org1@test.com')
        sa_org2 = User.objects.get(email='super_admin_org2@test.com')
        a1_org2 = User.objects.get(email='admin1_org2@test.com')
    except User.DoesNotExist as e:
        print(f"Error: Seeded users not found. Run seed_data.py first. Details: {e}")
        return

    factory = RequestFactory()

    # Define a helper to print test headers
    def test_header(title):
        print(f"\n========================================\n{title}\n========================================")

    # ==========================================
    # TEST 1: Tenant Isolation & Data Leakage (Branches)
    # ==========================================
    test_header("TEST 1: Branches List Isolation")
    
    # Query database directly first
    print(f"Direct DB: Total branches count = {Branch.objects.count()}")
    print(f"Direct DB: Branches for Org 1 = {Branch.objects.filter(admin_id='ADMORG1').count()}")
    print(f"Direct DB: Branches for Org 2 = {Branch.objects.filter(admin_id='ADMORG2').count()}")

    # Simulate Request for Super Admin Org 1
    req = factory.get('/branches/')
    req.user = sa_org1
    # branch_list view returns render() which we can inspect by extracting context/variables
    # Let's mock render to capture the context
    from django.shortcuts import render as original_render
    captured_contexts = {}
    
    def mock_render(request, template_name, context=None, content_type=None, status=None, using=None):
        captured_contexts[template_name] = context
        return original_render(request, template_name, context, content_type, status, using)

    import branches.views
    branches.views.render = mock_render
    
    # Run views and inspect context
    try:
        branches.views.branch_list(req)
        branches_json = captured_contexts.get('branches/list.html', {}).get('branches_json', '[]')
        import json
        branches_data = json.loads(branches_json)
        print(f"sa_org1 branch_list view: returned {len(branches_data)} branches. Names: {[b['name'] for b in branches_data]}")
    except Exception as e:
        print(f"sa_org1 branch_list error: {e}")

    # Simulate Request for Super Admin Org 2
    req2 = factory.get('/branches/')
    req2.user = sa_org2
    captured_contexts.clear()
    try:
        branches.views.branch_list(req2)
        branches_json = captured_contexts.get('branches/list.html', {}).get('branches_json', '[]')
        branches_data = json.loads(branches_json)
        print(f"sa_org2 branch_list view: returned {len(branches_data)} branches. Names: {[b['name'] for b in branches_data]}")
    except Exception as e:
        print(f"sa_org2 branch_list error: {e}")
        
    # Restore render
    branches.views.render = original_render

    # ==========================================
    # TEST 2: Employee List Isolation & Shared Visibility
    # ==========================================
    test_header("TEST 2: Employees Isolation & Scoping")
    
    # Query database directly
    print(f"Direct DB: Total employees count = {Employee.objects.count()}")
    print(f"Direct DB: Employees for Org 1 = {Employee.objects.filter(admin_id='ADMORG1').count()}")
    print(f"Direct DB: Employees for Org 2 = {Employee.objects.filter(admin_id='ADMORG2').count()}")

    import employees.views
    employees.views.render = mock_render
    
    # Run sa_org1 employee_list
    req = factory.get('/employees/')
    req.user = sa_org1
    captured_contexts.clear()
    try:
        employees.views.employee_list(req)
        employees_qs = captured_contexts.get('employees/list.html', {}).get('employees', [])
        print(f"sa_org1 employee_list view: returned {employees_qs.count()} employees.")
    except Exception as e:
        print(f"sa_org1 employee_list error: {e}")

    # Run a1_org1 (Linked Admin) employee_list
    req = factory.get('/employees/')
    req.user = a1_org1
    captured_contexts.clear()
    try:
        employees.views.employee_list(req)
        employees_qs = captured_contexts.get('employees/list.html', {}).get('employees', [])
        print(f"a1_org1 (Linked Admin) employee_list view: returned {employees_qs.count()} employees.")
    except Exception as e:
        print(f"a1_org1 employee_list error: {e}")

    # Run sa_org2 employee_list
    req = factory.get('/employees/')
    req.user = sa_org2
    captured_contexts.clear()
    try:
        employees.views.employee_list(req)
        employees_qs = captured_contexts.get('employees/list.html', {}).get('employees', [])
        print(f"sa_org2 employee_list view: returned {employees_qs.count()} employees.")
    except Exception as e:
        print(f"sa_org2 employee_list error: {e}")

    # Test Employee Mutation Isolation (collaboration block)
    # Find an employee created by sa_org1
    emp_sa = Employee.objects.filter(admin_id='ADMORG1', created_by=sa_org1).first()
    if emp_sa:
        print(f"Found employee '{emp_sa.name}' created by sa_org1 (ID: {emp_sa.id})")
        # Try editing or viewing this employee as a1_org1
        # View edit form
        req = factory.get(f'/employees/{emp_sa.id}/edit/')
        req.user = a1_org1
        try:
            employees.views.edit_employee(req, pk=emp_sa.id)
            print(f"a1_org1 view edit form: SUCCESS")
        except Exception as e:
            print(f"a1_org1 view edit form: FAILED (Expected due to created_by=request.user check). Details: {e}")

        # Try deleting this employee as a1_org1
        req = factory.post(f'/employees/{emp_sa.id}/delete/')
        req.user = a1_org1
        try:
            employees.views.delete_employee(req, pk=emp_sa.id)
            print(f"a1_org1 delete employee: SUCCESS")
        except Exception as e:
            print(f"a1_org1 delete employee: FAILED (Expected due to created_by=request.user check). Details: {e}")
    else:
        print("No employee created by sa_org1 found.")

    employees.views.render = original_render

    # ==========================================
    # TEST 3: Finance (Transactions) Isolation & Scoping
    # ==========================================
    test_header("TEST 3: Transaction Scoping & Leakage")

    print(f"Direct DB: Total transactions count = {Transaction.objects.count()}")
    print(f"Direct DB: Transactions for Org 1 = {Transaction.objects.filter(admin_id='ADMORG1').count()}")
    print(f"Direct DB: Transactions for Org 2 = {Transaction.objects.filter(admin_id='ADMORG2').count()}")

    import finance.views
    finance.views.render = mock_render

    # Run sa_org1 transaction_list
    req = factory.get('/expenses/')
    req.user = sa_org1
    captured_contexts.clear()
    try:
        finance.views.transaction_list(req)
        txns_list = captured_contexts.get('finance/list.html', {}).get('transactions', [])
        txns_json = captured_contexts.get('finance/list.html', {}).get('transactions_json', '[]')
        txns_data = json.loads(txns_json)
        print(f"sa_org1 transaction_list view: returned {len(txns_list)} transactions (json: {len(txns_data)}).")
    except Exception as e:
        print(f"sa_org1 transaction_list error: {e}")

    # Run a1_org1 (Linked Admin) transaction_list
    req = factory.get('/expenses/')
    req.user = a1_org1
    captured_contexts.clear()
    try:
        finance.views.transaction_list(req)
        txns_list = captured_contexts.get('finance/list.html', {}).get('transactions', [])
        txns_json = captured_contexts.get('finance/list.html', {}).get('transactions_json', '[]')
        txns_data = json.loads(txns_json)
        print(f"a1_org1 transaction_list view: returned {len(txns_list)} transactions (json: {len(txns_data)}).")
    except Exception as e:
        print(f"a1_org1 transaction_list error: {e}")

    # Run sa_org2 transaction_list
    req = factory.get('/expenses/')
    req.user = sa_org2
    captured_contexts.clear()
    try:
        finance.views.transaction_list(req)
        txns_list = captured_contexts.get('finance/list.html', {}).get('transactions', [])
        print(f"sa_org2 transaction_list view: returned {len(txns_list)} transactions.")
    except Exception as e:
        print(f"sa_org2 transaction_list error: {e}")

    finance.views.render = original_render

    # ==========================================
    # TEST 4: Income Isolation & Scoping
    # ==========================================
    test_header("TEST 4: Income Isolation & Leakage")

    print(f"Direct DB: Total income count = {Income.objects.count()}")
    print(f"Direct DB: Income for Org 1 = {Income.objects.filter(admin_id='ADMORG1').count()}")
    print(f"Direct DB: Income for Org 2 = {Income.objects.filter(admin_id='ADMORG2').count()}")

    import income.views
    income.views.render = mock_render

    # Run sa_org1 income_list
    req = factory.get('/income/')
    req.user = sa_org1
    captured_contexts.clear()
    try:
        income.views.income_list(req)
        inc_list = captured_contexts.get('income/list.html', {}).get('incomes', [])
        print(f"sa_org1 income_list view: returned {len(inc_list)} income records.")
    except Exception as e:
        print(f"sa_org1 income_list error: {e}")

    # Run a1_org1 income_list
    req = factory.get('/income/')
    req.user = a1_org1
    captured_contexts.clear()
    try:
        income.views.income_list(req)
        inc_list = captured_contexts.get('income/list.html', {}).get('incomes', [])
        print(f"a1_org1 income_list view: returned {len(inc_list)} income records.")
    except Exception as e:
        print(f"a1_org1 income_list error: {e}")

    # Run sa_org2 income_list
    req = factory.get('/income/')
    req.user = sa_org2
    captured_contexts.clear()
    try:
        income.views.income_list(req)
        inc_list = captured_contexts.get('income/list.html', {}).get('incomes', [])
        print(f"sa_org2 income_list view: returned {len(inc_list)} income records.")
    except Exception as e:
        print(f"sa_org2 income_list error: {e}")

    income.views.render = original_render

    # ==========================================
    # TEST 5: Dashboard and Reports Reflections & Isolation
    # ==========================================
    test_header("TEST 5: Dashboard and Reports Reflections & Isolation")

    import dashboard.views
    dashboard.views.render = mock_render
    
    # sa_org1 dashboard
    req = factory.get('/dashboard/')
    req.user = sa_org1
    captured_contexts.clear()
    try:
        dashboard.views.index(req)
        total_income = captured_contexts.get('dashboard/index.html', {}).get('total_income', 0)
        total_expense = captured_contexts.get('dashboard/index.html', {}).get('total_expense', 0)
        balance = captured_contexts.get('dashboard/index.html', {}).get('balance', 0)
        print(f"sa_org1 Dashboard: Total Income = Rs.{total_income}, Total Expense = Rs.{total_expense}, Balance = Rs.{balance}")
    except Exception as e:
        print(f"sa_org1 dashboard index error: {e}")

    # sa_org2 dashboard
    req = factory.get('/dashboard/')
    req.user = sa_org2
    captured_contexts.clear()
    try:
        dashboard.views.index(req)
        total_income = captured_contexts.get('dashboard/index.html', {}).get('total_income', 0)
        total_expense = captured_contexts.get('dashboard/index.html', {}).get('total_expense', 0)
        balance = captured_contexts.get('dashboard/index.html', {}).get('balance', 0)
        print(f"sa_org2 Dashboard: Total Income = Rs.{total_income}, Total Expense = Rs.{total_expense}, Balance = Rs.{balance}")
    except Exception as e:
        print(f"sa_org2 dashboard index error: {e}")

    dashboard.views.render = original_render

    import reports.views
    reports.views.render = mock_render

    # sa_org1 reports
    req = factory.get('/reports/')
    req.user = sa_org1
    captured_contexts.clear()
    try:
        reports.views.reports_index(req)
        periods = captured_contexts.get('reports/index.html', {}).get('periods', [])
        # print monthly period info
        monthly = next((p for p in periods if p['key'] == 'monthly'), None)
        if monthly:
            print(f"sa_org1 Reports (Monthly): Income = Rs.{monthly['income']}, Expense = Rs.{monthly['expense']}, Net = Rs.{monthly['net']}")
        else:
            print("sa_org1 Reports: No monthly card found.")
    except Exception as e:
        print(f"sa_org1 reports index error: {e}")

    # sa_org2 reports
    req = factory.get('/reports/')
    req.user = sa_org2
    captured_contexts.clear()
    try:
        reports.views.reports_index(req)
        periods = captured_contexts.get('reports/index.html', {}).get('periods', [])
        monthly = next((p for p in periods if p['key'] == 'monthly'), None)
        if monthly:
            print(f"sa_org2 Reports (Monthly): Income = Rs.{monthly['income']}, Expense = Rs.{monthly['expense']}, Net = Rs.{monthly['net']}")
        else:
            print("sa_org2 Reports: No monthly card found.")
    except Exception as e:
        print(f"sa_org2 reports index error: {e}")

    reports.views.render = original_render

    # ==========================================
    # TEST 6: Salary Calculations & Attendance-Based Deductions
    # ==========================================
    test_header("TEST 6: Salary Calculation Validation")
    
    # We will test the salary proration calculation function
    from employees.views import _compute_attendance_earnings
    
    # Let's take John Doe (Software Engineer, monthly salary 80,000)
    john = Employee.objects.filter(name="John Doe", admin_id="ADMORG1").first()
    if john:
        month_date = datetime.date(2026, 5, 1)
        # Check total attendance records for John Doe in May 2026
        may_records = AttendanceRecord.objects.filter(employee=john, date__year=2026, date__month=5)
        print(f"John Doe total attendance records marked in May 2026 = {may_records.count()}")
        
        presents = may_records.filter(status='present').count()
        half_days = may_records.filter(status='half_day').count()
        leaves = may_records.filter(status='leave').count()
        absents = may_records.filter(status='absent').count()
        print(f"John Doe attendance breakdown: present={presents}, half_day={half_days}, leave={leaves}, absent={absents}")
        
        effective_days = presents + (half_days * 0.5)
        total_days = 31 # May has 31 days
        expected_earnings = round((effective_days / total_days) * float(john.base_salary), 2)
        
        print(f"Divisor total_days = {total_days}")
        print(f"Calculated effective_days = {effective_days}")
        print(f"Base Salary = Rs.{john.base_salary}")
        
        try:
            actual_earnings = _compute_attendance_earnings(john, month_date, john.base_salary)
            print(f"Expected Earnings (formula: effective/total_days * base) = Rs.{expected_earnings}")
            print(f"Actual View Earnings = Rs.{actual_earnings}")
            print(f"Difference (Salary Deduction) = Rs.{float(john.base_salary) - float(actual_earnings)}")
        except TypeError as te:
            print(f"Actual View Earnings calculation FAILED directly with TypeError: {te}")
            # Try float conversion to verify if it works when cast to float
            actual_earnings = _compute_attendance_earnings(john, month_date, float(john.base_salary))
            print(f"When converted to float, actual_earnings = Rs.{actual_earnings}")
            print(f"Difference (Salary Deduction) = Rs.{float(john.base_salary) - float(actual_earnings)}")
        
        # Check if weekly offs are marked as 'leave'
        sunday_leaves = may_records.filter(status='leave', created_at__isnull=True).count() # seeded leaves have created_at? wait, let's just query leaves
        print(f"Total leaves (includes Sundays) = {leaves}")
        
        # If employee has 0 absences or half days other than Sunday weekly off
        # Let's see if Sundays are deducted. Since Sundays are marked as 'leave' and not 'present',
        # they are excluded from effective_days. Thus, employee suffers deduction for Sundays!
    else:
        print("Employee John Doe not found.")

    # ==========================================
    # TEST 7: Attendance Blank ID Multi-Object Return Bug
    # ==========================================
    test_header("TEST 7: Attendance save_attendance blank ID bug")
    
    # Check if there are employees with blank employee_id
    # Let's create two temporary employees with blank employee_id in Org 1
    import uuid
    uid = uuid.uuid4().hex[:6]
    temp_emp1 = Employee.objects.create(
        name=f"Temp Emp 1 {uid}",
        employee_id='',
        base_salary=Decimal(30000),
        admin_id='ADMORG1',
        created_by=sa_org1
    )
    temp_emp2 = Employee.objects.create(
        name=f"Temp Emp 2 {uid}",
        employee_id='',
        base_salary=Decimal(35000),
        admin_id='ADMORG1',
        created_by=sa_org1
    )
    
    print(f"Created two temporary employees with blank employee_id: '{temp_emp1.name}', '{temp_emp2.name}'")
    print(f"Direct DB: Employees with blank employee_id in Org 1 = {Employee.objects.filter(employee_id='', admin_id='ADMORG1').count()}")

    from attendance.views import save_attendance
    
    # Simulate POST data containing a blank empId or None/empty string
    # In save_attendance, when it iterates and gets a record:
    # record = {'empId': '', 'date': '2026-05-20', 'status': 'Present'}
    import json
    post_payload = json.dumps([
        {'empId': '', 'date': '2026-05-20', 'status': 'Present'}
    ])
    
    req = factory.post('/attendance/save/', data=post_payload, content_type='application/json')
    req.user = sa_org1
    
    try:
        resp = save_attendance(req)
        resp_data = json.loads(resp.content.decode('utf-8'))
        print(f"save_attendance call response: {resp_data}")
        # If it failed, it will return success: False and the error message
    except Exception as e:
        print(f"save_attendance call crashed directly: {e}")

    # Clean up temporary employees
    temp_emp1.delete()
    temp_emp2.delete()
    print("Cleaned up temporary employees.")

if __name__ == '__main__':
    run_test()
