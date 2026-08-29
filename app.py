import os
import psycopg
from psycopg.rows import dict_row
#import sqlite3
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-in-production")
DB_PATH = os.environ.get("DB_PATH", "temperature.db")



def get_db():
    return psycopg.connect(
        os.environ["DATABASE_URL"],
        row_factory=dict_row
    )


def init_db():
    conn = get_db()
    admin_username = os.environ.get("ADMIN_USERNAME")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS temperature_logs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            temperature DOUBLE PRECISION NOT NULL,
            recorded_at TIMESTAMPTZ NOT NULL
        )
    """)
    if admin_username and admin_password:
        existing_admin = conn.execute(
            "SELECT id FROM users WHERE username = %s",
            (admin_username,)
        ).fetchone()

        if not existing_admin:
            conn.execute(
                """
                INSERT INTO users
                    (username, password_hash, is_admin, created_at)
                VALUES
                    (%s, %s, TRUE, %s)
                """,
                (
                    admin_username,
                    generate_password_hash(admin_password),
                    datetime.now(timezone.utc)
                )
            )
            conn.commit()
    conn.commit()
    conn.close()

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return "Forbidden", 403
        return view(*args, **kwargs)
    return wrapped


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = %s", (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["is_admin"] = bool(user["is_admin"])
            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()

    # Latest temperature for each user.
    leaderboard = conn.execute("""
        SELECT u.username, t.temperature, t.recorded_at
        FROM users u
        JOIN temperature_logs t ON t.id = (
            SELECT t2.id
            FROM temperature_logs t2
            WHERE t2.user_id = u.id
            ORDER BY t2.recorded_at DESC, t2.id DESC
            LIMIT 1
        )
        ORDER BY t.temperature DESC
    """).fetchall()

    my_logs = conn.execute("""
        SELECT temperature, recorded_at
        FROM temperature_logs
        WHERE user_id = %s
        ORDER BY recorded_at DESC
        LIMIT 10
    """, (session["user_id"],)).fetchall()

    conn.close()
    return render_template(
        "dashboard.html",
        leaderboard=leaderboard,
        my_logs=my_logs
    )


@app.route("/log-temperature", methods=["POST"])
@login_required
def log_temperature():
    try:
        temperature = float(request.form["temperature"])
    except (ValueError, TypeError):
        flash("Please enter a valid temperature.", "error")
        return redirect(url_for("dashboard"))

    # Basic validation. Adjust if your use case needs another range.
    if temperature < 30 or temperature > 45:
        flash("Temperature must be between 30°C and 45°C.", "error")
        return redirect(url_for("dashboard"))

    recorded_at = datetime.now(timezone.utc).isoformat()

    conn = get_db()
    conn.execute(
        "INSERT INTO temperature_logs (user_id, temperature, recorded_at) VALUES (%s, %s, %s)",
        (session["user_id"], temperature, recorded_at)
    )
    conn.commit()
    conn.close()

    flash("Temperature recorded.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin")
@login_required
@admin_required
def admin():
    conn = get_db()
    users = conn.execute(
        "SELECT id, username, is_admin, created_at FROM users ORDER BY username"
    ).fetchall()
    conn.close()
    return render_template("admin.html", users=users)


@app.route("/admin/add-user", methods=["POST"])
@login_required
@admin_required
def add_user():
    username = request.form["username"].strip()
    password = request.form["password"]

    if not username or not password:
        flash("Username and password are required.", "error")
        return redirect(url_for("admin"))

    try:
        conn = get_db()
        conn.execute(
            """INSERT INTO users (username, password_hash, is_admin, created_at)
               VALUES (%s, %s, FALSE, %s)""",
            (
                username,
                generate_password_hash(password),
                datetime.now(timezone.utc).isoformat()
            )
        )
        conn.commit()
        conn.close()
        flash(f"User '{username}' created.", "success")
    except psycopg.errors.UniqueViolation:
        flash("That username already exists.", "error")
    return redirect(url_for("admin"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
