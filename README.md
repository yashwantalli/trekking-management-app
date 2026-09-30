# Trekking Management Application

A role-based web application (Admin / Trek Staff / Trekker) that replaces
spreadsheets and phone calls for coordinating treks, staff, and bookings.

Built with **Flask**, **Jinja2 + HTML + Bootstrap 5**, and a **SQLite**
database created entirely in code (no manual DB tooling, no ORM — plain
`sqlite3` so the schema is easy to read in `database.py`).

## How to run

```bash
# 1. (Recommended) create a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app (this creates trekking.db automatically on first run)
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

If you ever want to start over with a fresh database, just delete
`trekking.db` and run `python app.py` again — it will be recreated and
the admin account re-seeded.

## Default admin login

| Field    | Value      |
|----------|------------|
| Username | `admin`    |
| Password | `admin123` |

(Change `ADMIN_PASSWORD` in `database.py` before any real deployment.)

## How the roles work

- **Admin** — pre-seeded, no signup needed. Logs in immediately and can
  create/edit/delete treks, approve or blacklist staff, assign staff to
  treks, blacklist users, and search across everything.
- **Trek Staff** — self-registers via `/register`, but the account sits
  in a `pending` state and **cannot log in** until the admin approves it
  from the Staff page. Once approved and assigned to a trek, staff can
  update that trek's slots/status and see who has booked it.
- **Trekker (User)** — self-registers and can log in immediately. Can
  browse only `Open` treks, filter by difficulty/location, book (with
  automatic overbooking prevention and auto-close when full), cancel a
  booking (which frees the slot and re-opens the trek if needed), and
  view/edit their profile plus full booking history.

## Project structure

```
trekking_app/
├── app.py              # All routes, auth, and business logic
├── database.py         # Schema creation + admin seeding (run automatically)
├── requirements.txt
├── static/css/style.css
└── templates/
    ├── base.html        # Shared layout, navbar, flash messages
    ├── home.html, login.html, register.html
    ├── admin/           # dashboard.html, treks.html, staff.html, users.html
    ├── staff/           # dashboard.html, trek_detail.html
    └── user/            # dashboard.html, treks.html, bookings.html, profile.html
```

## Business rules enforced in code (see `app.py`)

- A trek can only be booked if its `status == 'Open'` and `available_slots > 0`.
- Booking decrements `available_slots` and auto-sets the trek to `Closed`
  when it hits 0; cancelling a booking reverses both.
- Only the staff member stored in `treks.assigned_staff_id` can view or
  update that trek (enforced with a `WHERE assigned_staff_id = <session user>`
  clause on every staff query).
- Staff accounts cannot log in while `approval_status = 'pending'`, and
  no one can log in while `approval_status = 'blacklisted'`.
- Every booking row is kept (status changes to `Cancelled`/`Completed`
  rather than being deleted), so full history is always available to
  both the trekker and the admin.

## Note on JavaScript

Per the assignment requirement, all core functionality (auth, booking,
approvals, filtering, CRUD) is implemented with plain HTML forms and
server-side rendering — **no custom JavaScript is used for any of it**.
The only JS on the page is Bootstrap's own bundle, which powers purely
cosmetic UI widgets (the collapsible navbar and modal dialogs); every
one of those forms still submits and works correctly as a normal HTML
form/link even without it.
