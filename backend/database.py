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

CREATE TABLE IF NOT EXISTS attempt_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    selected_choice TEXT NOT NULL DEFAULT '',
    is_correct INTEGER NOT NULL DEFAULT 0,
    elapsed_seconds INTEGER NOT NULL DEFAULT 0,
    flagged INTEGER NOT NULL DEFAULT 0
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

QUESTION_COLUMNS = {
    'question_type': "TEXT NOT NULL DEFAULT 'single'",
    'correct_json': "TEXT DEFAULT ''",
    'exhibit_json': "TEXT DEFAULT ''",
    'references_json': "TEXT DEFAULT ''",
}


def _columns(conn, table):
    return {row['name'] for row in conn.execute(f'PRAGMA table_info({table})')}


def _migrate(conn):
    cols = _columns(conn, 'questions')
    for name, spec in QUESTION_COLUMNS.items():
        if name not in cols:
            conn.execute(f'ALTER TABLE questions ADD COLUMN {name} {spec}')
    cols = _columns(conn, 'attempts')
    if 'answers_json' not in cols:
        conn.execute("ALTER TABLE attempts ADD COLUMN answers_json TEXT NOT NULL DEFAULT '[]'")
    if 'config_json' not in cols:
        conn.execute("ALTER TABLE attempts ADD COLUMN config_json TEXT NOT NULL DEFAULT '{}'")
    conn.execute("UPDATE questions SET question_type='single' WHERE question_type IS NULL OR question_type='' ")
    conn.execute("UPDATE questions SET correct_json=json_array(correct_choice) WHERE correct_json IS NULL OR correct_json='' ")
    conn.execute("UPDATE questions SET references_json=json_array(json_object('title','Official documentation','url',source_url)) WHERE (references_json IS NULL OR references_json='') AND source_url IS NOT NULL AND source_url<>''")
    conn.execute("UPDATE questions SET references_json=json_array(json_object('title','Microsoft Learn certification documentation','url','https://learn.microsoft.com/en-us/credentials/certifications/')) WHERE references_json IS NULL OR references_json='' ")


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
        _migrate(conn)


def row_to_dict(row):
    if row is None:
        return None
    d = dict(row)
    for key in ('choices_json', 'breakdown_json', 'answers_json', 'config_json', 'correct_json', 'exhibit_json', 'references_json'):
        if key in d:
            raw = d.pop(key)
            try:
                d[key.replace('_json', '')] = json.loads(raw) if raw else ([] if key != 'config_json' else {})
            except Exception:
                d[key.replace('_json', '')] = [] if key != 'config_json' else {}
    return d


def now_iso():
    return datetime.utcnow().isoformat(timespec='seconds') + 'Z'
