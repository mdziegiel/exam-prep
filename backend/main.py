import hashlib
import io
import json
import os
import random
import re
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pypdf import PdfReader

from database import DB_PATH, connect, init_db, now_iso, row_to_dict
from seed import seed

app = FastAPI(title='IT Exam Prep API', version='2.0.0')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])

class AnswerIn(BaseModel):
    question_id: int
    selected_choice: str = ''
    elapsed_seconds: int = 0
    flagged: bool = False

class AttemptIn(BaseModel):
    exam_id: str
    mode: str
    answers: list[AnswerIn]
    time_taken_seconds: int
    config: dict[str, Any] = Field(default_factory=dict)

class ManualQuestion(BaseModel):
    exam_id: str
    objective_code: str
    question_text: str
    choices: list[str] = Field(min_length=2)
    correct_choice: str = 'A'
    correct: list[str] = Field(default_factory=list)
    question_type: str = 'single'
    explanation: str
    references: list[dict[str, str]] = Field(default_factory=list)
    exhibit: dict[str, str] = Field(default_factory=dict)
    source: str = 'manual'
    verified: bool = False

class ReviewAction(BaseModel):
    action: str
    question: Optional[ManualQuestion] = None

class RefreshIn(BaseModel):
    exam_id: str
    source: str = 'all'


def ensure_ready():
    seed()

@app.on_event('startup')
def startup():
    ensure_ready()


def safe_json(raw, default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def fingerprint(exam_id: str, text: str) -> str:
    normalized = re.sub(r'\s+', ' ', text).strip().lower()
    return hashlib.sha256(f'{exam_id}:{normalized}'.encode()).hexdigest()


def objective_id(conn, exam_id: str, code: str):
    row = conn.execute('SELECT id FROM objectives WHERE exam_id=? AND code=?', (exam_id, code)).fetchone()
    if not row:
        raise HTTPException(400, f'Unknown objective {code} for {exam_id}')
    return row['id']


def normalize_correct(qtype: str, correct_choice: str, correct: list[str]) -> list[str]:
    if correct:
        return [str(x).upper() for x in correct]
    if correct_choice:
        return [x.strip().upper() for x in correct_choice.split(',') if x.strip()]
    return []


def insert_question(conn, q: ManualQuestion, active: int = 0):
    oid = objective_id(conn, q.exam_id, q.objective_code)
    fp = fingerprint(q.exam_id, q.question_text)
    correct = normalize_correct(q.question_type, q.correct_choice, q.correct)
    refs = q.references or [{'title': 'Official documentation', 'url': 'https://learn.microsoft.com/en-us/credentials/certifications/'}]
    try:
        cur = conn.execute('''INSERT INTO questions(exam_id,objective_id,question_text,choices_json,correct_choice,explanation,source,source_url,verified,active,difficulty,fingerprint,question_type,correct_json,exhibit_json,references_json)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (q.exam_id, oid, q.question_text, json.dumps(q.choices), ','.join(correct), q.explanation, q.source, refs[0].get('url',''), int(q.verified), active, 2, fp, q.question_type, json.dumps(correct), json.dumps(q.exhibit or {}), json.dumps(refs)))
        qid = cur.lastrowid
        conn.execute('INSERT OR IGNORE INTO progress(exam_id,question_id) VALUES(?,?)', (q.exam_id, qid))
        return qid, True
    except sqlite3.IntegrityError:
        return conn.execute('SELECT id FROM questions WHERE fingerprint=?', (fp,)).fetchone()['id'], False


def serialize_question(row, reveal=False, randomize_answers=False):
    d = row_to_dict(row)
    if not d:
        return None
    choices = d.pop('choices')
    items = [{'key': chr(65+i), 'text': choice} for i, choice in enumerate(choices)]
    correct = d.get('correct') or ([d.get('correct_choice')] if d.get('correct_choice') else [])
    if randomize_answers and d.get('question_type') in ('single', 'multiple'):
        pairs = list(zip(items, [c['key'] in correct for c in items]))
        random.shuffle(pairs)
        items = []
        new_correct = []
        for i, (old, is_correct) in enumerate(pairs):
            key = chr(65+i)
            items.append({'key': key, 'text': old['text']})
            if is_correct:
                new_correct.append(key)
        d['correct'] = new_correct
        d['correct_choice'] = ','.join(new_correct)
    d['choices'] = items
    d['required_answers'] = len(d.get('correct') or [d.get('correct_choice')])
    if not reveal:
        d.pop('correct_choice', None)
        d.pop('correct', None)
        d.pop('explanation', None)
        d.pop('references', None)
    return d


def is_correct_answer(question_row, selected: str) -> bool:
    qtype = question_row['question_type'] or 'single'
    correct = safe_json(question_row['correct_json'], None) or [x for x in (question_row['correct_choice'] or '').split(',') if x]
    selected_parts = [x.strip().upper() for x in (selected or '').split(',') if x.strip()]
    if qtype in ('multiple', 'order', 'match'):
        return selected_parts == [str(x).upper() for x in correct]
    return (selected or '').upper() == (correct[0] if correct else question_row['correct_choice']).upper()


def choice_text(row, selected: str):
    choices = safe_json(row['choices_json'], [])
    if not selected:
        return ''
    out = []
    for letter in selected.split(','):
        letter = letter.strip().upper()
        idx = ord(letter[0]) - 65 if letter else -1
        out.append(f'{letter}. {choices[idx]}' if 0 <= idx < len(choices) else letter)
    return '; '.join(out)

@app.get('/api/health')
def health():
    ensure_ready()
    with connect() as conn:
        totals = {r['exam_id']: r['c'] for r in conn.execute('SELECT exam_id, COUNT(*) c FROM questions GROUP BY exam_id')}
    return {'status': 'ok', 'database': str(DB_PATH), 'question_counts': totals}

@app.get('/api/dashboard')
def dashboard():
    with connect() as conn:
        attempts = conn.execute('SELECT * FROM attempts ORDER BY created_at DESC LIMIT 500').fetchall()
        taken = len(attempts)
        avg = round(sum(r['score'] for r in attempts) / taken, 1) if taken else 0
        passed = sum(1 for r in attempts if r['passed'])
        dates = {str(r['created_at'])[:10] for r in attempts}
        streak = 0
        day = datetime.utcnow().date()
        while day.isoformat() in dates:
            streak += 1
            day -= timedelta(days=1)
        missed = conn.execute('''SELECT q.id, q.exam_id, q.question_text, o.code objective_code, o.title objective_title, aa.selected_choice, aa.elapsed_seconds, a.created_at
            FROM attempt_answers aa JOIN attempts a ON a.id=aa.attempt_id JOIN questions q ON q.id=aa.question_id JOIN objectives o ON o.id=q.objective_id
            WHERE aa.is_correct=0 ORDER BY a.created_at DESC LIMIT 10''').fetchall()
        return {'total_exams_taken': taken, 'average_score': avg, 'pass_rate': round((passed/taken)*100,1) if taken else 0, 'study_streak': streak, 'recently_missed': [dict(r) for r in missed]}

@app.get('/api/exams')
def exams():
    with connect() as conn:
        output = []
        for exam in conn.execute('SELECT * FROM exams ORDER BY id'):
            e = dict(exam)
            total = conn.execute('SELECT COUNT(*) c FROM questions WHERE exam_id=? AND active=1 AND verified=1', (e['id'],)).fetchone()['c']
            mastered = conn.execute('SELECT COUNT(*) c FROM progress WHERE exam_id=? AND mastery>=0.8', (e['id'],)).fetchone()['c']
            spent = conn.execute('SELECT COALESCE(SUM(total_time_seconds),0) s FROM progress WHERE exam_id=?', (e['id'],)).fetchone()['s']
            a = conn.execute('SELECT COUNT(*) attempts, MAX(score) best_score, MAX(created_at) last_attempt FROM attempts WHERE exam_id=?', (e['id'],)).fetchone()
            e.update({'question_count': total, 'mastered': mastered, 'percent_mastered': round((mastered / total) * 100, 1) if total else 0, 'time_spent_seconds': spent, 'attempts': a['attempts'], 'best_score': a['best_score'] or 0, 'last_attempt': a['last_attempt']})
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
            AVG(p.mastery) avg_mastery, SUM(p.total_time_seconds) time_spent
            FROM objectives o JOIN questions q ON q.objective_id=o.id LEFT JOIN progress p ON p.question_id=q.id
            WHERE o.exam_id=? AND q.active=1 AND q.verified=1 GROUP BY o.id ORDER BY o.code''', (exam_id,)).fetchall()
        return [dict(r) for r in rows]


def pdf_escape(text: str) -> str:
    return str(text).replace('\\', '\\\\').replace('(', r'\(').replace(')', r'\)')

def wrap_pdf_text(text: str, width: int = 92) -> list[str]:
    words = re.sub(r'\s+', ' ', str(text)).strip().split(' ')
    lines, line = [], ''
    for word in words:
        candidate = f'{line} {word}'.strip()
        if len(candidate) > width and line:
            lines.append(line); line = word
        else:
            line = candidate
    if line: lines.append(line)
    return lines or ['']

def build_question_bank_pdf(exam: sqlite3.Row, questions: list[sqlite3.Row]) -> bytes:
    pages, current, line_limit = [], [f'{exam["id"]} — {exam["name"]}', 'Question Bank', ''], 48
    def add_line(line: str = ''):
        nonlocal current
        if len(current) >= line_limit:
            pages.append(current); current = []
        current.append(line)
    for i, row in enumerate(questions, 1):
        add_line(f'{i}. {row["question_text"]}')
        for idx, choice in enumerate(json.loads(row['choices_json'])):
            for n, part in enumerate(wrap_pdf_text(f'{chr(65+idx)}. {choice}', 88)):
                add_line(('   ' if n else '') + part)
        add_line('')
    if current: pages.append(current)
    answer_page = ['Answer Key', '']
    for i, row in enumerate(questions, 1):
        answer_page.extend(wrap_pdf_text(f'{i}. {row["correct_choice"]}', 96))
        answer_page.extend('   ' + line for line in wrap_pdf_text(f'Explanation: {row["explanation"]}', 92))
        answer_page.append('')
        if len(answer_page) >= line_limit:
            pages.append(answer_page); answer_page = ['Answer Key continued', '']
    if answer_page: pages.append(answer_page)
    objects = []
    def add_obj(data: bytes) -> int:
        objects.append(data); return len(objects)
    font_id = add_obj(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
    page_ids, content_ids = [], []
    for page_no, lines in enumerate(pages, 1):
        ops = ['BT', '/F1 10 Tf', '50 760 Td', '14 TL']
        for line in lines:
            ops += [f'({pdf_escape(line)}) Tj', 'T*']
        ops += ['ET', f'BT /F1 8 Tf 50 24 Td (Page {page_no} of {len(pages)}) Tj ET']
        stream = '\n'.join(ops).encode('latin-1', 'replace')
        content_ids.append(add_obj(b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream'))
    pages_id_guess = len(objects) + len(content_ids) + 1
    for content_id in content_ids:
        page_ids.append(add_obj(f'<< /Type /Page /Parent {pages_id_guess} 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>'.encode()))
    kids = ' '.join(f'{pid} 0 R' for pid in page_ids)
    pages_id = add_obj(f'<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>'.encode())
    if pages_id != pages_id_guess:
        for pid in page_ids:
            objects[pid-1] = objects[pid-1].replace(f'/Parent {pages_id_guess} 0 R'.encode(), f'/Parent {pages_id} 0 R'.encode())
    catalog_id = add_obj(f'<< /Type /Catalog /Pages {pages_id} 0 R >>'.encode())
    out = io.BytesIO(); out.write(b'%PDF-1.4\n'); offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(out.tell()); out.write(f'{i} 0 obj\n'.encode()); out.write(obj); out.write(b'\nendobj\n')
    xref = out.tell(); out.write(f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode())
    for off in offsets[1:]: out.write(f'{off:010d} 00000 n \n'.encode())
    out.write(f'trailer << /Size {len(objects)+1} /Root {catalog_id} 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    return out.getvalue()

@app.get('/api/exams/{exam_id}/printable.pdf')
def printable_pdf(exam_id: str):
    with connect() as conn:
        exam = conn.execute('SELECT * FROM exams WHERE id=?', (exam_id,)).fetchone()
        if not exam: raise HTTPException(404, 'Exam not found')
        rows = conn.execute('''SELECT q.*, o.code objective_code, o.title objective_title FROM questions q JOIN objectives o ON o.id=q.objective_id
            WHERE q.exam_id=? AND q.active=1 AND q.verified=1 ORDER BY o.code, q.id''', (exam_id,)).fetchall()
        pdf = build_question_bank_pdf(exam, rows)
    return StreamingResponse(io.BytesIO(pdf), media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename="{exam_id}-question-bank.pdf"'})

@app.get('/api/exams/{exam_id}/queue')
def queue(exam_id: str, limit: int = Query(10, ge=1, le=500), mode: str = 'practice', ids: Optional[str] = None, objectives: Optional[str] = None, objective: Optional[str] = None, wrong: bool = False, missed_last: int = 0, unseen_last: int = 0, randomize_questions: bool = False, randomize_answers: bool = False):
    with connect() as conn:
        if ids:
            wanted = [int(x) for x in ids.split(',') if x.strip().isdigit()]
            if not wanted: return []
            placeholders = ','.join('?' for _ in wanted)
            rows = conn.execute(f'''SELECT q.*, o.code objective_code, o.title objective_title, p.flagged, p.mastery FROM questions q JOIN objectives o ON o.id=q.objective_id JOIN progress p ON p.question_id=q.id
                WHERE q.exam_id=? AND q.active=1 AND q.verified=1 AND q.id IN ({placeholders})''', [exam_id, *wanted]).fetchall()
            order = {qid: i for i, qid in enumerate(wanted)}
            rows = sorted(rows, key=lambda r: order.get(r['id'], 9999))
        else:
            filters = ['q.exam_id=?', 'q.active=1', 'q.verified=1']; params: list[Any] = [exam_id]
            obj_codes = [x for x in (objectives or objective or '').split(',') if x]
            if obj_codes:
                filters.append('o.code IN (%s)' % ','.join('?' for _ in obj_codes)); params.extend(obj_codes)
            if wrong:
                filters.append('p.wrong_count > 0')
            if missed_last:
                filters.append('q.id IN (SELECT aa.question_id FROM attempt_answers aa JOIN attempts a ON a.id=aa.attempt_id WHERE a.exam_id=? AND aa.is_correct=0 ORDER BY a.created_at DESC LIMIT ?)')
                params.extend([exam_id, missed_last * 500])
            if unseen_last:
                filters.append('q.id NOT IN (SELECT aa.question_id FROM attempt_answers aa JOIN attempts a ON a.id=aa.attempt_id WHERE a.exam_id=? ORDER BY a.created_at DESC LIMIT ?)')
                params.extend([exam_id, unseen_last * 500])
            order = 'RANDOM()' if randomize_questions or mode in ('timed','certification','quick') else 'datetime(p.next_due) ASC, p.mastery ASC, q.difficulty DESC'
            params.append(limit)
            rows = conn.execute(f'''SELECT q.*, o.code objective_code, o.title objective_title, p.flagged, p.mastery FROM questions q JOIN objectives o ON o.id=q.objective_id JOIN progress p ON p.question_id=q.id
                WHERE {' AND '.join(filters)} ORDER BY {order} LIMIT ?''', params).fetchall()
        return [serialize_question(r, randomize_answers=randomize_answers) for r in rows]

@app.post('/api/answer')
def answer(payload: AnswerIn):
    selected = payload.selected_choice.upper()
    with connect() as conn:
        row = conn.execute('''SELECT q.*, o.code objective_code, o.title objective_title, p.streak, p.correct_count, p.wrong_count, p.mastery FROM questions q JOIN objectives o ON o.id=q.objective_id JOIN progress p ON p.question_id=q.id WHERE q.id=?''', (payload.question_id,)).fetchone()
        if not row: raise HTTPException(404, 'Question not found')
        correct = is_correct_answer(row, selected)
        streak = (row['streak'] + 1) if correct else 0
        mastery = max(0, min(1.0, (row['mastery'] or 0) + (0.18 if correct else -0.12)))
        delay_days = [0, 1, 3, 7, 14, 30][min(streak, 5)] if correct else 0
        due = (datetime.utcnow() + timedelta(days=delay_days, minutes=10 if not correct else 0)).isoformat(timespec='seconds') + 'Z'
        conn.execute('''UPDATE progress SET correct_count=correct_count+?, wrong_count=wrong_count+?, streak=?, mastery=?, next_due=?, last_seen=?, total_time_seconds=total_time_seconds+?, flagged=? WHERE question_id=?''', (int(correct), int(not correct), streak, mastery, due, now_iso(), payload.elapsed_seconds, int(payload.flagged), payload.question_id))
        q = serialize_question(row, reveal=True)
        q.update({'selected_choice': selected, 'selected_text': choice_text(row, selected), 'is_correct': correct, 'next_due': due, 'mastery': round(mastery, 2)})
        return q

@app.post('/api/flag/{question_id}')
def flag(question_id: int):
    with connect() as conn:
        row = conn.execute('SELECT flagged FROM progress WHERE question_id=?', (question_id,)).fetchone()
        if not row: raise HTTPException(404, 'Question not found')
        flagged = 0 if row['flagged'] else 1
        conn.execute('UPDATE progress SET flagged=? WHERE question_id=?', (flagged, question_id))
        return {'question_id': question_id, 'flagged': bool(flagged)}

@app.post('/api/attempts')
def save_attempt(payload: AttemptIn):
    with connect() as conn:
        exam = conn.execute('SELECT id,name,passing_score FROM exams WHERE id=?', (payload.exam_id,)).fetchone()
        if not exam: raise HTTPException(404, 'Exam not found')
        total, correct_count, breakdown, review = len(payload.answers), 0, {}, []
        for ans in payload.answers:
            row = conn.execute('''SELECT q.*, o.code, o.title FROM questions q JOIN objectives o ON o.id=q.objective_id WHERE q.id=?''', (ans.question_id,)).fetchone()
            if not row: continue
            ok = is_correct_answer(row, ans.selected_choice)
            b = breakdown.setdefault(row['code'], {'title': row['title'], 'correct': 0, 'total': 0})
            b['total'] += 1
            if ok: correct_count += 1; b['correct'] += 1
            review.append({'id': row['id'], 'question_text': row['question_text'], 'objective_code': row['code'], 'objective_title': row['title'], 'question_type': row['question_type'], 'choices': [{'key': chr(65+i), 'text': c} for i,c in enumerate(safe_json(row['choices_json'], []))], 'selected_choice': ans.selected_choice, 'selected_text': choice_text(row, ans.selected_choice), 'correct_choice': row['correct_choice'], 'correct': safe_json(row['correct_json'], []), 'correct_text': choice_text(row, row['correct_choice']), 'is_correct': ok, 'flagged': ans.flagged, 'explanation': row['explanation'], 'references': safe_json(row['references_json'], []), 'exhibit': safe_json(row['exhibit_json'], {})})
            p = conn.execute('SELECT streak, mastery FROM progress WHERE question_id=?', (ans.question_id,)).fetchone()
            streak = ((p['streak'] if p else 0) + 1) if ok else 0
            mastery = max(0, min(1.0, ((p['mastery'] if p else 0) or 0) + (0.18 if ok else -0.12)))
            conn.execute('''UPDATE progress SET correct_count=correct_count+?, wrong_count=wrong_count+?, streak=?, mastery=?, last_seen=?, total_time_seconds=total_time_seconds+?, flagged=? WHERE question_id=?''', (int(ok), int(not ok), streak, mastery, now_iso(), ans.elapsed_seconds, int(ans.flagged), ans.question_id))
        score = round((correct_count / total) * 100, 1) if total else 0
        passed = score >= exam['passing_score']
        cur = conn.execute('''INSERT INTO attempts(exam_id,mode,score,passed,correct,total,time_taken_seconds,breakdown_json,answers_json,config_json) VALUES(?,?,?,?,?,?,?,?,?,?)''', (payload.exam_id, payload.mode, score, int(passed), correct_count, total, payload.time_taken_seconds, json.dumps(breakdown), json.dumps(review), json.dumps(payload.config)))
        aid = cur.lastrowid
        for r, ans in zip(review, payload.answers):
            conn.execute('INSERT INTO attempt_answers(attempt_id,question_id,selected_choice,is_correct,elapsed_seconds,flagged) VALUES(?,?,?,?,?,?)', (aid, r['id'], ans.selected_choice, int(r['is_correct']), ans.elapsed_seconds, int(ans.flagged)))
        return {'id': aid, 'exam_id': payload.exam_id, 'exam_name': exam['name'], 'mode': payload.mode, 'score': score, 'passing_score': exam['passing_score'], 'passed': passed, 'correct': correct_count, 'total': total, 'time_taken_seconds': payload.time_taken_seconds, 'breakdown': breakdown, 'review_questions': review, 'wrong_questions': [r for r in review if not r['is_correct']], 'created_at': now_iso()}

@app.get('/api/attempts')
def attempts(exam_id: Optional[str] = None):
    with connect() as conn:
        rows = conn.execute('SELECT * FROM attempts WHERE (? IS NULL OR exam_id=?) ORDER BY created_at DESC LIMIT 100', (exam_id, exam_id)).fetchall()
        return [row_to_dict(r) for r in rows]

@app.get('/api/attempts/{attempt_id}')
def attempt_detail(attempt_id: int):
    with connect() as conn:
        row = conn.execute('SELECT * FROM attempts WHERE id=?', (attempt_id,)).fetchone()
        if not row: raise HTTPException(404, 'Attempt not found')
        return row_to_dict(row)

@app.get('/api/admin/review')
def review_queue():
    with connect() as conn:
        rows = conn.execute('''SELECT q.*, o.code objective_code, o.title objective_title FROM questions q JOIN objectives o ON o.id=q.objective_id WHERE q.verified=0 ORDER BY q.created_at DESC LIMIT 200''').fetchall()
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
            correct = normalize_correct(payload.question.question_type, payload.question.correct_choice, payload.question.correct)
            refs = payload.question.references or [{'title': 'Official documentation', 'url': 'https://learn.microsoft.com/en-us/credentials/certifications/'}]
            conn.execute('''UPDATE questions SET exam_id=?, objective_id=?, question_text=?, choices_json=?, correct_choice=?, explanation=?, source=?, source_url=?, verified=?, active=?, fingerprint=?, question_type=?, correct_json=?, exhibit_json=?, references_json=?, updated_at=CURRENT_TIMESTAMP WHERE id=?''', (payload.question.exam_id, oid, payload.question.question_text, json.dumps(payload.question.choices), ','.join(correct), payload.question.explanation, payload.question.source, refs[0].get('url',''), int(payload.question.verified), int(payload.question.verified), fingerprint(payload.question.exam_id, payload.question.question_text), payload.question.question_type, json.dumps(correct), json.dumps(payload.question.exhibit or {}), json.dumps(refs), question_id))
        else:
            raise HTTPException(400, 'action must be approve, reject, or edit')
        return {'id': question_id, 'action': payload.action}


def generate_llm_questions(exam_id: str, count: int = 12):
    key = os.getenv('ANTHROPIC_API_KEY')
    if not key:
        return [], 'ANTHROPIC_API_KEY not set; skipped Claude generation'
    prompt = f'''Generate {count} realistic certification practice questions for {exam_id}. Return only a JSON array. Each object: objective_code, question_type(single|multiple), question_text, choices, correct (array of letters), explanation (detailed why right and why wrong), references (array title/url). Use current official objectives.'''
    try:
        resp = requests.post('https://api.anthropic.com/v1/messages', headers={'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'}, json={'model': os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-20250514'), 'max_tokens': 7000, 'messages': [{'role': 'user', 'content': prompt}]}, timeout=60)
        resp.raise_for_status(); text = resp.json()['content'][0]['text']
        data = json.loads(re.search(r'\[.*\]', text, re.S).group(0))
        return data, 'generated via Anthropic'
    except Exception as exc:
        return [], f'Claude generation failed: {exc}'

def scrape_community(exam_id: str):
    urls = [f'https://learn.microsoft.com/en-us/credentials/certifications/{exam_id.lower()}/']
    results = []
    for url in urls:
        try:
            html = requests.get(url, timeout=15, headers={'User-Agent': 'exam-prep-selfhosted/2.0'}).text
            soup = BeautifulSoup(html, 'html.parser')
            for p in soup.select('p, li')[:20]:
                text = ' '.join(p.get_text(' ', strip=True).split())
                if len(text) > 90 and '?' in text:
                    results.append({'objective_code': '', 'question_text': text[:500], 'choices': ['Review official documentation', 'Disable controls', 'Use unsupported workaround', 'Ignore the finding'], 'correct': ['A'], 'question_type': 'single', 'explanation': 'Official documentation review is correct because certification questions expect supported controls. The alternatives either weaken security, use unsupported workarounds, or ignore the requirement.', 'references': [{'title':'Microsoft Learn','url':url}]})
        except Exception:
            continue
    return results

@app.post('/api/admin/refresh')
def refresh(payload: RefreshIn):
    imported = skipped = 0; messages = []
    with connect() as conn:
        default_obj = conn.execute('SELECT code FROM objectives WHERE exam_id=? ORDER BY code LIMIT 1', (payload.exam_id,)).fetchone()
        if not default_obj: raise HTTPException(404, 'Exam not found')
        items = []
        if payload.source in ('all', 'scraper'):
            scraped = scrape_community(payload.exam_id)
            for item in scraped:
                item['objective_code'] = item.get('objective_code') or default_obj['code']; item['source'] = 'community'
            items.extend(scraped); messages.append(f'scraper found {len(scraped)} candidates')
        if payload.source in ('all', 'llm'):
            generated, msg = generate_llm_questions(payload.exam_id)
            for item in generated: item['source'] = 'llm'
            items.extend(generated); messages.append(msg)
        for item in items:
            try:
                correct = item.get('correct') or [item.get('correct_choice','A')]
                q = ManualQuestion(exam_id=payload.exam_id, objective_code=item.get('objective_code') or default_obj['code'], question_text=item['question_text'], choices=item['choices'], correct_choice=','.join(correct), correct=correct, question_type=item.get('question_type','single'), explanation=item['explanation'], references=item.get('references') or [], source=item.get('source','refresh'), verified=False)
                _, inserted = insert_question(conn, q, active=0); imported += int(inserted); skipped += int(not inserted)
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
    raw = await file.read(); reader = PdfReader(io.BytesIO(raw)); text = '\n'.join(page.extract_text() or '' for page in reader.pages)
    chunks = [c.strip() for c in re.split(r'\n\s*\n|Question\s+\d+', text) if len(c.strip()) > 80]
    imported = skipped = 0
    with connect() as conn:
        for chunk in chunks[:100]:
            q = ManualQuestion(exam_id=exam_id, objective_code=objective_code, question_text=chunk[:900], choices=['Needs admin extraction/review', 'Incorrect placeholder', 'Incorrect placeholder', 'Incorrect placeholder'], correct_choice='A', correct=['A'], explanation='Imported from PDF and requires admin editing before approval. The correct answer placeholder must be replaced before activation.', references=[{'title':'Imported source PDF','url':''}], source='pdf', verified=False)
            _, inserted = insert_question(conn, q, active=0); imported += int(inserted); skipped += int(not inserted)
        conn.execute('INSERT INTO refresh_runs(exam_id,source,status,imported,skipped,message) VALUES(?,?,?,?,?,?)', (exam_id, 'pdf', 'ok', imported, skipped, f'PDF import from {file.filename}'))
    return {'imported': imported, 'skipped': skipped, 'filename': file.filename}

if os.path.isdir('/app/frontend-dist'):
    app.mount('/', StaticFiles(directory='/app/frontend-dist', html=True), name='frontend')
