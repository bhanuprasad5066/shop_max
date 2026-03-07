# Shop Max - AI Based E-commerce Web Application

Resume-ready full-stack Myntra-inspired project using Flask, MySQL (XAMPP), HTML, CSS, and JavaScript.

## Tech Stack
- Backend: Python, Flask
- Frontend: HTML, CSS, JavaScript
- Database: MySQL (XAMPP)
- Payments: Razorpay (test mode)
- Invoices: PDF (ReportLab)
- Dev Tooling: VS Code

## Project Structure
```text
shop_max/
|-- app.py
|-- requirements.txt
|-- .env.example
|-- database/
|   |-- schema.sql
|   `-- seed.sql
|-- shopmax/
|   |-- __init__.py
|   |-- config.py
|   |-- db.py
|   |-- auth.py
|   |-- store.py
|   |-- cart.py
|   `-- checkout.py
|-- templates/
|   |-- base.html
|   |-- index.html
|   |-- products.html
|   |-- product_detail.html
|   |-- cart.html
|   |-- checkout.html
|   |-- orders.html
|   |-- order_detail.html
|   |-- login.html
|   |-- register.html
|   `-- admin_products.html
`-- static/
    |-- css/style.css
    `-- js/main.js
```

## Setup (Windows + XAMPP + VS Code)
1. Start `Apache` and `MySQL` from XAMPP Control Panel.
2. Open `http://localhost/phpmyadmin`.
3. Run SQL from:
   - `database/schema.sql`
   - `database/seed.sql`
4. In VS Code terminal:
```powershell
cd C:\shop_max
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```
5. Update `.env` with MySQL and Razorpay test credentials.
6. Run the app:
```powershell
venv\\Scripts\\python.exe app.py
```
7. Open:
   - Home: `http://127.0.0.1:5000/`
   - Admin login: `admin@shopmax.com`
   - Admin password: `admin123`

## Feature Highlights
- User registration/login with hashed passwords
- Product listing, search, filter, and details page
- Session-based cart
- Razorpay checkout and payment verification
- Order history and order details`r`n- Cash on Delivery checkout option`r`n- Cancel order with stock rollback`r`n- Invoice PDF download per order
- Admin product management

## Razorpay Test Flow
1. Add products to cart.
2. Click `Proceed to Checkout`.
3. Pay with Razorpay test mode.
4. Order is saved and visible in `Orders`.
5. Download invoice from order details page.

## Notes
- `.env` is gitignored and should store secrets.
- This project is interview-ready and easy to extend with AI recommendations.

