"""Componente de Dados (repositório): todo o SQL do Meetings Service."""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "meetings.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # necessário para ON DELETE CASCADE
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organizer_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            room TEXT,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            recurrence TEXT,
            status TEXT NOT NULL DEFAULT 'scheduled')""")
        conn.execute("""CREATE TABLE IF NOT EXISTS meeting_participants (
            meeting_id INTEGER NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL,
            PRIMARY KEY (meeting_id, user_id))""")


def insert_meeting(organizer_id, title, room, start_time, end_time, recurrence):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO meetings (organizer_id, title, room, start_time, end_time, recurrence) VALUES (?, ?, ?, ?, ?, ?)",
            (organizer_id, title, room, start_time, end_time, recurrence),
        )
        return cur.lastrowid


def add_participants(meeting_id, ids):
    with get_conn() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO meeting_participants (meeting_id, user_id) VALUES (?, ?)",
            [(meeting_id, uid) for uid in ids],
        )


def _participants(conn, meeting_id):
    rows = conn.execute(
        "SELECT user_id FROM meeting_participants WHERE meeting_id = ? ORDER BY user_id", (meeting_id,)
    )
    return [r["user_id"] for r in rows]


def get_meeting(meeting_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        if not row:
            return None
        meeting = dict(row)
        meeting["participant_ids"] = _participants(conn, meeting_id)
        return meeting


def list_meetings(user_id=None):
    with get_conn() as conn:
        if user_id is None:
            rows = conn.execute("SELECT * FROM meetings ORDER BY start_time, id").fetchall()
        else:
            rows = conn.execute(
                """SELECT m.* FROM meetings m
                   JOIN meeting_participants p ON p.meeting_id = m.id
                   WHERE p.user_id = ? ORDER BY m.start_time, m.id""",
                (user_id,),
            ).fetchall()
        result = []
        for row in rows:
            m = dict(row)
            m["participant_ids"] = _participants(conn, m["id"])
            result.append(m)
        return result


def update_meeting(meeting_id, title, room, start_time, end_time, recurrence):
    with get_conn() as conn:
        conn.execute(
            "UPDATE meetings SET title=?, room=?, start_time=?, end_time=?, recurrence=? WHERE id=?",
            (title, room, start_time, end_time, recurrence, meeting_id),
        )


def replace_participants(meeting_id, ids):
    with get_conn() as conn:
        conn.execute("DELETE FROM meeting_participants WHERE meeting_id = ?", (meeting_id,))
        conn.executemany(
            "INSERT INTO meeting_participants (meeting_id, user_id) VALUES (?, ?)",
            [(meeting_id, uid) for uid in ids],
        )


def set_status(meeting_id, status):
    with get_conn() as conn:
        conn.execute("UPDATE meetings SET status = ? WHERE id = ?", (status, meeting_id))


def find_conflicts(user_ids, start, end, exclude_id=None):
    """IDs dos usuários (entre user_ids) que já têm reunião 'scheduled' sobreposta ao intervalo."""
    if not user_ids:
        return []
    placeholders = ",".join("?" for _ in user_ids)
    sql = f"""SELECT DISTINCT p.user_id FROM meetings m
        JOIN meeting_participants p ON p.meeting_id = m.id
        WHERE p.user_id IN ({placeholders}) AND m.status = 'scheduled'
          AND m.start_time < ? AND m.end_time > ?
          AND (? IS NULL OR m.id != ?)"""
    params = [*user_ids, end, start, exclude_id, exclude_id]
    with get_conn() as conn:
        return [r["user_id"] for r in conn.execute(sql, params)]
