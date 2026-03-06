# AM Academy Inventory System - One Page User Guide

## 1) Access the system
- Website: `https://naureen39.pythonanywhere.com`
- Username: provided by system owner (share privately)
- Password: provided by system owner (share privately)
- After login, you will see the dashboard navigation tabs.

## 2) What each tab does
- `Stock`
  - Shows current quantity of all products.
  - Shows `Low Stock` status when quantity is near limit.

- `Products`
  - Add new products (name, category, cost price, sale price, opening qty, low-stock limit).
  - Edit existing product details.
  - Delete product (only if no purchase/sale history exists).

- `Purchases`
  - Record new stock purchases.
  - Stock quantity automatically increases.
  - Edit purchase qty/cost later if entered wrong.
  - Delete purchase to revert stock (blocked if stock is already consumed).

- `Sales`
  - Record sold items.
  - Stock quantity automatically decreases.
  - System blocks sale if stock is insufficient.
  - Edit sale qty/price later if needed.
  - Delete sale to restore stock.

- `Daily Summary`
  - Select date.
  - View total sales, total cost, and total profit for that day.

## 3) Daily usage flow (recommended)
1. Add products once in `Products` tab.
2. When stock arrives, enter it in `Purchases`.
3. When item is sold, enter it in `Sales`.
4. At day end, check totals in `Daily Summary`.
5. Check `Stock` tab for low-stock alerts.

## 4) Correction rules (important)
- Wrong entry? Use `Edit` first.
- If entry is totally wrong, use `Delete` with confirmation.
- Avoid manually changing product quantity unless really needed.

## 5) Data safety
- Records are saved in database file: `inventory.db`.
- Backup is already supported by script: `./scripts/backup_db.sh`.
- Recommended: keep daily automatic backup task active on PythonAnywhere.

## 6) Quick troubleshooting
- If page looks old after update: hard refresh (`Ctrl+F5` / `Cmd+Shift+R`).
- If login fails: confirm username/password exactly.
- If app is down: reload web app from PythonAnywhere Web tab.

---
For any issue or feature request, contact the system owner/developer.
