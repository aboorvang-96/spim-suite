# Salary Manager - Developer Documentation

**For developers, architects, and backend integration specialists** 👨‍💻

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Data Model](#data-model)
3. [JavaScript API](#javascript-api)
4. [localStorage Schema](#localstorage-schema)
5. [Django Integration Guide](#django-integration-guide)
6. [Backend Endpoints](#backend-endpoints)
7. [Database Models](#database-models)
8. [Code Structure](#code-structure)
9. [Extending the Module](#extending-the-module)

---

## Architecture Overview

### Technology Stack

```
Frontend:
├─ HTML5 (semantic markup)
├─ CSS3 (CSS variables, Grid, Flexbox, Dark mode)
├─ Vanilla JavaScript (ES6+)
└─ External Libraries:
   ├─ jsPDF (PDF generation)
   ├─ XLSX (Excel export/import)
   └─ CDN-hosted (no build step required)

Storage:
├─ Browser localStorage (primary)
├─ Session storage (optional for temp data)
└─ Backend database (future integration)

Architecture Pattern:
├─ Modular UI (separate modals for add/edit/bank/pf)
├─ Event-driven (onclick handlers)
├─ Declarative rendering (map data to DOM)
└─ Persistent state (localStorage backup)
```

### Data Flow

```
┌─────────────────────────────────────────────────────────┐
│                    salary-manager.html                   │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐           ┌──────────────┐           │
│  │    Page 1    │ ──────→   │   Page 2     │           │
│  │  Employees   │ ←─────    │   Salary     │           │
│  └──────────────┘           └──────────────┘           │
│        ↕                            ↕                    │
│  ┌──────────────────────────────────────────────┐      │
│  │         Shared: employees[] Array            │      │
│  └──────────────────────────────────────────────┘      │
│        ↕                                                 │
│  ┌─────────────────────────────────────────────────┐   │
│  │        Browser localStorage                     │   │
│  │  Key: 'salaryMgr_v4'                           │   │
│  │  Value: {employees: [...], nextId: N}          │   │
│  └─────────────────────────────────────────────────┘   │
│        ↕                                                 │
│  ┌─────────────────────────────────────────────────┐   │
│  │   Backend API (future integration)              │   │
│  │   POST /api/employees/                          │   │
│  │   POST /api/salary/update/                      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Data Model

### Employee Object Structure

```javascript
{
  // Identification
  id:         number,    // Auto-incremented from nextId
  name:       string,    // Required: Full name (unique)
  role:       string,    // Required: Job title
  
  // Assignment
  location:   string,    // Required: Main area/team
  site:       string,    // Required: Exact work site
  
  // Salary Information
  salary:     number,    // Optional: Base monthly salary (default: 0)
  ot:         number,    // Optional: OT/Extra Allowance (default: 0) [NEW]
  advance:    number,    // Optional: Advance pay deduction (default: 0)
  deduction:  number,    // Optional: Total other deductions (default: 0)
  
  // Bank Details (for payment)
  bank:       string,    // Optional: Bank name
  holder:     string,    // Optional: Account holder name
  account:    string,    // Optional: Account number
  ifsc:       string,    // Optional: IFSC code
  
  // PF/ESIC Details (payslip only, not in salary calc)
  pf_no:      string,    // Optional: PF number [NEW]
  esic_no:    string,    // Optional: ESIC number [NEW]
  pf_amount:  number     // Optional: PF contribution (default: 0) [NEW]
}
```

### Sample Employee

```javascript
{
  id: 1,
  name: "Arun Kumar",
  role: "Site Engineer",
  location: "Tirunelveli",
  site: "Site 1 – Valliyur",
  salary: 45000,
  ot: 2000,
  advance: 3000,
  deduction: 1500,
  bank: "State Bank of India",
  holder: "Arun Kumar",
  account: "3256789012",
  ifsc: "SBIN0001234",
  pf_no: "DL/001234001",
  esic_no: "10001001001",
  pf_amount: 3600
}
```

---

## JavaScript API

### Core Functions

#### **Employee Management**

```javascript
// Create employee (from modal)
saveEmployee(stepFrom)
// stepFrom: 2 (save with Step 1 only)
//           3 (save with Steps 1-2)
//           4 (save with all 3 steps)

// Get employee by ID
emp(id)
// Returns: employee object or undefined

// Check if employee has bank details
hasBank(e)
// Returns: boolean (true if bank OR account filled)

// Check if employee has PF details
hasPF(e)
// Returns: boolean (true if pf_no OR esic_no OR pf_amount filled)

// Check for duplicate employee name
isDuplicate(name, excludeId=null)
// Returns: boolean

// Remove employee
confirmRemove()
// Removes: employees.find(x => x.id === removingId)
```

#### **Modal Management**

```javascript
// Employee Add Modal (3-step)
openAddModal()           // Opens add modal
closeAddModal()          // Closes add modal
renderAddStep(step)      // Renders step 1, 2, or 3
goStep(stepNumber)       // Navigate to step (with validation)
validateStep1()          // Returns: bool (required fields filled)

// Bank Details Modal
openBankModal(id)        // Opens with employee data
closeBankModal()
saveBankDetails()        // Saves e.bank, e.holder, e.account, e.ifsc

// PF Details Modal
openPFModal(id)          // Opens with employee data
closePFModal()
savePFDetails()          // Saves e.pf_no, e.esic_no, e.pf_amount

// Salary Edit Modal
openEditModal(id)        // Opens with salary data
closeEditModal()
saveEdit()               // Saves e.salary, e.advance, e.deduction, e.ot
calcNet()                // Recalculates: m-net = formula result
```

#### **Rendering**

```javascript
// Employee Grid on Employees page
renderEmployeeGrid()
// Filters by: search, location, site
// Renders: .emp-card elements in #emp-grid
// Updates: employee avatars, badges, buttons

// Salary Table on Salary page
renderSalaryTable()
// Filters by: sf-name, sf-loc, sf-site, sf-bank
// Renders: table rows with salary data
// Updates: net pay, bank info, action buttons

// Statistics
renderStats()
// Renders: .stats-row with summary info
// Calculates: total employees, total net payout

// Filter Dropdowns
populateFilterDropdowns()
// Populates: location, site, bank dropdowns from data
```

#### **Calculations**

```javascript
// Calculate net pay for employee
netPay(e)
// Formula: Math.max(0, e.salary + e.ot - e.advance - e.deduction)
// Returns: number (₹ value, never negative)

// Format currency
fmt(n)
// Input: number
// Output: string "₹45,000" (Indian locale)

// Get employee initials for avatar
initials(n)
// Input: "Arun Kumar"
// Output: "AK"

// Get avatar color
clr(id)
// Input: employee id
// Output: hex color from COLORS array
```

#### **Filtering**

```javascript
// Get unique values for filter dropdowns
getUnique(key)
// Input: "location" | "site" | "bank"
// Output: array of unique values, sorted

// Get filtered employee list
getFilteredList()
// Reads: sf-name, sf-loc, sf-site, sf-bank inputs
// Returns: filtered employees array
// Used by: PDF report, Excel report, salary table

// Filter salary table
filterTable()
// Updates: #salary-tbody with filtered rows
// Called by: filter changes
```

#### **Data Persistence**

```javascript
// Load data from localStorage
loadData()
// Key: 'salaryMgr_v4'
// Falls back to: sample data if key not found
// Sets: employees[], nextId

// Save to localStorage
persist()
// Saves: {employees: [], nextId: N}
// Called by: every data modification

// Import from JSON string
importJson()
// Reads: #json-area textarea
// Validates: must be array
// Skips: duplicates
// Adds: new employees to existing list
```

#### **Reporting**

```javascript
// Generate PDF report
generatePDF()
// Input: filtered employees list
// Output: downloads Salary_Report_DATE.pdf
// Uses: jsPDF + jsPDF.autotable
// Columns: #, Name, Bank, IFSC, Holder, Account, Net Pay

// Generate Excel report
generateExcel()
// Input: filtered employees list
// Output: downloads Salary_Report_DATE.xlsx
// Creates: multiple sheets (All, By Bank, By Location, By Site)
// Uses: XLSX library

// Bulk import from Excel/CSV
bulkImportExcel(input)
// Input: file element from import
// Reads: first sheet only
// Maps: Name, Role, Location, Site, Salary, Bank, Account, IFSC
// Returns: toast with import results
```

#### **UI Utilities**

```javascript
// Show notification toast
toast(msg, type='success')
// Types: 'success', 'error', 'info'
// Displays: 3.2 seconds then disappears

// Clear error message for input
clearE(id)
// Removes: 'show' class from error element

// Show/Hide modals
openRemoveMode()         // Shows remove mode notice
cancelRemoveMode()       // Hides remove mode notice
askRemove(id)           // Shows confirmation dialog
confirmRemove()         // Removes employee + closes dialog
closeConfirmModal()     // Closes confirmation dialog

// Page navigation
showPage(p, btn)
// Pages: 'employees' | 'salary'
// Updates: active page, active tab button
// Re-renders: appropriate page content
```

#### **Theme Management**

```javascript
// Apply theme
applyTheme(theme)
// Themes: 'light' | 'dark' | 'custom'
// Sets: data-theme attribute on html
// Saves: to localStorage (key: 'salaryMgr_theme')

// Load saved theme
loadTheme()
// Gets: from localStorage or defaults to 'light'
// Applies: applyTheme()

// Live custom color updates
liveCustom()
// Reads: color picker inputs (c-bg, c-surface, etc)
// Injects: CSS into #ct-style style tag
// Updates: live as user adjusts colors

// Lighten/Darken hex color
lh(hex, amt)
// Input: "#2563eb", +10 (lighter) or -10 (darker)
// Output: new hex color
// Used by: custom theme for subtle contrasts

// Reset custom theme
resetCustom()
// Sets: all color pickers to default custom values
// Calls: liveCustom() to apply
```

---

## localStorage Schema

### Key: `'salaryMgr_v4'`

```javascript
{
  employees: [
    {
      id, name, role, location, site,
      salary, ot, advance, deduction,
      bank, holder, account, ifsc,
      pf_no, esic_no, pf_amount
    },
    // ... more employees
  ],
  nextId: 9  // Auto-increment counter
}
```

### Key: `'salaryMgr_theme'`

```
Value: 'light' | 'dark' | 'custom'
Used by: loadTheme() on page load
```

### Key: `'smCustomCSS'`

```css
/* Only if theme = 'custom' */
[data-theme="custom"]{
  --bg: #fdf4f0;
  --surface: #ffffff;
  --primary: #c0392b;
  /* ... all CSS variables */
}
```

---

## Django Integration Guide

### Zero-Integration (Current State)

```
salary-manager.html works 100% offline
Data stored only in browser localStorage
No server communication
Good for: Single-user, offline-first scenarios
```

### Step 1: Add Django API Endpoints

Create in your Django app:

```python
# api/views.py
@csrf_exempt
@require_http_methods(["POST"])
def create_employee(request):
    data = json.loads(request.body)
    employee = Employee.objects.create(
        name=data['name'],
        role=data['role'],
        location=data['location'],
        site=data['site'],
        salary=data.get('salary', 0),
        designation=data['role'],
        admin=request.user.admin_profile
    )
    return JsonResponse({
        'status': 'success',
        'id': employee.id,
        'message': f'{data["name"]} created successfully'
    })

@csrf_exempt
@require_http_methods(["POST"])
def save_salary(request, employee_id):
    data = json.loads(request.body)
    employee = Employee.objects.get(id=employee_id)
    salary = SalaryUpdate.objects.create(
        employee=employee,
        basic_salary=data['salary'],
        ot_allowance=data['ot'],
        advance_pay=data['advance'],
        total_deduction=data['deduction'],
        admin=request.user.admin_profile
    )
    return JsonResponse({
        'status': 'success',
        'net_pay': salary.basic_salary + salary.ot_allowance - salary.advance_pay - salary.total_deduction
    })
```

### Step 2: Modify salary-manager.html JavaScript

```javascript
// Add this at top level:
const API_BASE = 'http://localhost:8000/api';
const USE_API = true; // Toggle for API usage

// Wrap saveEmployee() with API call:
async function saveEmployee(stepFrom) {
  // ... existing validation ...
  
  if (USE_API) {
    try {
      const response = await fetch(`${API_BASE}/employees/create/`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(e)
      });
      const result = await response.json();
      if (result.status === 'success') {
        e.id = result.id; // Update ID from server
        toast(result.message);
      } else {
        throw new Error(result.error);
      }
    } catch (error) {
      toast(`API Error: ${error.message}`, 'error');
      return;
    }
  }
  
  // ... rest of existing code (still save to localStorage) ...
}
```

### Step 3: Handle Bank & PF Endpoints

```javascript
// Save bank details with API
async function saveBankDetails() {
  const e = emp(bankEditId);
  // ... update e.bank, e.holder, e.account, e.ifsc ...
  
  if (USE_API) {
    await fetch(`${API_BASE}/employees/${e.id}/bank/`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        bank: e.bank,
        holder: e.holder,
        account: e.account,
        ifsc: e.ifsc
      })
    });
  }
  
  persist(); // Still update localStorage
  closeBankModal();
  renderEmployeeGrid();
  toast('🏦 Bank details saved');
}

// Similarly for savePFDetails()
async function savePFDetails() {
  const e = emp(pfEditId);
  // ... update e.pf_no, e.esic_no, e.pf_amount ...
  
  if (USE_API) {
    await fetch(`${API_BASE}/employees/${e.id}/pf/`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        pf_no: e.pf_no,
        esic_no: e.esic_no,
        pf_amount: e.pf_amount
      })
    });
  }
  
  persist();
  closePFModal();
  renderEmployeeGrid();
  toast('📋 PF details saved');
}
```

### Step 4: Sync Salary Updates

```javascript
// Modify saveEdit() to call backend
async function saveEdit() {
  const e = emp(editingId);
  const updatedData = {
    salary: +document.getElementById('m-salary').value || 0,
    advance: +document.getElementById('m-advance').value || 0,
    deduction: +document.getElementById('m-deduction').value || 0,
    ot: +document.getElementById('m-ot').value || 0
  };
  
  if (USE_API) {
    await fetch(`${API_BASE}/salary/update/${e.id}/`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(updatedData)
    });
  }
  
  // Apply changes locally
  e.salary = updatedData.salary;
  e.advance = updatedData.advance;
  e.deduction = updatedData.deduction;
  e.ot = updatedData.ot;
  
  persist();
  closeEditModal();
  renderStats();
  renderSalaryTable();
  toast('✅ Salary updated');
}
```

---

## Backend Endpoints

### Required Django URLs

```python
# urls.py
urlpatterns = [
    path('api/employees/create/', create_employee, name='create_employee'),
    path('api/employees/<int:id>/', get_employee, name='get_employee'),
    path('api/employees/<int:id>/bank/', save_bank, name='save_bank'),
    path('api/employees/<int:id>/pf/', save_pf, name='save_pf'),
    path('api/salary/update/<int:id>/', save_salary, name='save_salary'),
]
```

### Request/Response Formats

```javascript
// POST /api/employees/create/
Request: {
  "name": "Arun Kumar",
  "role": "Site Engineer",
  "location": "Tirunelveli",
  "site": "Site 1 - Valliyur",
  "salary": 45000,
  "ot": 2000
}

Response: {
  "status": "success",
  "id": 1,
  "message": "Arun Kumar created successfully"
}

───────────────────────────────────────

// POST /api/employees/1/bank/
Request: {
  "bank": "State Bank of India",
  "holder": "Arun Kumar",
  "account": "3256789012",
  "ifsc": "SBIN0001234"
}

Response: {
  "status": "success",
  "message": "Bank details saved"
}

───────────────────────────────────────

// POST /api/employees/1/pf/
Request: {
  "pf_no": "DL/001234001",
  "esic_no": "10001001001",
  "pf_amount": 3600
}

Response: {
  "status": "success",
  "message": "PF details saved"
}

───────────────────────────────────────

// POST /api/salary/update/1/
Request: {
  "salary": 45000,
  "advance": 3000,
  "deduction": 1500,
  "ot": 2000
}

Response: {
  "status": "success",
  "net_pay": 42500
}
```

---

## Database Models

### Django Models

```python
# employees/models.py

class Employee(models.Model):
    """Employee master data"""
    id = models.AutoField(primary_key=True)
    admin = models.ForeignKey(AdminProfile, on_delete=models.CASCADE)
    
    # Identity
    name = models.CharField(max_length=100, unique=True)
    employee_id = models.CharField(max_length=50, blank=True)
    role = models.CharField(max_length=100)
    designation = models.CharField(max_length=100)
    
    # Assignment
    location = models.CharField(max_length=100)
    site = models.CharField(max_length=100)
    
    # Salary
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Dates
    joining_date = models.DateField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    STATUS_CHOICES = [('Active', 'Active'), ('Inactive', 'Inactive')]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    
    class Meta:
        ordering = ['-joining_date']
    
    def __str__(self):
        return self.name


class BankDetail(models.Model):
    """One-to-One with Employee"""
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='bank_details')
    bank_name = models.CharField(max_length=100, blank=True)
    account_holder = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    ifsc_code = models.CharField(max_length=20, blank=True)
    branch = models.CharField(max_length=100, blank=True)


class PFDetail(models.Model):
    """One-to-One with Employee - For Payslip Only"""
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='pf_details')
    pf_number = models.CharField(max_length=50, blank=True)
    uan_number = models.CharField(max_length=50, blank=True)
    esic_number = models.CharField(max_length=20, blank=True)
    pf_employer_contribution = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pf_employee_contribution = models.DecimalField(max_digits=10, decimal_places=2, default=0)


class SalaryUpdate(models.Model):
    """Monthly salary record - OT included"""
    id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    admin = models.ForeignKey(AdminProfile, on_delete=models.SET_NULL, null=True)
    
    # Salary Components
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    extra_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ot_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # NEW
    
    # Deductions
    advance_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # PF Snapshots (for payslip audit trail)
    pf_employee_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pf_employer_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    month = models.DateField()
    
    @property
    def net_pay(self):
        """Formula: Salary + OT - Advance - Deduction"""
        return max(0, self.basic_salary + self.ot_allowance - self.advance_pay - self.total_deduction)
    
    class Meta:
        unique_together = ('employee', 'month', 'admin')
```

---

## Code Structure

### File Organization

```
salary-manager.html (Single file architecture - currently)
├─ HTML (top to bottom)
│  ├─ Head: Imports, styles, meta
│  ├─ Header: Navigation, theme selector
│  ├─ Page 1: Employees (grid + filters)
│  ├─ Page 2: Salary (table + reports)
│  ├─ Modals:
│  │  ├─ Add Employee (3-step)
│  │  ├─ Bank Details Modal
│  │  ├─ PF Details Modal
│  │  ├─ Edit Salary Modal
│  │  ├─ JSON Import/Export Modal
│  │  ├─ Custom Theme Modal
│  │  └─ Confirmation Modal
│  └─ Toast notification container
│
├─ CSS (middle section)
│  ├─ Theme tokens (CSS variables)
│  ├─ Base styles (*, body, html)
│  ├─ Components (header, buttons, forms, etc)
│  ├─ Layout (page, card, grid, table)
│  ├─ Modals & Overlays
│  ├─ Responsive (media queries)
│  └─ Animations (@keyframes)
│
└─ JavaScript (bottom section)
   ├─ Constants & State
   ├─ Persistence (localStorage)
   ├─ Helpers & Utilities
   ├─ Employee Management
   ├─ Modal Management
   ├─ Rendering & UI
   ├─ Filtering & Calculations
   ├─ Reporting (PDF/Excel)
   ├─ Data Import/Export
   ├─ Theme Management
   ├─ Page Navigation
   └─ Initialization (on document load)
```

### State Management

```javascript
// Global State (all in memory)
let employees = [];      // Array of employee objects
let nextId = 1;          // Auto-increment for new IDs
let editingId = null;    // Currently editing which employee
let bankEditId = null;   // Currently editing which bank
let removingId = null;   // Currently removing which employee
let removeModeOn = false;// Is remove mode active
let pfEditId = null;     // Currently editing which PF
let addStep = 1;         // Current step in add modal (1, 2, 3)
```

---

## Extending the Module

### Adding a New Field

**Example: Add "Department" field**

```javascript
// 1. Modify employee object initialization
const e = {
  id: nextId++,
  name: '...',
  department: document.getElementById('a-dept').value.trim(), // NEW
  // ... rest of fields
};

// 2. Add form input in HTML
<div class="form-group">
  <label>Department</label>
  <input class="form-input" id="a-dept" type="text" placeholder="e.g. Engineering">
</div>

// 3. Update edit modal to show field
document.getElementById('m-dept').value = e.department || '';

// 4. Include in filters if needed
const depts = getUnique('department');
```

### Adding a New Modal

**Example: Add "Emergency Contacts" modal**

```html
<!-- 1. Add modal HTML -->
<div class="modal-overlay" id="emergency-modal">
  <div class="modal">
    <div class="modal-header">
      <h3>🚨 Emergency Contacts — <span id="em-name"></span></h3>
      <button class="modal-close" onclick="closeEmergencyModal()">✕</button>
    </div>
    <div class="modal-body">
      <!-- form fields -->
    </div>
    <div class="modal-footer">
      <button class="btn btn-outline" onclick="closeEmergencyModal()">Cancel</button>
      <button class="btn btn-success" onclick="saveEmergency()">Save</button>
    </div>
  </div>
</div>
```

```javascript
// 2. Add JavaScript functions
let emergencyEditId = null;

function openEmergencyModal(id) {
  emergencyEditId = id;
  const e = emp(id);
  // populate form from e.emergency_contacts
  document.getElementById('emergency-modal').classList.add('open');
}

function closeEmergencyModal() {
  document.getElementById('emergency-modal').classList.remove('open');
  emergencyEditId = null;
}

function saveEmergency() {
  const e = emp(emergencyEditId);
  // update e.emergency_contacts fields
  persist();
  closeEmergencyModal();
  toast('🚨 Emergency contacts saved');
}

// 3. Add click handler
document.getElementById('emergency-modal').addEventListener('click', function(ev){
  if(ev.target === this) closeEmergencyModal();
});

// 4. Add button to employee card
<button class="btn-bank-edit" onclick="openEmergencyModal(${e.id})">
  🚨 Emergency Contacts
</button>
```

### Adding a New Report

**Example: Add "Tax Summary" report**

```javascript
function generateTaxReport() {
  const list = getFilteredList();
  if (!list.length) {
    toast('No employees to report.', 'error');
    return;
  }
  
  // Calculate tax for each employee
  const taxData = list.map(e => ({
    name: e.name,
    salary: e.salary + e.ot,
    advance: e.advance,
    tax: Math.floor((e.salary + e.ot - e.advance) * 0.10), // Example: 10% tax
    net: (e.salary + e.ot) - e.advance - (Math.floor((e.salary + e.ot - e.advance) * 0.10))
  }));
  
  // Create Excel workbook
  const wb = XLSX.utils.book_new();
  const wsData = [
    ['TAX SUMMARY REPORT'],
    ['Generated', new Date().toLocaleDateString('en-IN')],
    [],
    ['Name', 'Gross Salary', 'Advance', 'Tax (10%)', 'Net After Tax'],
    ...taxData.map(t => [t.name, t.salary, t.advance, t.tax, t.net])
  ];
  
  const ws = XLSX.utils.aoa_to_sheet(wsData);
  XLSX.utils.book_append_sheet(wb, ws, 'Tax Summary');
  XLSX.writeFile(wb, 'Tax_Report_' + new Date().toISOString().slice(0,10) + '.xlsx');
  
  toast('📊 Tax report downloaded!');
}
```

---

## Performance Notes

### Optimization Tips

```javascript
// Current O(n) operations:
isDuplicate(name) - O(n) search through employees
getUnique(key)    - O(n) process all employees
renderEmployeeGrid() - O(n) for each employee card
renderSalaryTable() - O(n) for each table row

// For 1000+ employees, consider:
// 1. Pagination (show 50 per page)
// 2. Virtual scrolling (render only visible rows)
// 3. Indexed map for isDuplicate():
   const nameMap = new Map(employees.map(e => [e.name.toLowerCase(), e.id]));
   isDuplicate(name) { return nameMap.has(name.toLowerCase()); }

// 4. Memoize getUnique() results between renders
// 5. Debounce renderEmployeeGrid() on search input
```

### Storage Limits

```javascript
// Browser localStorage limits:
// Firefox: 10 MB per domain
// Chrome: 5-10 MB per domain
// Safari: 5-10 MB per domain
// IE: 10 MB per domain

// Estimate:
// 1 employee ≈ 300 bytes (when serialized to JSON)
// 1000 employees ≈ 300 KB (safe)
// 10,000 employees ≈ 3 MB (still safe)
// 100,000 employees ≈ 30 MB (might exceed limits)

// Solution for large datasets:
// - Consider backend storage
// - Use IndexedDB instead of localStorage
// - Archive old data to backend
```

---

## Testing Guide

```javascript
// Manual Testing Checklist

□ Employee Creation
  □ Step 1: Name, Role, Location, Site (required)
  □ Step 1: Salary, OT (optional, numeric)
  □ Step 2: Bank fields (optional)
  □ Step 3: PF fields (optional)
  □ Validate: Can't skip required fields
  □ Validate: Duplicate names rejected
  □ Validate: OT goes into formula

□ Salary Calculation
  □ Net Pay = Salary + OT - Advance - Deduction
  □ Net Pay never negative (capped at 0)
  □ Formula updates in real-time
  □ OT included in table
  □ OT included in net pay cell

□ PF Handling
  □ PF data saved separately
  □ PF doesn't affect net pay
  □ PF appears in payslip output
  □ PF not visible in salary table

□ Reports
  □ PDF downloads successfully
  □ PDF has correct columns
  □ Excel downloads with correct number of sheets
  □ JSON export/import works bidirectionally

□ Persistence
  □ Data survives page refresh
  □ Data survives browser restart
  □ localStorage properly formatted
  □ nextId increments correctly

□ UI/UX
  □ Responsive on mobile
  □ Modals close on outside click
  □ Toasts disappear after 3 seconds
  □ Filters update grid in real-time
  □ Themes switch without page reload
```

---

## Browser Compatibility

```
✅ Chrome/Edge (v90+)
✅ Firefox (v88+)
✅ Safari (v14+)
❌ IE 11 (not supported - uses ES6+)

Required Features:
- localStorage API
- Array.map(), Array.filter()
- Template literals
- fetch() API (for future backend integration)
- Fetch + CORS for API calls
```

---

## Version History & Migration

```
v1.0 (2026-03-30):
  + Initial release
  + 3-step employee wizard
  + Bank details management
  + PF/ESIC tracking
  + OT/Extra Allowance field
  + Net Pay formula with OT
  + PDF & Excel reports
  + Theme support
  + Offline localStorage

Migration from earlier versions:
  localStorage key changed to 'salaryMgr_v4'
  Old data must be exported as JSON and re-imported
  New fields (ot, pf_no, esic_no, pf_amount) added
```

---

**Last Updated**: March 30, 2026  
**For**: Developers integrating with Django backend  
**Status**: Production Ready ✅
