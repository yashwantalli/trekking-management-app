"""
app.py
------
Main Flask application for the Trekking Management System.

Roles:
  - admin : pre-seeded, manages treks/staff/users
  - staff : self-registers, needs admin approval, manages assigned treks
  - user  : self-registers, browses & books treks

No JavaScript is used for core functionality — all actions (booking,
approving, editing) are done through plain HTML forms and full page
reloads, handled entirely by Flask + Jinja2.
"""

from functools import wraps
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from database import init_db, get_db_connection

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-this-in-production"  # needed for session/flash


# =====================================================================
# Helpers & decorators
# =====================================================================

def login_required(view):
    """Redirect to login if no user is in the session."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def role_required(role):
    """Restrict a view to a specific role (admin / staff / user)."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if session.get("role") != role:
                flash("You are not authorized to view that page.", "danger")
                return redirect(url_for("login"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def current_user():
    """Fetch the full row of the logged-in user, or None."""
    if "user_id" not in session:
        return None
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    conn.close()
    return user


def now_str():
    return datetime.now().isoformat(timespec="seconds")


# =====================================================================
# Public routes: home, register, login, logout
# =====================================================================

@app.route("/")
def home():
    if "user_id" in session:
        role = session.get("role")
        if role == "admin":
            return redirect(url_for("admin_dashboard"))
        elif role == "staff":
            return redirect(url_for("staff_dashboard"))
        else:
            return redirect(url_for("user_dashboard"))
    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Self-registration for Staff and Users (not Admin)."""
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        full_name = request.form["full_name"].strip()
        email = request.form.get("email", "").strip()
        contact = request.form.get("contact", "").strip()
        role = request.form["role"]  # 'staff' or 'user'

        if role not in ("staff", "user"):
            flash("Invalid role selected.", "danger")
            return redirect(url_for("register"))

        conn = get_db_connection()
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()

        if existing:
            flash("That username is already taken.", "danger")
            conn.close()
            return redirect(url_for("register"))

        # Staff accounts start 'pending' until admin approves them.
        # User accounts are 'active' immediately.
        approval_status = "pending" if role == "staff" else "active"

        conn.execute("""
            INSERT INTO users (username, password_hash, role, full_name,
                                email, contact, approval_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (username, generate_password_hash(password), role, full_name,
              email, contact, approval_status, now_str()))
        conn.commit()
        conn.close()

        if role == "staff":
            flash("Registration successful! Your account needs admin approval "
                  "before you can log in.", "info")
        else:
            flash("Registration successful! You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password.", "danger")
            return redirect(url_for("login"))

        if user["approval_status"] == "blacklisted":
            flash("Your account has been blacklisted. Contact the admin.", "danger")
            return redirect(url_for("login"))

        if user["role"] == "staff" and user["approval_status"] == "pending":
            flash("Your staff account is awaiting admin approval.", "warning")
            return redirect(url_for("login"))

        # Log the user in
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        session["full_name"] = user["full_name"]

        flash(f"Welcome back, {user['full_name']}!", "success")

        if user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        elif user["role"] == "staff":
            return redirect(url_for("staff_dashboard"))
        else:
            return redirect(url_for("user_dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# =====================================================================
# ADMIN routes
# =====================================================================

@app.route("/admin/dashboard")
@login_required
@role_required("admin")
def admin_dashboard():
    conn = get_db_connection()
    trek_count = conn.execute("SELECT COUNT(*) c FROM treks").fetchone()["c"]
    people_count = conn.execute(
        "SELECT COUNT(*) c FROM users WHERE role IN ('staff','user')"
    ).fetchone()["c"]
    booking_count = conn.execute("SELECT COUNT(*) c FROM bookings").fetchone()["c"]
    pending_staff = conn.execute(
        "SELECT COUNT(*) c FROM users WHERE role='staff' AND approval_status='pending'"
    ).fetchone()["c"]
    recent_treks = conn.execute(
        "SELECT * FROM treks ORDER BY created_at DESC LIMIT 5"
    ).fetchall()
    conn.close()
    return render_template("admin/dashboard.html",
                            trek_count=trek_count,
                            people_count=people_count,
                            booking_count=booking_count,
                            pending_staff=pending_staff,
                            recent_treks=recent_treks)


# ---- Admin: Treks CRUD ----------------------------------------------

@app.route("/admin/treks")
@login_required
@role_required("admin")
def admin_treks():
    q = request.args.get("q", "").strip()
    conn = get_db_connection()
    if q:
        treks = conn.execute("""
            SELECT treks.*, users.full_name AS staff_name
            FROM treks LEFT JOIN users ON treks.assigned_staff_id = users.id
            WHERE treks.name LIKE ? OR treks.location LIKE ? OR treks.id = ?
            ORDER BY treks.created_at DESC
        """, (f"%{q}%", f"%{q}%", q if q.isdigit() else -1)).fetchall()
    else:
        treks = conn.execute("""
            SELECT treks.*, users.full_name AS staff_name
            FROM treks LEFT JOIN users ON treks.assigned_staff_id = users.id
            ORDER BY treks.created_at DESC
        """).fetchall()
    staff_list = conn.execute(
        "SELECT id, full_name FROM users WHERE role='staff' AND approval_status='active'"
    ).fetchall()
    conn.close()
    return render_template("admin/treks.html", treks=treks, staff_list=staff_list, q=q)


@app.route("/admin/treks/add", methods=["POST"])
@login_required
@role_required("admin")
def admin_add_trek():
    name = request.form["name"].strip()
    location = request.form["location"].strip()
    difficulty = request.form["difficulty"]
    duration_days = int(request.form["duration_days"])
    total_slots = int(request.form["total_slots"])
    start_date = request.form.get("start_date", "")
    end_date = request.form.get("end_date", "")

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO treks (name, location, difficulty, duration_days, total_slots,
                            available_slots, status, start_date, end_date, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?, ?, ?)
    """, (name, location, difficulty, duration_days, total_slots, total_slots,
          start_date, end_date, now_str()))
    conn.commit()
    conn.close()
    flash(f"Trek '{name}' created.", "success")
    return redirect(url_for("admin_treks"))


@app.route("/admin/treks/edit/<int:trek_id>", methods=["POST"])
@login_required
@role_required("admin")
def admin_edit_trek(trek_id):
    name = request.form["name"].strip()
    location = request.form["location"].strip()
    difficulty = request.form["difficulty"]
    duration_days = int(request.form["duration_days"])
    total_slots = int(request.form["total_slots"])
    start_date = request.form.get("start_date", "")
    end_date = request.form.get("end_date", "")
    assigned_staff_id = request.form.get("assigned_staff_id") or None

    conn = get_db_connection()
    trek = conn.execute("SELECT * FROM treks WHERE id = ?", (trek_id,)).fetchone()
    if trek is None:
        flash("Trek not found.", "danger")
        conn.close()
        return redirect(url_for("admin_treks"))

    # Keep "already booked" slots consistent when total_slots changes
    booked = trek["total_slots"] - trek["available_slots"]
    new_available = max(total_slots - booked, 0)

    conn.execute("""
        UPDATE treks SET name=?, location=?, difficulty=?, duration_days=?,
            total_slots=?, available_slots=?, start_date=?, end_date=?,
            assigned_staff_id=?
        WHERE id=?
    """, (name, location, difficulty, duration_days, total_slots, new_available,
          start_date, end_date, assigned_staff_id, trek_id))
    conn.commit()
    conn.close()
    flash(f"Trek '{name}' updated.", "success")
    return redirect(url_for("admin_treks"))


@app.route("/admin/treks/approve/<int:trek_id>")
@login_required
@role_required("admin")
def admin_approve_trek(trek_id):
    """Move a trek from Pending -> Open (admin publishes it)."""
    conn = get_db_connection()
    conn.execute("UPDATE treks SET status='Open' WHERE id=? AND status='Pending'", (trek_id,))
    conn.commit()
    conn.close()
    flash("Trek approved and opened for booking.", "success")
    return redirect(url_for("admin_treks"))


@app.route("/admin/treks/delete/<int:trek_id>")
@login_required
@role_required("admin")
def admin_delete_trek(trek_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM bookings WHERE trek_id = ?", (trek_id,))
    conn.execute("DELETE FROM treks WHERE id = ?", (trek_id,))
    conn.commit()
    conn.close()
    flash("Trek deleted.", "info")
    return redirect(url_for("admin_treks"))


# ---- Admin: Staff management ------------------------------------------

@app.route("/admin/staff")
@login_required
@role_required("admin")
def admin_staff():
    q = request.args.get("q", "").strip()
    conn = get_db_connection()
    if q:
        staff = conn.execute("""
            SELECT * FROM users WHERE role='staff'
            AND (full_name LIKE ? OR username LIKE ? OR id = ?)
            ORDER BY created_at DESC
        """, (f"%{q}%", f"%{q}%", q if q.isdigit() else -1)).fetchall()
    else:
        staff = conn.execute(
            "SELECT * FROM users WHERE role='staff' ORDER BY created_at DESC"
        ).fetchall()
    conn.close()
    return render_template("admin/staff.html", staff=staff, q=q)


@app.route("/admin/staff/approve/<int:user_id>")
@login_required
@role_required("admin")
def admin_approve_staff(user_id):
    conn = get_db_connection()
    conn.execute("UPDATE users SET approval_status='active' WHERE id=? AND role='staff'", (user_id,))
    conn.commit()
    conn.close()
    flash("Staff member approved.", "success")
    return redirect(url_for("admin_staff"))


@app.route("/admin/staff/blacklist/<int:user_id>")
@login_required
@role_required("admin")
def admin_blacklist_staff(user_id):
    conn = get_db_connection()
    conn.execute("UPDATE users SET approval_status='blacklisted' WHERE id=? AND role='staff'", (user_id,))
    conn.commit()
    conn.close()
    flash("Staff member blacklisted.", "warning")
    return redirect(url_for("admin_staff"))


@app.route("/admin/staff/reactivate/<int:user_id>")
@login_required
@role_required("admin")
def admin_reactivate_staff(user_id):
    conn = get_db_connection()
    conn.execute("UPDATE users SET approval_status='active' WHERE id=? AND role='staff'", (user_id,))
    conn.commit()
    conn.close()
    flash("Staff member reactivated.", "success")
    return redirect(url_for("admin_staff"))


# ---- Admin: Users management -------------------------------------------

@app.route("/admin/users")
@login_required
@role_required("admin")
def admin_users():
    q = request.args.get("q", "").strip()
    conn = get_db_connection()
    if q:
        users = conn.execute("""
            SELECT * FROM users WHERE role='user'
            AND (full_name LIKE ? OR username LIKE ? OR id = ?)
            ORDER BY created_at DESC
        """, (f"%{q}%", f"%{q}%", q if q.isdigit() else -1)).fetchall()
    else:
        users = conn.execute(
            "SELECT * FROM users WHERE role='user' ORDER BY created_at DESC"
        ).fetchall()
    conn.close()
    return render_template("admin/users.html", users=users, q=q)


@app.route("/admin/users/blacklist/<int:user_id>")
@login_required
@role_required("admin")
def admin_blacklist_user(user_id):
    conn = get_db_connection()
    conn.execute("UPDATE users SET approval_status='blacklisted' WHERE id=? AND role='user'", (user_id,))
    conn.commit()
    conn.close()
    flash("User blacklisted.", "warning")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/reactivate/<int:user_id>")
@login_required
@role_required("admin")
def admin_reactivate_user(user_id):
    conn = get_db_connection()
    conn.execute("UPDATE users SET approval_status='active' WHERE id=? AND role='user'", (user_id,))
    conn.commit()
    conn.close()
    flash("User reactivated.", "success")
    return redirect(url_for("admin_users"))


# =====================================================================
# STAFF routes
# =====================================================================

@app.route("/staff/dashboard")
@login_required
@role_required("staff")
def staff_dashboard():
    conn = get_db_connection()
    treks = conn.execute(
        "SELECT * FROM treks WHERE assigned_staff_id = ? ORDER BY created_at DESC",
        (session["user_id"],)
    ).fetchall()
    conn.close()
    return render_template("staff/dashboard.html", treks=treks)


@app.route("/staff/trek/<int:trek_id>")
@login_required
@role_required("staff")
def staff_trek_detail(trek_id):
    conn = get_db_connection()
    trek = conn.execute(
        "SELECT * FROM treks WHERE id = ? AND assigned_staff_id = ?",
        (trek_id, session["user_id"])
    ).fetchone()
    if trek is None:
        flash("You are not assigned to that trek.", "danger")
        conn.close()
        return redirect(url_for("staff_dashboard"))

    participants = conn.execute("""
        SELECT bookings.*, users.full_name, users.email, users.contact
        FROM bookings JOIN users ON bookings.user_id = users.id
        WHERE bookings.trek_id = ? AND bookings.status != 'Cancelled'
        ORDER BY bookings.booking_date
    """, (trek_id,)).fetchall()
    conn.close()
    return render_template("staff/trek_detail.html", trek=trek, participants=participants)


@app.route("/staff/trek/<int:trek_id>/update", methods=["POST"])
@login_required
@role_required("staff")
def staff_update_trek(trek_id):
    conn = get_db_connection()
    trek = conn.execute(
        "SELECT * FROM treks WHERE id = ? AND assigned_staff_id = ?",
        (trek_id, session["user_id"])
    ).fetchone()
    if trek is None:
        flash("You are not assigned to that trek.", "danger")
        conn.close()
        return redirect(url_for("staff_dashboard"))

    new_status = request.form["status"]
    available_slots = int(request.form["available_slots"])

    # Staff can only toggle between the operational statuses, not skip
    # straight to Completed without going Ongoing first — kept simple here.
    valid_transitions = {"Open", "Closed", "Ongoing", "Completed"}
    if new_status not in valid_transitions:
        flash("Invalid status.", "danger")
        conn.close()
        return redirect(url_for("staff_trek_detail", trek_id=trek_id))

    if available_slots > trek["total_slots"] or available_slots < 0:
        flash("Available slots must be between 0 and total slots.", "danger")
        conn.close()
        return redirect(url_for("staff_trek_detail", trek_id=trek_id))

    conn.execute(
        "UPDATE treks SET status=?, available_slots=? WHERE id=?",
        (new_status, available_slots, trek_id)
    )

    # If trek is marked Completed, mark all active bookings as Completed too
    if new_status == "Completed":
        conn.execute(
            "UPDATE bookings SET status='Completed' WHERE trek_id=? AND status='Booked'",
            (trek_id,)
        )

    conn.commit()
    conn.close()
    flash("Trek updated.", "success")
    return redirect(url_for("staff_trek_detail", trek_id=trek_id))


# =====================================================================
# USER (Trekker) routes
# =====================================================================

@app.route("/user/dashboard")
@login_required
@role_required("user")
def user_dashboard():
    conn = get_db_connection()
    upcoming = conn.execute("""
        SELECT bookings.*, treks.name AS trek_name, treks.location, treks.start_date, treks.status AS trek_status
        FROM bookings JOIN treks ON bookings.trek_id = treks.id
        WHERE bookings.user_id = ? AND bookings.status = 'Booked'
        ORDER BY treks.start_date
    """, (session["user_id"],)).fetchall()
    history_count = conn.execute(
        "SELECT COUNT(*) c FROM bookings WHERE user_id = ?", (session["user_id"],)
    ).fetchone()["c"]
    conn.close()
    return render_template("user/dashboard.html", upcoming=upcoming, history_count=history_count)


@app.route("/user/treks")
@login_required
@role_required("user")
def user_treks():
    difficulty = request.args.get("difficulty", "")
    location = request.args.get("location", "").strip()

    query = "SELECT * FROM treks WHERE status = 'Open'"
    params = []
    if difficulty:
        query += " AND difficulty = ?"
        params.append(difficulty)
    if location:
        query += " AND location LIKE ?"
        params.append(f"%{location}%")
    query += " ORDER BY start_date"

    conn = get_db_connection()
    treks = conn.execute(query, params).fetchall()

    # Which of these has the current user already booked?
    my_bookings = conn.execute(
        "SELECT trek_id FROM bookings WHERE user_id=? AND status='Booked'",
        (session["user_id"],)
    ).fetchall()
    booked_trek_ids = {row["trek_id"] for row in my_bookings}
    conn.close()

    return render_template("user/treks.html", treks=treks, difficulty=difficulty,
                            location=location, booked_trek_ids=booked_trek_ids)


@app.route("/user/treks/<int:trek_id>/book", methods=["POST"])
@login_required
@role_required("user")
def user_book_trek(trek_id):
    conn = get_db_connection()
    trek = conn.execute("SELECT * FROM treks WHERE id = ?", (trek_id,)).fetchone()

    if trek is None:
        flash("Trek not found.", "danger")
        conn.close()
        return redirect(url_for("user_treks"))

    # ---- Business rules ----
    if trek["status"] != "Open":
        flash("This trek is not open for booking.", "danger")
        conn.close()
        return redirect(url_for("user_treks"))

    if trek["available_slots"] <= 0:
        flash("Sorry, this trek is fully booked.", "danger")
        conn.close()
        return redirect(url_for("user_treks"))

    already = conn.execute(
        "SELECT id FROM bookings WHERE user_id=? AND trek_id=? AND status='Booked'",
        (session["user_id"], trek_id)
    ).fetchone()
    if already:
        flash("You have already booked this trek.", "info")
        conn.close()
        return redirect(url_for("user_treks"))

    # Prevent overbooking with an atomic-ish check + update
    conn.execute("""
        UPDATE treks SET available_slots = available_slots - 1
        WHERE id = ? AND available_slots > 0
    """, (trek_id,))

    conn.execute("""
        INSERT INTO bookings (user_id, trek_id, booking_date, status)
        VALUES (?, ?, ?, 'Booked')
    """, (session["user_id"], trek_id, now_str()))

    # If that was the last slot, auto-close the trek
    updated_trek = conn.execute("SELECT available_slots FROM treks WHERE id=?", (trek_id,)).fetchone()
    if updated_trek["available_slots"] == 0:
        conn.execute("UPDATE treks SET status='Closed' WHERE id=?", (trek_id,))

    conn.commit()
    conn.close()
    flash(f"Trek '{trek['name']}' booked successfully!", "success")
    return redirect(url_for("user_bookings"))


@app.route("/user/bookings")
@login_required
@role_required("user")
def user_bookings():
    conn = get_db_connection()
    bookings = conn.execute("""
        SELECT bookings.*, treks.name AS trek_name, treks.location,
               treks.difficulty, treks.start_date, treks.end_date
        FROM bookings JOIN treks ON bookings.trek_id = treks.id
        WHERE bookings.user_id = ?
        ORDER BY bookings.booking_date DESC
    """, (session["user_id"],)).fetchall()
    conn.close()
    return render_template("user/bookings.html", bookings=bookings)


@app.route("/user/bookings/<int:booking_id>/cancel")
@login_required
@role_required("user")
def user_cancel_booking(booking_id):
    conn = get_db_connection()
    booking = conn.execute(
        "SELECT * FROM bookings WHERE id=? AND user_id=?",
        (booking_id, session["user_id"])
    ).fetchone()

    if booking is None:
        flash("Booking not found.", "danger")
        conn.close()
        return redirect(url_for("user_bookings"))

    if booking["status"] != "Booked":
        flash("Only active bookings can be cancelled.", "warning")
        conn.close()
        return redirect(url_for("user_bookings"))

    conn.execute("UPDATE bookings SET status='Cancelled' WHERE id=?", (booking_id,))
    # Free up the slot, and reopen the trek if it had been auto-closed
    trek = conn.execute("SELECT * FROM treks WHERE id=?", (booking["trek_id"],)).fetchone()
    conn.execute("UPDATE treks SET available_slots = available_slots + 1 WHERE id=?",
                 (booking["trek_id"],))
    if trek["status"] == "Closed":
        conn.execute("UPDATE treks SET status='Open' WHERE id=?", (booking["trek_id"],))

    conn.commit()
    conn.close()
    flash("Booking cancelled.", "info")
    return redirect(url_for("user_bookings"))


@app.route("/user/profile", methods=["GET", "POST"])
@login_required
@role_required("user")
def user_profile():
    conn = get_db_connection()
    if request.method == "POST":
        full_name = request.form["full_name"].strip()
        email = request.form.get("email", "").strip()
        contact = request.form.get("contact", "").strip()
        conn.execute(
            "UPDATE users SET full_name=?, email=?, contact=? WHERE id=?",
            (full_name, email, contact, session["user_id"])
        )
        conn.commit()
        session["full_name"] = full_name
        flash("Profile updated.", "success")

    user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    conn.close()
    return render_template("user/profile.html", user=user)


# =====================================================================
# Entry point
# =====================================================================

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
