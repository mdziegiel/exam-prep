import hashlib
import json
import os
import random
import re
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pypdf import PdfReader

from database import DB_PATH, connect, init_db, now_iso, row_to_dict
from seed import seed

app = FastAPI(title='IT Exam Prep API', version='1.0.0')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

class AnswerIn(BaseModel):
    question_id: int
    selected_choice: str
    elapsed_seconds: int = 0

class AttemptIn(BaseModel):
    exam_id: str
    mode: str
    answers: list[AnswerIn]
    time_taken_seconds: int

class ManualQuestion(BaseModel):
    exam_id: str
    objective_code: str
    question_text: str
    choices: list[str] = Field(min_length=4, max_length=4)
    correct_choice: str
    explanation: str
    source: str = 'manual'
    verified: bool = False

class ReviewAction(BaseModel):
    action: str
    question: Optional[ManualQuestion] = None

class RefreshIn(BaseModel):
    exam_id: str
    source: str = 'all'


def ensure_ready():
    init_db()
    with connect() as conn:
        count = conn.execute('SELECT COUNT(*) c FROM exams').fetchone()['c']
    if count == 0:
        seed()

@app.on_event('startup')
def startup():
    ensure_ready()

def fingerprint(exam_id: str, text: str) -> str:
    normalized = re.sub(r'\s+', ' ', text).strip().lower()
    return hashlib.sha256(f'{exam_id}:{normalized}'.encode()).hexdigest()

def objective_id(conn, exam_id: str, code: str):
    row = conn.execute('SELECT id FROM objectives WHERE exam_id=? AND code=?', (exam_id, code)).fetchone()
    if not row:
        raise HTTPException(400, f'Unknown objective {code} for {exam_id}')
    return row['id']

def insert_question(conn, q: ManualQuestion, active: int = 0):
    oid = objective_id(conn, q.exam_id, q.objective_code)
    fp = fingerprint(q.exam_id, q.question_text)
    try:
        cur = conn.execute('''INSERT INTO questions(exam_id,objective_id,question_text,choices_json,correct_choice,explanation,source,verified,active,difficulty,fingerprint)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
            (q.exam_id, oid, q.question_text, json.dumps(q.choices), q.correct_choice.upper(), q.explanation, q.source, int(q.verified), active, 2, fp))
        qid = cur.lastrowid
        conn.execute('INSERT OR IGNORE INTO progress(exam_id,question_id) VALUES(?,?)', (q.exam_id, qid))
        return qid, True
    except sqlite3.IntegrityError:
        return conn.execute('SELECT id FROM questions WHERE fingerprint=?', (fp,)).fetchone()['id'], False

def serialize_question(row, reveal=False):
    d = row_to_dict(row)
    if not d:
        return None
    choices = d.pop('choices')
    d['choices'] = [{'key': chr(65+i), 'text': choice} for i, choice in enumerate(choices)]
    if not reveal:
        d.pop('correct_choice', None)
        d.pop('explanation', None)
    return d

@app.get('/api/health')
def health():
    ensure_ready()
    with connect() as conn:
        totals = {r['exam_id']: r['c'] for r in conn.execute('SELECT exam_id, COUNT(*) c FROM questions GROUP BY exam_id')}
    return {'status': 'ok', 'database': str(DB_PATH), 'question_counts': totals}

@app.get('/api/exams')
def exams():
    with connect() as conn:
        output = []
        for exam in conn.execute('SELECT * FROM exams ORDER BY id'):
            e = dict(exam)
            total = conn.execute('SELECT COUNT(*) c FROM questions WHERE exam_id=? AND active=1 AND verified=1', (e['id'],)).fetchone()['c']
            mastered = conn.execute('SELECT COUNT(*) c FROM progress WHERE exam_id=? AND mastery>=0.8', (e['id'],)).fetchone()['c']
            spent = conn.execute('SELECT COALESCE(SUM(total_time_seconds),0) s FROM progress WHERE exam_id=?', (e['id'],)).fetchone()['s']
            e.update({'question_count': total, 'mastered': mastered, 'percent_mastered': round((mastered / total) * 100, 1) if total else 0, 'time_spent_seconds': spent})
            output.append(e)
        return output

@app.get('/api/exams/{exam_id}/objectives')
def objectives(exam_id: str):
    with connect() as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM objectives WHERE exam_id=? ORDER BY code', (exam_id,))]

@app.get('/api/exams/{exam_id}/progress')
def progress(exam_id: str):
    with connect() as conn:
        rows = conn.execute('''SELECT o.code, o.title, COUNT(q.id) total,
            SUM(CASE WHEN p.mastery>=0.8 THEN 1 ELSE 0 END) mastered,
            AVG(p.mastery) avg_mastery,
            SUM(p.total_time_seconds) time_spent
            FROM objectives o JOIN questions q ON q.objective_id=o.id LEFT JOIN progress p ON p.question_id=q.id
            WHERE o.exam_id=? AND q.active=1 AND q.verified=1 GROUP BY o.id ORDER BY o.code''', (exam_id,)).fetchall()
        return [dict(r) for r in rows]

@app.get('/api/exams/{exam_id}/queue')
def queue(exam_id: str, limit: int = Query(10, ge=1, le=100), mode: str = 'practice'):
    order = 'RANDOM()' if mode == 'timed' else 'datetime(p.next_due) ASC, p.mastery ASC, q.difficulty DESC'
    with connect() as conn:
        rows = conn.execute(f'''SELECT q.*, o.code objective_code, o.title objective_title, p.flagged, p.mastery
            FROM questions q JOIN objectives o ON o.id=q.objective_id JOIN progress p ON p.question_id=q.id
            WHERE q.exam_id=? AND q.active=1 AND q.verified=1 ORDER BY {order} LIMIT ?''', (exam_id, limit)).fetchall()
        return [serialize_question(r) for r in rows]

@app.post('/api/answer')
def answer(payload: AnswerIn):
    selected = payload.selected_choice.upper()
    with connect() as conn:
        row = conn.execute('''SELECT q.*, o.code objective_code, o.title objective_title, p.streak, p.correct_count, p.wrong_count, p.mastery
            FROM questions q JOIN objectives o ON o.id=q.objective_id JOIN progress p ON p.question_id=q.id WHERE q.id=?''', (payload.question_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Question not found')
        correct = selected == row['correct_choice']
        streak = (row['streak'] + 1) if correct else 0
        mastery = min(1.0, (row['mastery'] or 0) + (0.18 if correct else -0.12))
        mastery = max(0, mastery)
        delay_days = [0, 1, 3, 7, 14, 30][min(streak, 5)] if correct else 0
        due = (datetime.utcnow() + timedelta(days=delay_days, minutes=10 if not correct else 0)).isoformat(timespec='seconds') + 'Z'
        conn.execute('''UPDATE progress SET correct_count=correct_count+?, wrong_count=wrong_count+?, streak=?, mastery=?, next_due=?, last_seen=?, total_time_seconds=total_time_seconds+? WHERE question_id=?''',
                     (int(correct), int(not correct), streak, mastery, due, now_iso(), payload.elapsed_seconds, payload.question_id))
        q = serialize_question(row, reveal=True)
        q.update({'selected_choice': selected, 'is_correct': correct, 'next_due': due, 'mastery': round(mastery, 2)})
        return q

@app.post('/api/flag/{question_id}')
def flag(question_id: int):
    with connect() as conn:
        row = conn.execute('SELECT flagged FROM progress WHERE question_id=?', (question_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Question not found')
        flagged = 0 if row['flagged'] else 1
        conn.execute('UPDATE progress SET flagged=? WHERE question_id=?', (flagged, question_id))
        return {'question_id': question_id, 'flagged': bool(flagged)}

@app.post('/api/attempts')
def save_attempt(payload: AttemptIn):
    with connect() as conn:
        total = len(payload.answers)
        correct = 0
        breakdown: dict[str, dict[str, Any]] = {}
        for ans in payload.answers:
            row = conn.execute('SELECT q.correct_choice, o.code, o.title FROM questions q JOIN objectives o ON o.id=q.objective_id WHERE q.id=?', (ans.question_id,)).fetchone()
            if not row:
                continue
            b = breakdown.setdefault(row['code'], {'title': row['title'], 'correct': 0, 'total': 0})
            b['total'] += 1
            if ans.selected_choice.upper() == row['correct_choice']:
                correct += 1; b['correct'] += 1
        score = round((correct / total) * 100, 1) if total else 0
        passed = score >= 70
        cur = conn.execute('INSERT INTO attempts(exam_id,mode,score,passed,correct,total,time_taken_seconds,breakdown_json) VALUES(?,?,?,?,?,?,?,?)',
                           (payload.exam_id, payload.mode, score, int(passed), correct, total, payload.time_taken_seconds, json.dumps(breakdown)))
        return {'id': cur.lastrowid, 'score': score, 'passed': passed, 'correct': correct, 'total': total, 'breakdown': breakdown}

@app.get('/api/attempts')
def attempts(exam_id: Optional[str] = None):
    with connect() as conn:
        if exam_id:
            rows = conn.execute('SELECT * FROM attempts WHERE exam_id=? ORDER BY created_at DESC LIMIT 100', (exam_id,)).fetchall()
        else:
            rows = conn.execute('SELECT * FROM attempts ORDER BY created_at DESC LIMIT 100').fetchall()
        return [row_to_dict(r) for r in rows]

@app.get('/api/admin/review')
def review_queue():
    with connect() as conn:
        rows = conn.execute('''SELECT q.*, o.code objective_code, o.title objective_title FROM questions q JOIN objectives o ON o.id=q.objective_id
            WHERE q.verified=0 ORDER BY q.created_at DESC LIMIT 200''').fetchall()
        return [serialize_question(r, reveal=True) for r in rows]

@app.post('/api/admin/questions')
def add_question(q: ManualQuestion):
    with connect() as conn:
        qid, inserted = insert_question(conn, q, active=1 if q.verified else 0)
        return {'id': qid, 'inserted': inserted}

@app.post('/api/admin/review/{question_id}')
def review(question_id: int, payload: ReviewAction):
    with connect() as conn:
        if payload.action == 'approve':
            conn.execute('UPDATE questions SET verified=1, active=1, updated_at=CURRENT_TIMESTAMP WHERE id=?', (question_id,))
        elif payload.action == 'reject':
            conn.execute('UPDATE questions SET verified=0, active=0, updated_at=CURRENT_TIMESTAMP WHERE id=?', (question_id,))
        elif payload.action == 'edit' and payload.question:
            oid = objective_id(conn, payload.question.exam_id, payload.question.objective_code)
            conn.execute('''UPDATE questions SET exam_id=?, objective_id=?, question_text=?, choices_json=?, correct_choice=?, explanation=?, source=?, verified=?, active=?, fingerprint=?, updated_at=CURRENT_TIMESTAMP WHERE id=?''',
                         (payload.question.exam_id, oid, payload.question.question_text, json.dumps(payload.question.choices), payload.question.correct_choice.upper(), payload.question.explanation, payload.question.source, int(payload.question.verified), int(payload.question.verified), fingerprint(payload.question.exam_id, payload.question.question_text), question_id))
        else:
            raise HTTPException(400, 'action must be approve, reject, or edit')
        return {'id': question_id, 'action': payload.action}

def generate_llm_questions(exam_id: str, count: int = 12):
    key = os.getenv('ANTHROPIC_API_KEY')
    if not key:
        return [], 'ANTHROPIC_API_KEY not set; skipped Claude generation'
    # Conservative API hook. Keeps generated output in review queue. Network/API errors are reported in refresh_runs.
    prompt = f'Generate {count} realistic certification practice questions for {exam_id}. Return JSON array with objective_code, question_text, choices, correct_choice, explanation.'
    try:
        resp = requests.post('https://api.anthropic.com/v1/messages', headers={
            'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'
        }, json={'model': os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-20250514'), 'max_tokens': 5000, 'messages': [{'role': 'user', 'content': prompt}]}, timeout=60)
        resp.raise_for_status()
        text = resp.json()['content'][0]['text']
        data = json.loads(re.search(r'\[.*\]', text, re.S).group(0))
        return data, 'generated via Anthropic'
    except Exception as exc:
        return [], f'Claude generation failed: {exc}'

def scrape_community(exam_id: str):
    # Respectful, low-volume scraper skeleton. Sites change constantly and some block automation. Imported items remain unverified.
    urls = [f'https://www.examtopics.com/exams/microsoft/{exam_id.lower()}/', f'https://learn.microsoft.com/en-us/credentials/certifications/{exam_id.lower()}/']
    results = []
    for url in urls:
        try:
            html = requests.get(url, timeout=15, headers={'User-Agent': 'exam-prep-selfhosted/1.0'}).text
            soup = BeautifulSoup(html, 'html.parser')
            for p in soup.select('p, li')[:20]:
                text = ' '.join(p.get_text(' ', strip=True).split())
                if len(text) > 90 and '?' in text:
                    results.append({'objective_code': '', 'question_text': text[:500], 'choices': ['Review official documentation', 'Disable controls', 'Use unsupported workaround', 'Ignore the finding'], 'correct_choice': 'A', 'explanation': 'Community-sourced item requires admin review before activation.'})
        except Exception:
            continue
    return results

@app.post('/api/admin/refresh')
def refresh(payload: RefreshIn):
    imported = skipped = 0
    messages = []
    with connect() as conn:
        default_obj = conn.execute('SELECT code FROM objectives WHERE exam_id=? ORDER BY code LIMIT 1', (payload.exam_id,)).fetchone()
        if not default_obj:
            raise HTTPException(404, 'Exam not found')
        items = []
        if payload.source in ('all', 'scraper'):
            scraped = scrape_community(payload.exam_id)
            for item in scraped:
                item['objective_code'] = item.get('objective_code') or default_obj['code']
                item['source'] = 'community'
            items.extend(scraped); messages.append(f'scraper found {len(scraped)} candidates')
        if payload.source in ('all', 'llm'):
            generated, msg = generate_llm_questions(payload.exam_id)
            for item in generated:
                item['source'] = 'llm'
            items.extend(generated); messages.append(msg)
        for item in items:
            try:
                q = ManualQuestion(exam_id=payload.exam_id, objective_code=item.get('objective_code') or default_obj['code'], question_text=item['question_text'], choices=item['choices'][:4], correct_choice=item['correct_choice'], explanation=item['explanation'], source=item.get('source','refresh'), verified=False)
                _, inserted = insert_question(conn, q, active=0)
                imported += int(inserted); skipped += int(not inserted)
            except Exception:
                skipped += 1
        status = 'ok' if imported or skipped else 'empty'
        conn.execute('INSERT INTO refresh_runs(exam_id,source,status,imported,skipped,message) VALUES(?,?,?,?,?,?)', (payload.exam_id, payload.source, status, imported, skipped, '; '.join(messages)))
        return {'status': status, 'imported': imported, 'skipped': skipped, 'messages': messages}

@app.get('/api/admin/refresh-runs')
def refresh_runs():
    with connect() as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM refresh_runs ORDER BY created_at DESC LIMIT 50')]

@app.post('/api/admin/import-pdf')
async def import_pdf(exam_id: str, objective_code: str, file: UploadFile = File(...)):
    raw = await file.read()
    import io
    reader = PdfReader(io.BytesIO(raw))
    text = '\n'.join(page.extract_text() or '' for page in reader.pages)
    chunks = [c.strip() for c in re.split(r'\n\s*\n|Question\s+\d+', text) if len(c.strip()) > 80]
    imported = skipped = 0
    with connect() as conn:
        for chunk in chunks[:100]:
            q = ManualQuestion(
                exam_id=exam_id,
                objective_code=objective_code,
                question_text=chunk[:900],
                choices=['Needs admin extraction/review', 'Incorrect placeholder', 'Incorrect placeholder', 'Incorrect placeholder'],
                correct_choice='A',
                explanation='Imported from PDF and requires admin editing before approval.',
                source='pdf',
                verified=False,
            )
            _, inserted = insert_question(conn, q, active=0)
            imported += int(inserted); skipped += int(not inserted)
        conn.execute('INSERT INTO refresh_runs(exam_id,source,status,imported,skipped,message) VALUES(?,?,?,?,?,?)', (exam_id, 'pdf', 'ok', imported, skipped, f'PDF import from {file.filename}'))
    return {'imported': imported, 'skipped': skipped, 'filename': file.filename}

# Static frontend mounted last.
if os.path.isdir('/app/frontend-dist'):
    app.mount('/', StaticFiles(directory='/app/frontend-dist', html=True), name='frontend')
