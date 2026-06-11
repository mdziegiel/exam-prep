import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = Path(os.getenv('DATABASE_PATH', '/data/exam-prep.sqlite'))

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS exams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    vendor TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 90,
    passing_score INTEGER NOT NULL DEFAULT 70,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS objectives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id TEXT NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    title TEXT NOT NULL,
    weight INTEGER NOT NULL DEFAULT 0,
    UNIQUE(exam_id, code)
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id TEXT NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    objective_id INTEGER REFERENCES objectives(id),
    question_text TEXT NOT NULL,
    choices_json TEXT NOT NULL,
    correct_choice TEXT NOT NULL,
    explanation TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'seed',
    source_url TEXT DEFAULT '',
    verified INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1,
    difficulty INTEGER NOT NULL DEFAULT 2,
    fingerprint TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id TEXT NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    correct_count INTEGER NOT NULL DEFAULT 0,
    wrong_count INTEGER NOT NULL DEFAULT 0,
    streak INTEGER NOT NULL DEFAULT 0,
    mastery REAL NOT NULL DEFAULT 0,
    next_due TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen TEXT,
    total_time_seconds INTEGER NOT NULL DEFAULT 0,
    flagged INTEGER NOT NULL DEFAULT 0,
    UNIQUE(exam_id, question_id)
);

CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id TEXT NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    mode TEXT NOT NULL,
    score REAL NOT NULL,
    passed INTEGER NOT NULL,
    correct INTEGER NOT NULL,
    total INTEGER NOT NULL,
    time_taken_seconds INTEGER NOT NULL,
    breakdown_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS refresh_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id TEXT,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    imported INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('PRAGMA foreign_keys=ON')
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)

def row_to_dict(row):
    if row is None:
        return None
    d = dict(row)
    for key in ('choices_json', 'breakdown_json'):
        if key in d:
            d[key.replace('_json', '')] = json.loads(d.pop(key))
    return d

def now_iso():
    return datetime.utcnow().isoformat(timespec='seconds') + 'Z'
