# Inventory System (MVP)

A simple inventory management system for a small stationery shop.

## Features
- Add products with cost, sale price, quantity, low-stock limit
- Record purchases (increases stock)
- Record sales (decreases stock)
- Delete sale record (restores stock)
- Delete purchase record (reverts stock if available)
- Edit product details (name, prices, quantity, low-stock limit)
- Edit purchase qty/cost (auto-adjusts stock)
- Edit sale qty/price (auto-adjusts stock)
- Prevent sales when stock is insufficient
- Daily summary with total sales, total cost, and total profit
- Stock page with low-stock indicator

## Run locally
1. Create virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```
2. Install dependencies
```bash
pip install -r requirements.txt
```
3. Run app
```bash
python server.py
```
4. Open in browser
`http://127.0.0.1:5000`

## Notes
- Database is SQLite (`inventory.db`) and auto-created on first run.
- This is intentionally minimal and designed for easy extension.

## Data Safety and Backup
### 1) Secure credentials
In your PythonAnywhere WSGI file, set:
```python
os.environ["APP_USERNAME"] = "your-username"
os.environ["APP_PASSWORD"] = "your-password"
os.environ["SECRET_KEY"] = "a-long-random-secret"
```
Important: do not commit real credentials into GitHub. Keep them only in server environment settings.

### 2) Lock database file permissions
Run in PythonAnywhere Bash:
```bash
cd /home/<your-username>/inventory_system
chmod 600 inventory.db
```

### 3) Create a safe backup
```bash
cd /home/<your-username>/inventory_system
./scripts/backup_db.sh
```

### 4) Verify backup works (important)
```bash
sqlite3 backups/<backup-file-name>.db ".tables"
```
If tables are listed (`products`, `purchases`, `sales`), backup is valid.

### 5) Schedule daily backup on PythonAnywhere
- Go to `Tasks` tab -> add a daily task:
```bash
cd /home/<your-username>/inventory_system && ./scripts/backup_db.sh
```

### 6) Restore if needed
```bash
cp /home/<your-username>/inventory_system/backups/<backup-file-name>.db /home/<your-username>/inventory_system/inventory.db
```
Then reload web app.

## Delete Logic Notes
- Deleting a `sale` adds sold quantity back to stock.
- Deleting a `purchase` removes purchased quantity from stock.
- Purchase deletion is blocked if it would make stock negative.
- Product deletion is allowed only when there is no purchase/sale history.
- Editing purchase/sale does not change product selection; delete and recreate if wrong product was picked.

## Deploy on PythonAnywhere (Free)
1. Push project to GitHub.
2. In PythonAnywhere, open a `Bash` console and clone your repo:
```bash
git clone <your-repo-url>
cd inventory_system
python3.10 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
3. In PythonAnywhere dashboard, create a new web app:
- Choose `Manual configuration` and `Python 3.10`.
4. Set paths in Web tab:
- Source code: `/home/<your-username>/inventory_system`
- Working directory: `/home/<your-username>/inventory_system`
5. Edit the WSGI file and replace its content with:
```python
import sys
path = '/home/<your-username>/inventory_system'
if path not in sys.path:
    sys.path.insert(0, path)

from wsgi import application
```
6. In Web tab, set virtualenv path:
- `/home/<your-username>/inventory_system/.venv`
7. Click `Reload`.

Your app will be live at:
`https://<your-username>.pythonanywhere.com`
