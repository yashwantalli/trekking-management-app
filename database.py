"""
database.py
-----------
Everything related to the SQLite database lives here:
  - connecting to the database
  - creating tables (schema)
  - seeding the default Admin account
  - small helper functions used by app.py

We use Python's built-in sqlite3 module directly (no ORM) so that the
SQL is visible and easy to follow for anyone reading the project.
"""

import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash

DB_NAME = "trekking.db"

# Default admin credentials (pre-seeded, as required by the spec).
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "123admin"   # change after first login in a real deployment


def get_db_connection():
    """Return a new SQLite connection with rows accessible by column name."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    # Enforce foreign key constraints (off by default in SQLite)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """
    Create all tables if they do not already exist, and seed the admin
    account. Safe to call every time the app starts.
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # ---------------------------------------------------------------
    # USERS table
    # Holds every person in the system: admin, staff, and trekkers.
    # role              : 'admin' | 'staff' | 'user'
    # approval_status   : 'active'   -> can log in and use the app
    #                      'pending' -> staff waiting for admin approval
    #                      'blacklisted' -> blocked from logging in
    # ---------------------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'staff', 'user')),
            full_name TEXT NOT NULL,
            email TEXT,
            contact TEXT,
            approval_status TEXT NOT NULL DEFAULT 'active'
                CHECK(approval_status IN ('active', 'pending', 'blacklisted')),
            created_at TEXT NOT NULL
        )
    """)

    # ---------------------------------------------------------------
    # TREKS table
    # status: 'Pending' -> just created by admin, not yet open
    #         'Open'    -> users can book
    #         'Closed'  -> no more bookings (slots full / manually closed)
    #         'Ongoing' -> trek has started
    #         'Completed' -> trek finished
    # assigned_staff_id : which staff member manages this trek (nullable)
    # ---------------------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS treks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            difficulty TEXT NOT NULL CHECK(difficulty IN ('Easy', 'Moderate', 'Hard')),
            duration_days INTEGER NOT NULL,
            total_slots INTEGER NOT NULL,
            available_slots INTEGER NOT NULL,
            assigned_staff_id INTEGER,
            status TEXT NOT NULL DEFAULT 'Pending'
                CHECK(status IN ('Pending', 'Open', 'Closed', 'Ongoing', 'Completed')),
            start_date TEXT,
            end_date TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (assigned_staff_id) REFERENCES users(id)
        )
    """)

    # ---------------------------------------------------------------
    # BOOKINGS table
    # status: 'Booked' | 'Cancelled' | 'Completed'
    # ---------------------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            trek_id INTEGER NOT NULL,
            booking_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Booked'
                CHECK(status IN ('Booked', 'Cancelled', 'Completed')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (trek_id) REFERENCES treks(id)
        )
    """)

    conn.commit()

    # ---------------------------------------------------------------
    # Seed the admin account (only once)
    # ---------------------------------------------------------------
    existing = cur.execute(
        "SELECT id FROM users WHERE username = ?", (ADMIN_USERNAME,)
    ).fetchone()

    if existing is None:
        cur.execute("""
            INSERT INTO users (username, password_hash, role, full_name,
                                email, contact, approval_status, created_at)
            VALUES (?, ?, 'admin', 'System Administrator', 'admin@trekapp.com',
                    '0000000000', 'active', ?)
        """, (
            ADMIN_USERNAME,
            generate_password_hash(ADMIN_PASSWORD),
            datetime.now().isoformat(timespec="seconds")
        ))
        conn.commit()
        print(f"[init_db] Seeded default admin -> username: '{ADMIN_USERNAME}', "
              f"password: '{ADMIN_PASSWORD}'")

    conn.close()
