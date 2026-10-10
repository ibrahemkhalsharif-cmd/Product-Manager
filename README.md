# Product Manager

> **Work in progress:** this project is being rebuilt in stages. The setup and run instructions below describe the old version and are rewritten in the final stage.

A small two-page web app for managing a shop's product list, with an Arabic, fully right-to-left interface.

- **Products page:** table of all products (name, barcode, category, price, quantity), search by name or barcode, and Edit / Delete buttons on every row (delete asks for confirmation).
- **Add / Edit page:** one form for creating and editing a product. It checks for required fields, positive price and quantity, and duplicate barcodes, then saves to MariaDB and returns to the products page.

## Why Flask (and not FastAPI)

This app is two server-rendered HTML pages with a form. Flask with Jinja templates covers that directly: one route renders a page, one handles the form post, and there is very little to configure. FastAPI is excellent for JSON APIs, async code and auto-generated API docs, but none of those are needed here, so it would add concepts (schemas, a separate template setup, form-parsing add-ons) without making the app better.

## Tech stack

| Item | Choice |
| --- | --- |
| Language | Python 3.10+ |
| Framework | Flask |
| Database | MariaDB (tables `categories` and `products`, linked by a foreign key) |
| DB driver | PyMySQL (pure Python, installs on Windows without extra build tools) |
| Interface | Arabic, `dir="rtl"`, plain CSS (no internet connection needed) |

## Database design

- `categories (id, name)`
- `products (id, name, barcode, price, quantity, category_id)`
  - `barcode` is `UNIQUE`
  - `price > 0` and `quantity > 0` are enforced by `CHECK` constraints
  - `category_id` is a **foreign key** to `categories.id` (`ON DELETE RESTRICT`, so a category that still has products cannot be deleted)

## Installation and running (from scratch)

### 1. Install the prerequisites

Python 3.10 or newer, MariaDB, Git, and VS Code (optional).

### 2. Get the code

```
git clone https://github.com/ibrahemkhalsharif-cmd/TestOne.git
cd TestOne
```

### 3. Create a virtual environment and install packages

Windows (PowerShell):

```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks the activate script, run this once and try again:

```
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

macOS / Linux:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Create the database

Run the SQL script. It creates the `shop_db` database, both tables, and sample Arabic data. Use your own MariaDB port (3306 is the default; 3307 is used in the example below).

```
mariadb -u root -p -h 127.0.0.1 -P 3307 --default-character-set=utf8mb4 -e "source database.sql"
```

You will be asked for your MariaDB root password. Running the script again resets the database to the sample data.

### 5. Configure the connection

Copy the example settings file and edit it:

```
copy .env.example .env        # Windows
cp .env.example .env          # macOS / Linux
```

Open `.env` and set `DB_PASSWORD` to your MariaDB password. Change `DB_PORT` if your MariaDB does not use 3307. `.env` is ignored by Git, so your password is never committed.

### 6. Run the app

```
python app.py
```

Open http://127.0.0.1:5000 in your browser.

## Project structure

```
app.py              Flask routes and validation
config.py           Settings read from .env
db.py               MariaDB connection handling
database.sql        Tables and sample data
requirements.txt    Python packages
.env.example        Template for your local settings
templates/          Jinja pages (base, products, product_form, error)
static/style.css    RTL styling
```

## Troubleshooting

- **"تعذّر الاتصال بقاعدة البيانات" (cannot connect to the database):** check that MariaDB is running and that `DB_HOST`, `DB_PORT`, `DB_USER` and `DB_PASSWORD` in `.env` are correct. If another database server (for example MySQL) also runs on your machine, make sure `DB_PORT` is the MariaDB port, not the other server's.
- **`mariadb` is not recognized:** add MariaDB's `bin` folder (for example `C:\Program Files\MariaDB 13.0\bin`) to your PATH, then open a new terminal.
- **Arabic text looks like `????`:** run the SQL script with `--default-character-set=utf8mb4`, as shown in step 4.
- **Access denied for user:** the password in `.env` does not match the MariaDB user's password.

## Notes

`python app.py` starts Flask's development server in debug mode. That is fine for local use and a demo, but it is not meant for a public deployment.
