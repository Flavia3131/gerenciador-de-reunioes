"""Componente de Dados (repositório): todo o SQL do Auth Service."""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth.db")
PUBLIC = "id, name, email"  # nunca expõe password_hash


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")


def insert_user(name, email, password_hash):
    with get_conn() as conn:
        cur = conn.execute("INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                           (name, email, password_hash))
        return cur.lastrowid


def get_user(user_id):
    with get_conn() as conn:
        row = conn.execute(f"SELECT {PUBLIC} FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_user_by_email(email):
    with get_conn() as conn:
        row = conn.execute(f"SELECT {PUBLIC} FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def get_credentials_by_email(email):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def get_password_hash(user_id):
    with get_conn() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
        return row["password_hash"] if row else None


def list_users():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(f"SELECT {PUBLIC} FROM users ORDER BY name")]


def update_user(user_id, name, email):
    with get_conn() as conn:
        conn.execute("UPDATE users SET name=?, email=? WHERE id=?", (name, email, user_id))


def update_password(user_id, password_hash):
    with get_conn() as conn:
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (password_hash, user_id))


def delete_user(user_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
