import hashlib
import json
import os
import random
import re
import shutil
import sqlite3
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import requests

DB = os.getenv('DATABASE_PATH', '/data/exam-prep.sqlite')
EXAM = 'MD-102'
OBJ_URL = 'https://learn.microsoft.com/en-us/credentials/certifications/resources/study-guides/md-102'
CERT_URL = 'https://learn.microsoft.com/en-us/credentials/certifications/exams/md-102/'
MODEL = os.getenv('ANTHROPIC_MODEL', 'claude-haiku-4-5-20251001')
TARGET_TOTAL = int(os.getenv('MD102_TARGET_TOTAL', '320'))

# Official Microsoft Learn MD-102 study guide, skills measured as of April 28, 2026.
# Chosen counts are inside the official published ranges and sum to 320.
TARGETS = {
    '1.0': {
        'title': 'Prepare infrastructure for devices',
        'weight': 28,
        'target': 88,
        'range': '25-30%',
        'objectives': [
            'Add devices to Microsoft Entra ID: choose device join type, join devices, register devices, plan and implement groups for devices.',
            'Enroll devices to Microsoft Intune: configure enrollment settings; automatic enrollment for Windows; bulk enrollment for iOS/iPadOS and Android; Android enrollment profiles including fully managed, dedicated, corporate-owned, and work profile.',
            'Implement identity and compliance: manage roles in Intune; compliance policies for all supported platforms; Conditional Access policies requiring compliance; Windows Hello for Business; Windows LAPS; local group membership on Windows devices by using Intune.',
        ],
        'topics': [
            'Microsoft Entra join versus registration', 'dynamic device group planning', 'Intune automatic enrollment', 'Android Enterprise fully managed enrollment',
            'Android dedicated device enrollment', 'iOS/iPadOS bulk enrollment', 'Intune RBAC role scope tags', 'cross-platform compliance policies',
            'Conditional Access requiring compliant devices', 'Windows Hello for Business deployment', 'Windows LAPS policy', 'local administrators group management',
            'enrollment restrictions', 'corporate device identifiers', 'device compliance grace periods', 'user versus device assignment scope',
        ],
    },
    '2.0': {
        'title': 'Manage and maintain devices',
        'weight': 33,
        'target': 104,
        'range': '30-35%',
        'objectives': [
            'Deploy and upgrade Windows clients by using cloud-based tools: choose between Windows Autopilot and provisioning packages; choose Autopilot deployment mode; apply device name template; implement Autopilot; create Enrollment Status Page; provisioning packages; Windows 11 upgrades; Windows 365 Cloud PC deployment.',
            'Plan and implement device configuration profiles for Windows, Android, iOS/iPadOS, macOS, and Windows 11 Enterprise multi-session devices; import ADMX files; target a profile by using filters.',
            'Implement Intune Suite add-on capabilities: Endpoint Privilege Management; Enterprise App Catalog; Intune Advanced Analytics; Remote Help; Microsoft Cloud PKI use cases; Microsoft Tunnel for Mobile Application Management.',
            'Perform remote actions on devices: sync, restart, retire, wipe, bulk remote actions, update Defender Antivirus security intelligence, rotate BitLocker recovery keys, run device query by using KQL.',
        ],
        'topics': [
            'Windows Autopilot user-driven deployment', 'Autopilot self-deploying mode', 'Autopilot pre-provisioning', 'Enrollment Status Page blocking apps',
            'Windows 11 feature update deployment', 'provisioning package selection', 'Windows 365 Cloud PC provisioning policy', 'configuration profile assignment filters',
            'ADMX-backed policy import', 'Windows 11 Enterprise multi-session configuration', 'macOS device configuration profile', 'iOS/iPadOS configuration profile',
            'Android device configuration profile', 'Endpoint Privilege Management elevation rule', 'Enterprise App Catalog app management', 'Intune Advanced Analytics anomaly',
            'Remote Help role and session', 'Cloud PKI certificate deployment use case', 'Microsoft Tunnel for MAM', 'device wipe versus retire',
            'bulk remote action', 'BitLocker recovery key rotation', 'Defender security intelligence update', 'KQL device query',
        ],
    },
    '3.0': {
        'title': 'Manage applications',
        'weight': 20,
        'target': 64,
        'range': '15-20%',
        'objectives': [
            'Deploy and update apps: prepare applications for deployment by using Intune; deploy apps using Intune; deploy Microsoft 365 Apps; configure Office app policies; deploy Microsoft 365 Apps during Autopilot with ODT or OCT; manage Microsoft 365 Apps admin center; deploy platform-specific store apps.',
            'Plan and implement app protection and app configuration policies: app protection policies; Conditional Access policies for app protection policies; app configuration policies for managed apps and managed devices.',
        ],
        'topics': [
            'Win32 app packaging and detection rules', 'Microsoft 365 Apps deployment in Intune', 'Office policy configuration', 'Office Deployment Tool with Autopilot',
            'Office Customization Tool XML', 'Microsoft 365 Apps admin center update channel', 'Microsoft Store app deployment', 'Apple App Store deployment',
            'Managed Google Play app deployment', 'app protection policy for unmanaged devices', 'MAM Conditional Access requirement', 'app configuration policy for Outlook',
            'required versus available app assignment', 'supersedence for app update', 'app install status troubleshooting', 'managed app configuration values',
        ],
    },
    '4.0': {
        'title': 'Protect devices',
        'weight': 20,
        'target': 64,
        'range': '15-20%',
        'objectives': [
            'Configure endpoint security: create antivirus policies; disk encryption policies; firewall policies; Attack surface reduction policies; security baselines; integrate Intune with Microsoft Defender for Endpoint; onboard devices into Defender for Endpoint.',
            'Manage device updates by using Intune: plan for updates; create and manage update rings; create and manage update policies for Intune including iOS/iPadOS and macOS; manage Android updates using configuration profiles or FOTA deployments; configure Windows Delivery Optimization; monitor updates.',
        ],
        'topics': [
            'Intune antivirus policy', 'BitLocker disk encryption policy', 'Windows Firewall endpoint security policy', 'Attack surface reduction rule',
            'security baseline assignment', 'Microsoft Defender for Endpoint connector', 'Defender for Endpoint onboarding profile', 'tamper protection policy',
            'Windows Update ring deadline', 'Windows feature update policy', 'expedited quality update', 'driver update policy',
            'iOS/iPadOS update policy', 'macOS update policy', 'Android FOTA deployment', 'Delivery Optimization configuration',
            'update compliance monitoring', 'Defender device risk signal in compliance',
        ],
    },
}

DOMAIN_KEYWORDS = {
    '1.0': ['entra', 'azure ad', 'join', 'register', 'enrollment', 'enroll', 'compliance', 'conditional access', 'hello', 'laps', 'local administrator', 'rbac', 'scope tag', 'android enterprise'],
    '2.0': ['autopilot', 'provisioning', 'configuration profile', 'admx', 'windows 365', 'cloud pc', 'remote help', 'privilege', 'analytics', 'tunnel', 'wipe', 'retire', 'sync', 'bitlocker recovery', 'kql'],
    '3.0': ['app', 'office', 'microsoft 365 apps', 'win32', 'store', 'protection policy', 'configuration policy', 'mam', 'odt', 'oct', 'deployment tool'],
    '4.0': ['security', 'defender', 'antivirus', 'firewall', 'encryption', 'attack surface', 'baseline', 'update ring', 'feature update', 'quality update', 'delivery optimization', 'fota'],
}

SCENARIO_STYLES = [
    'troubleshooting a production tenant', 'planning a zero-touch rollout', 'remediating an audit finding', 'reducing help desk escalations',
    'supporting a hybrid workforce', 'migrating from legacy management', 'hardening endpoint security', 'standardizing cross-platform management',
]


def clean(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def fp(text):
    return hashlib.sha256(f'{EXAM}:{text}'.encode()).hexdigest()


def get_token():
    token = os.getenv('ANTHROPIC_TOKEN', '').strip()
    if token:
        return token
    token_file = os.getenv('ANTHROPIC_TOKEN_FILE', '/tmp/anthropic_token')
    if os.path.exists(token_file):
        return Path(token_file).read_text().strip()
    return ''


def auth_headers(token):
    return {
        'authorization': 'Bearer ' + token,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
    }


def token_fingerprint(token):
    return {
        'prefix': token[:10],
        'suffix': token[-6:],
        'length': len(token),
        'sha256_12': hashlib.sha256(token.encode()).hexdigest()[:12],
    }


def preflight(token):
    payload = {'model': MODEL, 'max_tokens': 32, 'messages': [{'role': 'user', 'content': 'Return only: ok'}]}
    resp = requests.post('https://api.anthropic.com/v1/messages', headers=auth_headers(token), json=payload, timeout=30)
    return resp.status_code, resp.text[:500]


def classify_question(text, choices):
    hay = (text + ' ' + ' '.join(choices)).lower()
    scores = {code: sum(1 for kw in kws if kw in hay) for code, kws in DOMAIN_KEYWORDS.items()}
    best = max(scores, key=lambda k: scores[k])
    if scores[best] > 0:
        return best
    return '2.0'


def valid_existing(row):
    try:
        choices = json.loads(row['choices_json'])
    except Exception:
        return None
    correct = [x.strip().upper() for x in (row['correct_choice'] or '').split(',') if x.strip()]
    explanation = clean(row['explanation'])
    if len(choices) != 4:
        return None
    if len(correct) != 1 or correct[0] not in list('ABCD'):
        return None
    if row['question_type'] != 'single':
        return None
    if len(explanation) <= 120:
        return None
    text = clean(row['question_text'])
    if not text:
        return None
    code = classify_question(text, [clean(c) for c in choices])
    refs = row['references_json'] or ''
    try:
        refs_obj = json.loads(refs) if refs else []
    except Exception:
        refs_obj = []
    if not refs_obj:
        refs_obj = [{'title': 'Microsoft Learn MD-102 study guide', 'url': OBJ_URL}]
    return {
        'objective_code': code,
        'question_text': text,
        'choices': [clean(c) for c in choices],
        'correct': correct,
        'question_type': 'single',
        'explanation': explanation,
        'references': refs_obj,
        'source': row['source'],
        'source_url': row['source_url'] or OBJ_URL,
        'difficulty': row['difficulty'] or 2,
    }


def domain_excerpt(code):
    d = TARGETS[code]
    return '\n'.join([f"{code} {d['title']} ({d['range']})"] + [f'- {x}' for x in d['objectives']])


def parse_json_array(text):
    text = text.strip()
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text, re.I)
    if m:
        text = m.group(1).strip()
    else:
        m = re.search(r'\[[\s\S]*\]', text)
        if m:
            text = m.group(0)
    return json.loads(text)


def validate_generated_item(q, code):
    if not isinstance(q, dict):
        return None
    text = clean(q.get('question_text'))
    choices = [clean(c) for c in q.get('choices', [])]
    correct = q.get('correct') or q.get('correct_answers') or []
    if isinstance(correct, str):
        correct = [correct]
    correct = [str(c).strip().upper() for c in correct]
    explanation = clean(q.get('explanation'))
    if len(choices) != 4:
        return None
    if len(correct) != 1 or correct[0] not in list('ABCD'):
        return None
    if len(explanation) <= 120:
        return None
    if len(text) < 50:
        return None
    if len(set(c.lower() for c in choices)) != 4:
        return None
    if 'all of the above' in ' '.join(choices).lower() or 'none of the above' in ' '.join(choices).lower():
        return None
    return {
        'objective_code': code,
        'question_text': text,
        'choices': choices,
        'correct': correct,
        'question_type': 'single',
        'explanation': explanation,
        'references': [{'title': 'Microsoft Learn MD-102 study guide', 'url': OBJ_URL}, {'title': 'Microsoft MD-102 exam page', 'url': CERT_URL}],
        'source': 'claude-generated',
        'source_url': OBJ_URL,
        'difficulty': int(q.get('difficulty') or random.choice([2, 2, 3])),
    }


def generate_questions(token, code, count, existing_fps):
    if count <= 0:
        return []
    out = []
    attempts = 0
    topic_offset = random.randrange(1000)
    while len(out) < count and attempts < 20:
        attempts += 1
        batch = min(8, count - len(out))
        d = TARGETS[code]
        topics = d['topics']
        selected_topics = [topics[(topic_offset + len(out) + i) % len(topics)] for i in range(max(batch, 8))]
        style = SCENARIO_STYLES[(attempts + len(out)) % len(SCENARIO_STYLES)]
        prompt = f"""Generate {batch} ORIGINAL Microsoft MD-102 practice questions for domain {code} {d['title']}.
Use only the official Microsoft Learn objective scope below. Do not reproduce real exam questions, dumps, or copyrighted items.

Required style:
- Authentic Microsoft role-based exam style for an Endpoint Administrator using Microsoft Intune, Microsoft Entra ID, Windows, Microsoft 365 Apps, and Defender for Endpoint.
- Scenario-based, practical, and specific. Avoid generic definitions.
- Exactly 4 answer choices per question.
- Exactly one correct answer, represented as [\"A\"], [\"B\"], [\"C\"], or [\"D\"].
- Explanation must be detailed, over 120 characters, explain why the correct choice is right and why the distractors are wrong.
- No exhibits, no select-two, no ordering, no matching, no all/none-of-the-above.
- Vary the correct answer position.
- Use this scenario flavor where possible: {style}.
- Include these topic focuses without making the questions templated: {', '.join(selected_topics)}.

Return ONLY a valid JSON array. Schema per item:
{{"objective_code":"{code}","question_text":"...","choices":["...","...","...","..."],"correct":["A"],"question_type":"single","difficulty":2,"explanation":"..."}}

Official objectives excerpt:
{domain_excerpt(code)}"""
        payload = {
            'model': MODEL,
            'max_tokens': 9000,
            'temperature': 0.65,
            'messages': [{'role': 'user', 'content': prompt}],
        }
        resp = requests.post('https://api.anthropic.com/v1/messages', headers=auth_headers(token), json=payload, timeout=120)
        if resp.status_code >= 400:
            raise RuntimeError(f'Claude API {resp.status_code}: {resp.text[:500]}')
        text = '\n'.join(c.get('text', '') for c in resp.json().get('content', []) if c.get('type') == 'text')
        try:
            data = parse_json_array(text)
        except Exception as exc:
            print(json.dumps({'warning': 'json_parse_failed', 'domain': code, 'attempt': attempts, 'error': str(exc), 'text_prefix': text[:200]}), flush=True)
            time.sleep(2)
            continue
        added = 0
        for raw in data:
            q = validate_generated_item(raw, code)
            if not q:
                continue
            f = fp(q['question_text'])
            if f in existing_fps:
                continue
            existing_fps.add(f)
            out.append(q)
            added += 1
            if len(out) >= count:
                break
        print(json.dumps({'domain': code, 'attempt': attempts, 'requested_batch': batch, 'accepted': added, 'domain_total': len(out), 'domain_need': count}), flush=True)
        time.sleep(1.5)
    if len(out) < count:
        raise RuntimeError(f'Generated only {len(out)} of {count} required for {code}')
    return out[:count]


def load_preserved(conn):
    rows = conn.execute('select * from questions where exam_id=? and active=1 and verified=1 order by id', (EXAM,)).fetchall()
    preserved = []
    rejected = 0
    seen = set()
    for row in rows:
        q = valid_existing(row)
        if not q:
            rejected += 1
            continue
        f = fp(q['question_text'])
        if f in seen:
            rejected += 1
            continue
        seen.add(f)
        preserved.append(q)
    return preserved, rejected


def insert_pool(conn, questions):
    old_ids = [r['id'] for r in conn.execute('select id from questions where exam_id=?', (EXAM,))]
    if old_ids:
        for start in range(0, len(old_ids), 500):
            chunk = old_ids[start:start + 500]
            ph = ','.join('?' for _ in chunk)
            conn.execute(f'delete from progress where question_id in ({ph})', chunk)
            conn.execute(f'delete from attempt_answers where question_id in ({ph})', chunk)
    conn.execute('delete from attempts where exam_id=?', (EXAM,))
    conn.execute('delete from questions where exam_id=?', (EXAM,))
    conn.execute('delete from objectives where exam_id=?', (EXAM,))
    conn.execute('insert or ignore into exams(id,name,vendor,duration_minutes,passing_score,description) values(?,?,?,?,?,?)', (
        EXAM, 'Microsoft Endpoint Administrator', 'Microsoft', 100, 70,
        'Endpoint administration with Microsoft Intune, Microsoft Entra ID, Windows, Microsoft 365 Apps, and endpoint security aligned to the current MD-102 objectives.',
    ))
    conn.execute('update exams set name=?, vendor=?, duration_minutes=?, passing_score=?, description=? where id=?', (
        'Microsoft Endpoint Administrator', 'Microsoft', 100, 70,
        'Endpoint administration with Microsoft Intune, Microsoft Entra ID, Windows, Microsoft 365 Apps, and endpoint security aligned to the current MD-102 objectives.', EXAM,
    ))
    obj_ids = {}
    for code, d in TARGETS.items():
        conn.execute('insert into objectives(exam_id,code,title,weight) values(?,?,?,?)', (EXAM, code, d['title'], d['weight']))
        obj_ids[code] = conn.execute('select last_insert_rowid() id').fetchone()['id']
    for q in questions:
        code = q['objective_code']
        choices = q['choices'][:4]
        correct = [str(x).upper() for x in q['correct'] if str(x).upper() in list('ABCD')]
        if len(choices) != 4 or len(correct) != 1 or len(clean(q['explanation'])) <= 120:
            continue
        text = clean(q['question_text'])
        try:
            cur = conn.execute('''insert into questions(exam_id,objective_id,question_text,choices_json,correct_choice,explanation,source,source_url,verified,active,difficulty,fingerprint,question_type,correct_json,exhibit_json,references_json)
                values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
                EXAM, obj_ids[code], text, json.dumps(choices), correct[0], clean(q['explanation']), q['source'], q.get('source_url', OBJ_URL), 1, 1,
                q.get('difficulty', 2), fp(text), 'single', json.dumps(correct), json.dumps({}), json.dumps(q.get('references') or [{'title': 'Microsoft Learn MD-102 study guide', 'url': OBJ_URL}]),
            ))
        except sqlite3.IntegrityError:
            continue
        conn.execute('insert or ignore into progress(exam_id,question_id) values(?,?)', (EXAM, cur.lastrowid))


def final_report(conn):
    total = conn.execute('select count(*) c from questions where exam_id=? and active=1 and verified=1', (EXAM,)).fetchone()['c']
    sources = [dict(r) for r in conn.execute('select source,count(*) count from questions where exam_id=? and active=1 and verified=1 group by source order by count desc, source', (EXAM,))]
    domains = [dict(r) for r in conn.execute('''select o.code,o.title,o.weight,count(q.id) count
        from objectives o left join questions q on q.objective_id=o.id and q.active=1 and q.verified=1
        where o.exam_id=? group by o.id order by o.code''', (EXAM,))]
    invalid = []
    for r in conn.execute('select id,choices_json,correct_choice,explanation,question_type from questions where exam_id=? and active=1 and verified=1', (EXAM,)):
        try:
            choices = json.loads(r['choices_json'])
        except Exception:
            choices = []
        corr = [x.strip() for x in (r['correct_choice'] or '').split(',') if x.strip()]
        if len(choices) != 4 or len(corr) != 1 or corr[0] not in list('ABCD') or len(r['explanation'] or '') <= 120 or r['question_type'] != 'single':
            invalid.append(r['id'])
    return {'total': total, 'sources': sources, 'domains': domains, 'invalid_count': len(invalid), 'invalid_ids_sample': invalid[:10]}


def main():
    random.seed()
    token = get_token()
    if not token:
        raise SystemExit('ANTHROPIC_TOKEN or ANTHROPIC_TOKEN_FILE is required. Refusing to use stale x-api-key path.')
    print(json.dumps({
        'provider_audit': {
            'endpoint': 'https://api.anthropic.com/v1/messages',
            'auth_header_type': 'Authorization: Bearer',
            'token_fingerprint': token_fingerprint(token),
            'model': MODEL,
        }
    }, indent=2), flush=True)
    status, body = preflight(token)
    print(json.dumps({'preflight_status': status, 'preflight_body_prefix': body[:240]}, indent=2), flush=True)
    if status >= 400:
        raise SystemExit('Preflight failed. Database was not changed.')

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    before = final_report(con)
    preserved, rejected = load_preserved(con)
    preserved_by_domain = Counter(q['objective_code'] for q in preserved)
    print(json.dumps({'before': before, 'preserved_valid_existing': len(preserved), 'rejected_existing_invalid_or_duplicate': rejected, 'preserved_by_domain': preserved_by_domain}, indent=2), flush=True)

    selected = list(preserved)
    existing_fps = {fp(q['question_text']) for q in selected}
    generation_need = {}
    for code, d in TARGETS.items():
        generation_need[code] = max(0, d['target'] - preserved_by_domain.get(code, 0))
    print(json.dumps({'target_counts': {k: v['target'] for k, v in TARGETS.items()}, 'generation_need': generation_need}, indent=2), flush=True)

    for code in TARGETS:
        gen = generate_questions(token, code, generation_need[code], existing_fps)
        selected.extend(gen)

    # If preserving a valid existing row pushed any domain beyond target, keep it. The user asked to preserve valid rows and total at least 320.
    backup = f"{DB}.bak.pre-md102-claude-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(DB, backup)
    print(json.dumps({'backup': backup, 'inserting_selected': len(selected)}), flush=True)
    try:
        with con:
            insert_pool(con, selected)
    except Exception:
        restore = f"{DB}.failed-md102-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(DB, restore)
        shutil.copy2(backup, DB)
        raise
    after = final_report(con)
    print(json.dumps({'after': after}, indent=2), flush=True)
    if after['total'] < TARGET_TOTAL or after['invalid_count'] != 0:
        raise SystemExit('Final validation failed. Backup exists; inspect database before continuing.')


if __name__ == '__main__':
    main()
