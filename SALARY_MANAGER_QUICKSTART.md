# Salary Manager - Quick Start Guide

**Get up and running in 5 minutes** ⚡

---

## 1️⃣ Open the Application

```
Double-click: salary-manager.html
→ Opens in your browser
→ Shows sample employees (optional)
```

---

## 2️⃣ Add Your First Employee

### Button: 👤 Employees → [Add Employee]

```
STEP 1: Employee Details
├─ Employee Name *      → "Ravi Kumar"
├─ Employee Role *      → "Site Engineer"
├─ Location *           → "Tirunelveli"
├─ Site *               → "Site 1 - Valliyur"
├─ Base Salary          → "45000" (or leave blank)
└─ OT / Extra Allowance → "2000" (or leave blank)

BUTTON: [Next → Bank Details]
```

```
STEP 2: Bank Details (OPTIONAL)
├─ Bank Name            → "Canara Bank"
├─ Account Holder Name  → "Ravi Kumar"
├─ Account Number       → "3256789012"
└─ IFSC Code            → "CNRB0001234"

BUTTON: [Next → PF Details]
```

```
STEP 3: PF Details (OPTIONAL - PAYSLIP ONLY)
├─ PF Number            → "DL/001234001"
├─ ESIC Number          → "10123456789"
└─ PF Amount            → "3600"

BUTTON: [Save Employee] ✓
```

---

## 3️⃣ View Employees

All employees appear as **cards** in the grid:

```
┌──────────────────────┐
│      [Avatar]        │
│   Ravi Kumar         │
│   Site Engineer      │
│   📍 Tirunelveli     │
│   🏢 Site 1 - Val... │
│ ✅ Bank details      │
│ [Edit Bank Details]  │
│ ✅ PF details        │
│ [Edit PF Details]    │
└──────────────────────┘
```

**Search or Filter**:
- Type name in search box
- Select location from dropdown
- Select site from dropdown

---

## 4️⃣ Manage Salary

### Tab: 💰 Salary

```
┌──────────────────────────────────────────────────────┐
│ #  Name         Advance  Deduction  OT      Net Pay  │
├──────────────────────────────────────────────────────┤
│ 1  Ravi Kumar   3000     1500      2000    42500    │
│ 2  Priya S...   0        2200      0       52800    │
└──────────────────────────────────────────────────────┘
```

**Edit Salary**:
1. Click **[Edit]** button in row
2. Change: Advance Pay, Deduction, OT, Base Salary
3. See Net Pay update in real-time
4. Click **[Save Changes]**

```
Formula: Net Pay = Salary + OT - Advance - Deduction
```

---

## 5️⃣ Generate Reports

### PDF Report
```
Button: [📄 PDF Report]
↓
Downloads: Salary_Report_2026-03-30.pdf
Contents: Professional table with employee and salary data
```

### Excel Report
```
Button: [📊 Excel Report]
↓
Downloads: Salary_Report_2026-03-30.xlsx
Contents: Multiple sheets (All, By Bank, By Location, etc.)
```

---

## 6️⃣ Backup Your Data

### Export as JSON
```
Button: [JSON Data]
↓
Modal Opens: Shows full JSON array
↓
Click: [Copy] button
↓
Save to file: employees_backup.json
```

### Restore from JSON
```
Button: [JSON Data]
↓
Paste your JSON into textarea
↓
Click: [Import JSON Data]
↓
Toast shows: "Imported X employee(s)"
```

---

## 7️⃣ Bulk Import from Excel

### File Setup (Excel or CSV):

```
Name                | Role              | Location   | Salary
──────────────────────────────────────────────────────
Arun Kumar          | Site Engineer     | Tirunelveli| 45000
Priya Sharma        | HR Manager        | Chennai    | 55000
Ramesh Babu         | Supervisor        | Tirunelveli| 38000
```

### Steps:
```
Button: [Import Excel]
↓
Select the .xlsx or .csv file
↓
Process automatic
↓
Toast shows: "Imported 3 employee(s). Skipped 0"
```

---

## 8️⃣ Change Theme

**Top Right Corner**: Theme Selector

```
☀️ Light  → Clean & bright (default)
🌙 Dark   → Dark blue with light text
🎨 Custom → Pick your own colors
```

---

## Key Fields Reference

| Field | Type | Required | Example | Notes |
|-------|------|----------|---------|-------|
| **Name** | Text | YES ✓ | Ravi Kumar | Cannot duplicate |
| **Role** | Text | YES ✓ | Site Engineer | Any job title |
| **Location** | Text | YES ✓ | Tirunelveli | Team/Area |
| **Site** | Text | YES ✓ | Site 1 - Valliyur | Exact location |
| **Salary** | Number | NO | 45000 | Base monthly pay |
| **OT** | Number | NO | 2000 | **Included in Net Pay** ⭐ |
| **Advance** | Number | NO | 3000 | Deducted from Net Pay |
| **Deduction** | Number | NO | 1500 | Deducted from Net Pay |
| **Bank** | Text | NO | Canara Bank | For payment |
| **Account** | Text | NO | 3256789012 | Bank account |
| **IFSC** | Text | NO | CNRB0001234 | Bank code |
| **PF No** | Text | NO | DL/001234 | **Not in Net Pay calc** ⭐ |
| **ESIC** | Text | NO | 10001001001 | Not in salary calc |
| **PF Amt** | Number | NO | 3600 | **Payslip only** ⭐ |

---

## Important Calculations

### Net Pay Formula

```
Net Pay = Base Salary + OT - Advance - Deduction

✅ OT IS INCLUDED in Net Pay
❌ PF Amount is NOT included in Net Pay
   (PF appears only in payslip output)
```

**Example**:
```
Employee: Ravi Kumar
Base Salary:           ₹45,000
+ OT Allowance:        ₹2,000
- Advance Payment:     ₹3,000
- Total Deduction:     ₹1,500
──────────────────
= Net Pay to Pay:      ₹42,500 ✓

In Payslip (separate):
PF Number:     DL/001234001
PF Amount:     ₹3,600
ESIC Number:   10123456789
(These do NOT change the ₹42,500)
```

---

## Common Tasks

### Add Bank Details to Existing Employee
```
1. Employee card → [Edit Bank Details]
2. Fill 4 fields
3. [Save Bank Details] ✓
4. Badge updates to ✅
```

### Edit PF Details
```
1. Employee card → [Edit PF Details]
2. Fill 3 fields
3. [Save PF Details] ✓
4. Badge updates to ✅
```

### Remove Employee
```
1. [Remove Employee] button
2. ⚠️ Warning appears
3. Click ✕ on employee card
4. Confirm deletion
5. Employee removed permanently
```

### Search Employees
```
1. Employees page
2. Type in search box
3. Results update live
```

### Filter by Location/Site
```
1. Employees page
2. Select from dropdowns
3. Grid filters instantly
```

### Edit Salary Values
```
1. Salary page
2. Click [Edit] in row
3. Change values
4. See Net Pay update
5. [Save Changes] ✓
```

---

## Keyboard Shortcuts

| Action | How |
|--------|-----|
| Close Modal | Click X button or click outside |
| Cancel Form | Click Cancel button |
| Search | Click search box + type |

---

## Data Locations

```
Where is my data saved?
↓
Browser Storage (localStorage)
↓
Persists until you clear browser data
↓
Always backup before clearing browser!
```

---

## Offline Use

✅ **Fully works offline** once loaded
- No internet required
- All data stored locally
- Refresh page to see latest data

⚠️ **To sync with backend**:
- Export JSON
- Use JSON Data buttons
- Or integrate with Django backend

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Data not saving | Enable localStorage in browser settings |
| Employee not appearing | Check search/filter settings |
| Net pay wrong | Verify: Salary + OT - Advance - Deduction |
| Import fails | Use .xlsx or .csv with headers |
| Theme not saving | Check browser privacy settings |
| Missing bank details | Add via employee card [Edit Bank Details] |

---

## Next Steps

1. ✅ Open salary-manager.html
2. ✅ Add 2-3 employees
3. ✅ Add salary details (advance, deduction, OT)
4. ✅ Generate PDF report
5. ✅ Export JSON backup
6. ✅ Try dark theme
7. ✅ Test with Excel import

---

**That's it!** You now know all the essential operations. 🎉

For detailed documentation, see: `SALARY_MANAGER_GUIDE.md`
