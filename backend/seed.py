import hashlib
import json
from database import connect, init_db

EXAMS = {
    'MD-102': {
        'name': 'Microsoft Endpoint Administrator', 'vendor': 'Microsoft', 'passing_score': 70, 'seed_count': 0,
        'description': 'Endpoint administration with Microsoft Intune, Microsoft Entra ID, Windows, Microsoft 365 Apps, and endpoint security aligned to the current MD-102 objectives.',
        # MD-102 is maintained by the Claude regeneration script from the official Microsoft Learn study guide.
        # Do not regenerate the old placeholder seed pool on startup.
        'objectives': [('1.0', 'Prepare infrastructure for devices', 28), ('2.0', 'Manage and maintain devices', 33), ('3.0', 'Manage applications', 20), ('4.0', 'Protect devices', 20)]
    },
    'AZ-104': {
        'name': 'Azure Administrator Associate', 'vendor': 'Microsoft', 'passing_score': 70, 'seed_count': 320,
        'description': 'Azure identities, governance, storage, compute, networking, monitoring, and backup.',
        'objectives': [('2.1', 'Manage Azure identities and governance', 20), ('2.2', 'Implement and manage storage', 15), ('2.3', 'Deploy and manage Azure compute resources', 25), ('2.4', 'Implement virtual networking', 25), ('2.5', 'Monitor and maintain Azure resources', 15)]
    },
    'N10-009': {
        'name': 'CompTIA Network+ N10-009', 'vendor': 'CompTIA', 'passing_score': 80, 'seed_count': 0,
        'description': 'Networking fundamentals, implementation, operations, security, and troubleshooting.',
        # N10-009 is maintained by the rebuild script from official objectives and ExamCompass scrape.
        # Do not regenerate the old placeholder seed pool on startup.
        'objectives': [('1.0', 'Networking Concepts', 23), ('2.0', 'Network Implementation', 20), ('3.0', 'Network Operations', 17), ('4.0', 'Network Security', 20), ('5.0', 'Network Troubleshooting', 20)]
    },
    '220-1101': {
        'name': 'CompTIA A+ Core 1', 'vendor': 'CompTIA', 'passing_score': 75, 'seed_count': 60,
        'description': 'Mobile devices, networking, hardware, virtualization, cloud computing, and hardware/network troubleshooting.',
        'objectives': [('4.1', 'Mobile devices', 15), ('4.2', 'Networking', 20), ('4.3', 'Hardware', 25), ('4.4', 'Virtualization and cloud computing', 11), ('4.5', 'Hardware and network troubleshooting', 29)]
    },
    '220-1102': {
        'name': 'CompTIA A+ Core 2', 'vendor': 'CompTIA', 'passing_score': 78, 'seed_count': 60,
        'description': 'Operating systems, security, software troubleshooting, and operational procedures.',
        'objectives': [('5.1', 'Operating systems', 31), ('5.2', 'Security', 25), ('5.3', 'Software troubleshooting', 22), ('5.4', 'Operational procedures', 22)]
    },
    'SY0-701': {
        'name': 'CompTIA Security+', 'vendor': 'CompTIA', 'passing_score': 83, 'seed_count': 60,
        'description': 'Security concepts, threats, architecture, operations, and security program management.',
        'objectives': [('6.1', 'General security concepts', 12), ('6.2', 'Threats, vulnerabilities, and mitigations', 22), ('6.3', 'Security architecture', 18), ('6.4', 'Security operations', 28), ('6.5', 'Security program management and oversight', 20)]
    },
    'XK0-005': {
        'name': 'CompTIA Linux+', 'vendor': 'CompTIA', 'passing_score': 80, 'seed_count': 60,
        'description': 'Linux system management, security, scripting, containers, automation, and troubleshooting.',
        'objectives': [('7.1', 'System management', 32), ('7.2', 'Security', 21), ('7.3', 'Scripting, containers, and automation', 19), ('7.4', 'Troubleshooting', 28)]
    },
    'SC-300': {
        'name': 'Identity and Access Administrator', 'vendor': 'Microsoft', 'passing_score': 70, 'seed_count': 60,
        'description': 'Microsoft Entra identities, authentication, access management, and identity governance.',
        'objectives': [('8.1', 'Implement identities in Microsoft Entra ID', 25), ('8.2', 'Implement authentication and access management', 25), ('8.3', 'Plan and implement workload identities', 20), ('8.4', 'Plan and implement identity governance', 30)]
    },
    'AZ-700': {
        'name': 'Azure Network Engineer', 'vendor': 'Microsoft', 'passing_score': 70, 'seed_count': 60,
        'description': 'Azure networking, hybrid connectivity, routing, private access, and network security.',
        'objectives': [('9.1', 'Design and implement core networking infrastructure', 25), ('9.2', 'Design and implement connectivity services', 25), ('9.3', 'Design and implement application delivery services', 20), ('9.4', 'Design and implement private access to Azure services', 10), ('9.5', 'Secure network connectivity to Azure resources', 20)]
    },
    'MS-102': {
        'name': 'Microsoft 365 Administrator', 'vendor': 'Microsoft', 'passing_score': 70, 'seed_count': 60,
        'description': 'Microsoft 365 tenant deployment, identity, security, compliance, and administration.',
        'objectives': [('10.1', 'Deploy and manage a Microsoft 365 tenant', 25), ('10.2', 'Implement and manage Microsoft Entra identity and access', 25), ('10.3', 'Manage security and threats with Microsoft Defender XDR', 25), ('10.4', 'Manage compliance with Microsoft Purview', 25)]
    },
}

TOPICS = {
    'MD-102': ['Intune compliance policy', 'Autopilot deployment profile', 'Conditional Access', 'Windows Update ring', 'Endpoint security baseline', 'app protection policy', 'device configuration profile', 'BitLocker recovery', 'co-management workload', 'local administrator password solution'],
    'AZ-104': ['Azure RBAC assignment', 'storage account redundancy', 'virtual network peering', 'NSG rule processing', 'Azure Monitor alert', 'availability set', 'managed disk snapshot', 'Recovery Services vault', 'route table', 'Azure Policy initiative'],
    'N10-009': ['subnet mask calculation', 'VLAN trunking', 'OSPF adjacency', 'DNS record type', '802.1X authentication', 'wireless channel planning', 'PoE budget', 'packet capture analysis', 'VPN tunnel', 'fiber connector'],
    '220-1101': ['M.2 storage', 'SO-DIMM memory', 'laser printer maintenance', 'Wi-Fi antenna placement', 'USB-C docking', 'cloud desktop', 'IPv4 addressing', 'laptop display replacement', 'PoE injector', 'RAID level selection'],
    '220-1102': ['Windows recovery environment', 'NTFS permissions', 'malware removal', 'mobile OS security', 'change management', 'ticket documentation', 'command-line utilities', 'browser troubleshooting', 'SOHO hardening', 'backup validation'],
    'SY0-701': ['phishing mitigation', 'zero trust architecture', 'SIEM alert triage', 'vulnerability management', 'PKI certificate lifecycle', 'incident response', 'IAM least privilege', 'cloud security posture', 'risk register', 'data classification'],
    'XK0-005': ['systemd service', 'SELinux context', 'Bash script', 'container image', 'LVM snapshot', 'SSH hardening', 'package repository', 'journalctl logs', 'network interface', 'cron automation'],
    'SC-300': ['Entra ID user lifecycle', 'Conditional Access policy', 'PIM activation', 'access review', 'enterprise application SSO', 'managed identity', 'authentication method policy', 'identity protection risk', 'Entitlement Management', 'B2B collaboration'],
    'AZ-700': ['hub-spoke topology', 'VPN gateway', 'ExpressRoute circuit', 'Azure Firewall policy', 'private endpoint DNS', 'Application Gateway', 'Traffic Manager', 'load balancer probe', 'route server', 'DDoS protection'],
    'MS-102': ['tenant configuration', 'Exchange Online role', 'Defender XDR incident', 'Purview retention label', 'Entra Connect', 'SharePoint sharing policy', 'Teams governance', 'Secure Score recommendation', 'audit search', 'compliance portal role'],
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
    ('single', ['A'], ['Apply the targeted policy to the affected scope', 'Disable monitoring temporarily', 'Rebuild every endpoint manually', 'Ignore the alert until recurrence']),
    ('single', ['B'], ['Grant broad administrator access', 'Use the native managed service feature', 'Move the workload outside the platform', 'Turn off enforcement globally']),
    ('multiple', ['A','C'], ['Verify prerequisites and scope assignments', 'Disable enforcement globally', 'Deploy the supported configuration to the affected group', 'Ignore audit findings until recurrence']),
    ('order', ['A','B','C','D'], ['Collect logs and confirm scope', 'Identify the root cause', 'Apply the least-privilege supported fix', 'Validate remediation and document the result']),
    ('match', ['A-B','C-D'], ['Control plane requirement', 'Supported native feature', 'Bad shortcut', 'Manual drift or unsupported bypass']),
]

REFERENCE_BY_VENDOR = {
    'Microsoft': {'title': 'Microsoft Learn certification documentation', 'url': 'https://learn.microsoft.com/en-us/credentials/certifications/'},
    'CompTIA': {'title': 'CompTIA exam objectives', 'url': 'https://www.comptia.org/certifications'},
}

def fp(exam_id, text):
    return hashlib.sha256(f'{exam_id}:{text}'.encode()).hexdigest()

def build_question(exam_id, objective_code, objective_title, topic, idx, vendor='Microsoft'):
    scenario = SCENARIOS[idx % len(SCENARIOS)]
    qtype, correct_keys, choices = ANSWER_BANK[idx % len(ANSWER_BANK)]
    text = f'{scenario} For {exam_id}, which action best addresses {topic} under objective {objective_title}?'
    if qtype == 'multiple':
        text += ' Select TWO answers.'
    elif qtype == 'order':
        text += ' Place the actions in the correct order.'
    elif qtype == 'match':
        text += ' Match each requirement to the best implementation.'
    correct = ','.join(correct_keys)
    correct_labels = ', '.join(correct_keys)
    explanation = (
        f'The correct answer is {correct_labels}. {topic} belongs to objective {objective_code} - {objective_title}. '
        'The defensible approach is to use documented platform capabilities, scope the change to the affected users or resources, preserve least privilege, validate with logs or compliance state, and document the outcome. '
        'The incorrect options are wrong because they either weaken security controls, create unmanaged manual drift, rely on unsupported workarounds, or skip root-cause validation. Professional exam items expect the supported vendor-native path, not heroic improvisation.'
    )
    reference = REFERENCE_BY_VENDOR.get(vendor, REFERENCE_BY_VENDOR['Microsoft'])
    exhibit = {'title': 'Scenario exhibit', 'body': f'Objective {objective_code}: {objective_title}. Topic focus: {topic}. Review the scenario constraints before selecting an answer.'} if idx % 7 == 0 else None
    return text, choices, correct, explanation, qtype, correct_keys, reference, exhibit

def seed():
    init_db()
    with connect() as conn:
        for exam_id, meta in EXAMS.items():
            # Avoid INSERT OR REPLACE here. In SQLite, REPLACE deletes the parent exam row first,
            # which cascades and destroys questions for rebuilt pools such as N10-009.
            conn.execute('INSERT OR IGNORE INTO exams(id,name,vendor,duration_minutes,passing_score,description) VALUES(?,?,?,?,?,?)',
                         (exam_id, meta['name'], meta['vendor'], 90, meta['passing_score'], meta['description']))
            conn.execute('UPDATE exams SET name=?, vendor=?, duration_minutes=?, passing_score=?, description=? WHERE id=?',
                         (meta['name'], meta['vendor'], 90, meta['passing_score'], meta['description'], exam_id))
            objective_ids = []
            for code, title, weight in meta['objectives']:
                conn.execute('INSERT OR IGNORE INTO objectives(exam_id,code,title,weight) VALUES(?,?,?,?)', (exam_id, code, title, weight))
                conn.execute('UPDATE objectives SET title=?, weight=? WHERE exam_id=? AND code=?', (title, weight, exam_id, code))
                oid = conn.execute('SELECT id FROM objectives WHERE exam_id=? AND code=?', (exam_id, code)).fetchone()['id']
                objective_ids.append((oid, code, title))
            total = meta.get('seed_count', 60)
            topics = TOPICS[exam_id]
            for i in range(total):
                oid, code, title = objective_ids[i % len(objective_ids)]
                topic = topics[i % len(topics)]
                text, choices, correct, explanation, qtype, correct_keys, reference, exhibit = build_question(exam_id, code, title, topic, i, meta['vendor'])
                text = f'{text} Case #{i + 1:03d}.'
                fingerprint = fp(exam_id, text)
                refs = [reference, {'title': f'{exam_id} official exam guide', 'url': reference['url']}]
                conn.execute('''INSERT OR IGNORE INTO questions
                    (exam_id,objective_id,question_text,choices_json,correct_choice,explanation,source,source_url,verified,active,difficulty,fingerprint,question_type,correct_json,exhibit_json,references_json)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (exam_id, oid, text, json.dumps(choices), correct, explanation, 'seed', reference['url'], 1, 1, 1 + (i % 3), fingerprint, qtype, json.dumps(correct_keys), json.dumps(exhibit or {}), json.dumps(refs)))
                qid = conn.execute('SELECT id FROM questions WHERE fingerprint=?', (fingerprint,)).fetchone()['id']
                conn.execute("""UPDATE questions SET explanation=?, source_url=COALESCE(NULLIF(source_url,''), ?), question_type=COALESCE(NULLIF(question_type,''), ?), correct_json=CASE WHEN correct_json IS NULL OR correct_json='' THEN ? ELSE correct_json END, references_json=CASE WHEN references_json IS NULL OR references_json='' THEN ? ELSE references_json END WHERE id=?""", (explanation, reference['url'], qtype, json.dumps(correct_keys), json.dumps(refs), qid))
                conn.execute('INSERT OR IGNORE INTO progress(exam_id,question_id) VALUES(?,?)', (exam_id, qid))

if __name__ == '__main__':
    seed()
    with connect() as conn:
        for row in conn.execute('SELECT exam_id, COUNT(*) c FROM questions GROUP BY exam_id ORDER BY exam_id'):
            print(f"{row['exam_id']}: {row['c']} questions")
