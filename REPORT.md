# Project Report: Trekking Management Application

**Student Name:** _[fill in]_
**Roll No. / ID:** 24f10020
**Course / Subject:** _[fill in]_
**Submission Date:** _[fill in]_
**Video Walkthrough Link:** _[fill in — 5–10 min video URL]_

---

## 1. Problem Statement & Approach

Adventure/trekking organizations currently coordinate treks, staff, and
participants manually using spreadsheets and phone calls. This causes
overbooking, poor visibility into trek history, and slow staff approvals.

This project builds a **role-based web application** with three roles —
**Admin**, **Trek Staff**, and **Trekker (User)** — that digitizes this
entire workflow end-to-end:

1. The database schema was designed first (Users, Treks, Bookings — see
   ER diagram below), with a single `users` table holding all three
   roles distinguished by a `role` column, to keep authentication simple
   and centralized.
2. The role-based flow was planned as: **register → (admin approval for
   staff only) → login → role-specific dashboard → role-specific actions**.
3. Flask project structure was set up with `database.py` handling all
   schema creation and admin seeding programmatically at startup (no
   manual DB tool was used at any point).
4. Session-based authentication was implemented using Flask's built-in
   `session` object plus two decorators, `@login_required` and
   `@role_required(role)`, that guard every protected route.
5. Admin features were built first (trek CRUD, staff/user approval &
   blacklisting, search), then Staff features (view assigned treks,
   update slots/status, view participants), then User features (browse
   & filter open treks, book, cancel, view history, edit profile).
6. Validation rules were added directly in the route handlers: slot
   counts are checked before every booking to prevent overbooking, only
   the staff member stored in a trek's `assigned_staff_id` can manage
   that trek, and only `Open` treks with free slots can be booked.
7. The UI was styled with Bootstrap 5 and a small custom stylesheet, and
   the whole flow was tested end-to-end with an automated test script
   exercising all three roles (registration, approval, booking,
   overbooking prevention, cancellation, search, blacklisting).

## 2. AI / LLM Usage Declaration

This project was built with the assistance of **Claude (Anthropic)**,
an AI coding assistant, which was used to:
- Design the database schema and route structure.
- Generate the Flask routes, Jinja2 templates, and CSS.
- Write and run an automated end-to-end test script to verify all
  business rules (overbooking prevention, approval gating, role
  isolation) before delivery.

All generated code was reviewed and tested by the student before
submission. _[Adjust this section to accurately reflect your own usage
and your institution's AI-declaration requirements.]_

## 3. Frameworks & Libraries Used

| Component        | Technology                         |
|-------------------|-------------------------------------|
| Backend framework | Flask 3.x (Python)                 |
| Templating        | Jinja2                             |
| Frontend styling  | Bootstrap 5 (CSS + bundled JS for cosmetic widgets only) |
| Database          | SQLite 3, accessed via Python's built-in `sqlite3` module (no ORM) |
| Password hashing  | Werkzeug's `generate_password_hash` / `check_password_hash` |
| Sessions          | Flask's built-in signed-cookie `session` |

No JavaScript is used for any core functionality (authentication,
booking, filtering, CRUD, approvals) — every one of those actions is a
plain HTML `<form>` or link handled entirely server-side. The only JS
on any page is Bootstrap's own bundle, used purely for the collapsible
navbar and modal pop-ups; the underlying forms work as normal HTML even
without it.

## 4. ER Diagram

```
┌───────────────────────────┐        ┌───────────────────────────┐
│          USERS            │        │           TREKS            │
├───────────────────────────┤        ├───────────────────────────┤
│ id (PK)                   │◄──┐    │ id (PK)                    │
│ username (UNIQUE)         │   │    │ name                       │
│ password_hash             │   │    │ location                   │
│ role  (admin/staff/user)  │   └────┤ assigned_staff_id (FK→users)│
│ full_name                 │        │ difficulty                 │
│ email                     │        │ duration_days               │
│ contact                   │        │ total_slots                 │
│ approval_status           │        │ available_slots             │
│  (active/pending/         │        │ status (Pending/Open/       │
│   blacklisted)            │        │   Closed/Ongoing/Completed) │
│ created_at                │        │ start_date / end_date        │
└─────────────┬─────────────┘        │ created_at                  │
              │                      └──────────────┬──────────────┘
              │ 1                                    │ 1
              │                                       │
              │            ┌──────────────────────────┘
              │            │
              │ N          │ N
        ┌─────▼────────────▼─────┐
        │        BOOKINGS         │
        ├──────────────────────────┤
        │ id (PK)                  │
        │ user_id  (FK → users)    │
        │ trek_id  (FK → treks)    │
        │ booking_date              │
        │ status (Booked/           │
        │   Cancelled/Completed)    │
        └──────────────────────────┘
```

**Relationships**
- One **user** (role = staff) is assigned to zero or many **treks** (1:N via `treks.assigned_staff_id`).
- One **user** (role = user) can have zero or many **bookings** (1:N via `bookings.user_id`).
- One **trek** can have zero or many **bookings** (1:N via `bookings.trek_id`).
- `bookings` is the resolving entity for the many-to-many relationship between Users and Treks.

## 5. API / Route Endpoints

All endpoints are server-rendered HTML routes (this is a traditional
Flask + Jinja2 app, not a JSON API), listed here for completeness:

| Route | Method(s) | Role | Purpose |
|---|---|---|---|
| `/` | GET | Any | Home / redirects to the right dashboard |
| `/register` | GET, POST | Public | Self-registration (staff or user) |
| `/login` | GET, POST | Public | Login |
| `/logout` | GET | Any | Logout |
| `/admin/dashboard` | GET | Admin | Totals: treks, users+staff, bookings |
| `/admin/treks` | GET | Admin | List/search treks |
| `/admin/treks/add` | POST | Admin | Create a trek |
| `/admin/treks/edit/<id>` | POST | Admin | Edit a trek, assign staff |
| `/admin/treks/approve/<id>` | GET | Admin | Move trek Pending → Open |
| `/admin/treks/delete/<id>` | GET | Admin | Delete a trek |
| `/admin/staff` | GET | Admin | List/search staff |
| `/admin/staff/approve/<id>` | GET | Admin | Approve a pending staff account |
| `/admin/staff/blacklist/<id>` | GET | Admin | Blacklist a staff account |
| `/admin/staff/reactivate/<id>` | GET | Admin | Reactivate a blacklisted staff account |
| `/admin/users` | GET | Admin | List/search trekkers |
| `/admin/users/blacklist/<id>` | GET | Admin | Blacklist a trekker |
| `/admin/users/reactivate/<id>` | GET | Admin | Reactivate a trekker |
| `/staff/dashboard` | GET | Staff | List treks assigned to the logged-in staff member |
| `/staff/trek/<id>` | GET | Staff | View trek details + participant list |
| `/staff/trek/<id>/update` | POST | Staff | Update slots / status (Open/Closed/Ongoing/Completed) |
| `/user/dashboard` | GET | User | Upcoming bookings + history count |
| `/user/treks` | GET | User | Browse/filter open treks (difficulty, location) |
| `/user/treks/<id>/book` | POST | User | Book a trek (overbooking prevented) |
| `/user/bookings` | GET | User | Full booking history |
| `/user/bookings/<id>/cancel` | GET | User | Cancel a booking (frees the slot) |
| `/user/profile` | GET, POST | User | View/edit profile |

## 6. Extra Features Beyond the Minimum Spec

- Auto-close: a trek automatically flips to `Closed` the instant its
  last slot is booked, and automatically re-opens if a cancellation
  frees a slot on a trek that was auto-closed.
- Full booking history is preserved forever (rows are never deleted —
  only their `status` changes), satisfying "Admin can view all
  historical trekking data" and "Full booking history per user."
- Search works across ID, name, and location/username in a single box
  for treks, staff, and users.
- Completing a trek automatically marks all of its active bookings as
  `Completed` in the same action, so staff don't have to update every
  booking individually.

## 7. Video Walkthrough

_[Insert your 5–10 minute video link here, covering: intro, approach,
key features per role, and any extra features.]_
