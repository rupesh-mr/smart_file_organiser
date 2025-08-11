import sqlite3
from datetime import datetime

DB_FILE = "file_logs.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            path TEXT,
            filetype TEXT,
            category TEXT,
            summary TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_file(filename, path, filetype, category, summary):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO files (filename, path, filetype, category, summary, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        filename,
        path,
        filetype,
        category,
        summary,
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()
