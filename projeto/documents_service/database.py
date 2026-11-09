"""Componente de Dados (repositório): todo o SQL do Documents Service."""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents.db")
NOW = "strftime('%Y-%m-%dT%H:%M:%SZ','now')"

# Documento + dados do arquivo da versão atual
_SELECT = """SELECT d.id, d.meeting_id, d.doc_type, d.title, d.description, d.created_by, d.created_at,
        d.updated_at, d.current_version, v.filename, v.content_type, v.size, v.uploaded_by,
        v.uploaded_at AS file_uploaded_at,
        (SELECT COUNT(*) FROM document_versions WHERE document_id = d.id) AS version_count
    FROM documents d JOIN document_versions v ON v.document_id = d.id AND v.version = d.current_version"""


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER NOT NULL,
            doc_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created_by INTEGER NOT NULL,
            current_version INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS document_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            version INTEGER NOT NULL,
            filename TEXT NOT NULL,
            content_type TEXT NOT NULL,
            size INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            stored_name TEXT NOT NULL,
            uploaded_by INTEGER NOT NULL,
            uploaded_at TEXT NOT NULL,
            UNIQUE (document_id, version))""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_meeting ON documents(meeting_id)")


def _insert_version(conn, doc_id, version, info):
    conn.execute(
        f"""INSERT INTO document_versions (document_id, version, filename, content_type, size, sha256,
            stored_name, uploaded_by, uploaded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, {NOW})""",
        (doc_id, version, info["filename"], info["content_type"], info["size"], info["sha256"],
         info["stored_name"], info["uploaded_by"]))


def insert_document(meeting_id, doc_type, title, description, created_by, info):
    with get_conn() as conn:
        cur = conn.execute(
            f"""INSERT INTO documents (meeting_id, doc_type, title, description, created_by,
                current_version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1, {NOW}, {NOW})""",
            (meeting_id, doc_type, title, description, created_by))
        _insert_version(conn, cur.lastrowid, 1, info)
        return cur.lastrowid


def add_version(doc_id, info):
    with get_conn() as conn:
        current = conn.execute("SELECT current_version FROM documents WHERE id = ?", (doc_id,)).fetchone()[0]
        _insert_version(conn, doc_id, current + 1, info)
        conn.execute(f"UPDATE documents SET current_version = ?, updated_at = {NOW} WHERE id = ?",
                     (current + 1, doc_id))
        return current + 1


def get_document(doc_id):
    with get_conn() as conn:
        row = conn.execute(_SELECT + " WHERE d.id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None


def list_documents(meeting_ids, doc_type=None):
    if not meeting_ids:
        return []
    sql = _SELECT + f" WHERE d.meeting_id IN ({','.join('?' for _ in meeting_ids)})"
    params = list(meeting_ids)
    if doc_type:
        sql += " AND d.doc_type = ?"
        params.append(doc_type)
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql + " ORDER BY d.updated_at DESC, d.id DESC", params)]


def get_versions(doc_id):
    """Histórico (sem o nome interno do arquivo)."""
    with get_conn() as conn:
        rows = conn.execute("""SELECT version, filename, content_type, size, sha256, uploaded_by, uploaded_at
            FROM document_versions WHERE document_id = ? ORDER BY version DESC""", (doc_id,))
        return [dict(r) for r in rows]


def get_version(doc_id, version):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM document_versions WHERE document_id = ? AND version = ?",
                           (doc_id, version)).fetchone()
        return dict(row) if row else None


def update_document(doc_id, doc_type, title, description):
    with get_conn() as conn:
        conn.execute(f"UPDATE documents SET doc_type=?, title=?, description=?, updated_at={NOW} WHERE id=?",
                     (doc_type, title, description, doc_id))


def delete_document(doc_id):
    """Remove o documento (versões caem em cascata) e devolve os nomes internos dos arquivos."""
    with get_conn() as conn:
        names = [r[0] for r in conn.execute(
            "SELECT stored_name FROM document_versions WHERE document_id = ?", (doc_id,))]
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        return names
