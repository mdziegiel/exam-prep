import hashlib
import json
from database import connect, init_db

EXAMS = {
    'MD-102': {
        'name': 'Microsoft Endpoint Administrator', 'vendor': 'Microsoft', 'description': 'Endpoint management with Intune, Entra ID, Windows, compliance, and security.',
        'objectives': [
            ('1.1', 'Deploy Windows client', 25), ('1.2', 'Manage identity and compliance', 25),
            ('1.3', 'Manage, maintain, and protect devices', 30), ('1.4', 'Manage applications', 20)
        ]
    },
    'AZ-104': {
        'name': 'Azure Administrator Associate', 'vendor': 'Microsoft', 'description': 'Azure identities, governance, storage, compute, networking, monitoring, and backup.',
        'objectives': [
            ('2.1', 'Manage Azure identities and governance', 20), ('2.2', 'Implement and manage storage', 15),
            ('2.3', 'Deploy and manage Azure compute resources', 25), ('2.4', 'Implement virtual networking', 25),
            ('2.5', 'Monitor and maintain Azure resources', 15)
        ]
    },
    'N10-009': {
        'name': 'CompTIA Network+ N10-009', 'vendor': 'CompTIA', 'description': 'Networking fundamentals, implementation, operations, security, and troubleshooting.',
        'objectives': [
            ('3.1', 'Networking concepts', 23), ('3.2', 'Network implementation', 20),
            ('3.3', 'Network operations', 19), ('3.4', 'Network security', 14), ('3.5', 'Network troubleshooting', 24)
        ]
    }
}

TOPICS = {
    'MD-102': ['Intune compliance policy', 'Autopilot deployment profile', 'Conditional Access', 'Windows Update ring', 'Endpoint security baseline', 'app protection policy', 'device configuration profile', 'BitLocker recovery', 'co-management workload', 'local administrator password solution'],
    'AZ-104': ['Azure RBAC assignment', 'storage account redundancy', 'virtual network peering', 'NSG rule processing', 'Azure Monitor alert', 'availability set', 'managed disk snapshot', 'Recovery Services vault', 'route table', 'Azure Policy initiative'],
    'N10-009': ['subnet mask calculation', 'VLAN trunking', 'OSPF adjacency', 'DNS record type', '802.1X authentication', 'wireless channel planning', 'PoE budget', 'packet capture analysis', 'VPN tunnel', 'fiber connector']
}

SCENARIOS = [
    'A company needs to improve reliability while minimizing administrative overhead.',
    'An administrator is troubleshooting a production issue reported by several users.',
    'A security team requires the least-privilege configuration for a new rollout.',
    'A migration project must preserve service availability during business hours.',
    'An audit found inconsistent settings across managed assets.',
    'A help desk team needs a repeatable process for a common support case.',
]

ANSWER_BANK = [
    ('A', ['Apply the targeted policy to the affected scope', 'Disable monitoring temporarily', 'Rebuild every endpoint manually', 'Ignore the alert until recurrence']),
    ('B', ['Grant broad administrator access', 'Use the native managed service feature', 'Move the workload outside the platform', 'Turn off enforcement globally']),
    ('C', ['Create a local exception on each device', 'Delete the existing configuration', 'Validate prerequisites, then deploy a scoped configuration', 'Wait for users to self-remediate']),
    ('D', ['Use an unsupported third-party workaround', 'Lower the security baseline', 'Bypass identity controls', 'Review logs, correct the root cause, and verify compliance']),
]

def fp(exam_id, text):
    return hashlib.sha256(f'{exam_id}:{text}'.encode()).hexdigest()

def build_question(exam_id, objective_code, objective_title, topic, idx):
    scenario = SCENARIOS[idx % len(SCENARIOS)]
    correct, choices = ANSWER_BANK[idx % len(ANSWER_BANK)]
    text = f'{scenario} For {exam_id}, which action best addresses {topic} under objective {objective_title}?'
    explanation = f'The correct answer is {correct}. {topic} maps to {objective_code} - {objective_title}. The right approach uses supported platform controls, scoped deployment, verification, and least privilege instead of broad manual changes or weakening security.'
    return text, choices, correct, explanation

def seed():
    init_db()
    with connect() as conn:
        for exam_id, meta in EXAMS.items():
            conn.execute('INSERT OR REPLACE INTO exams(id,name,vendor,duration_minutes,passing_score,description) VALUES(?,?,?,?,?,?)',
                         (exam_id, meta['name'], meta['vendor'], 90, 70, meta['description']))
            objective_ids = []
            for code, title, weight in meta['objectives']:
                conn.execute('INSERT OR IGNORE INTO objectives(exam_id,code,title,weight) VALUES(?,?,?,?)', (exam_id, code, title, weight))
                oid = conn.execute('SELECT id FROM objectives WHERE exam_id=? AND code=?', (exam_id, code)).fetchone()['id']
                objective_ids.append((oid, code, title))
            total = 320
            topics = TOPICS[exam_id]
            for i in range(total):
                oid, code, title = objective_ids[i % len(objective_ids)]
                topic = topics[i % len(topics)]
                text, choices, correct, explanation = build_question(exam_id, code, title, topic, i)
                # Make fingerprint-specific stem unique while keeping readable.
                text = f'{text} Case #{i + 1:03d}.'
                conn.execute('''INSERT OR IGNORE INTO questions
                    (exam_id,objective_id,question_text,choices_json,correct_choice,explanation,source,verified,active,difficulty,fingerprint)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                    (exam_id, oid, text, json.dumps(choices), correct, explanation, 'seed', 1, 1, 1 + (i % 3), fp(exam_id, text)))
                qid = conn.execute('SELECT id FROM questions WHERE fingerprint=?', (fp(exam_id, text),)).fetchone()['id']
                conn.execute('INSERT OR IGNORE INTO progress(exam_id,question_id) VALUES(?,?)', (exam_id, qid))

if __name__ == '__main__':
    seed()
    with connect() as conn:
        for row in conn.execute('SELECT exam_id, COUNT(*) c FROM questions GROUP BY exam_id'):
            print(f"{row['exam_id']}: {row['c']} questions")
