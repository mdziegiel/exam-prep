import hashlib
import json
from database import connect, init_db

EXAMS = {
    'MD-102': {
        'name': 'Microsoft Endpoint Administrator', 'vendor': 'Microsoft', 'passing_score': 70, 'seed_count': 320,
        'description': 'Endpoint management with Intune, Entra ID, Windows, compliance, and security.',
        'objectives': [('1.1', 'Deploy Windows client', 25), ('1.2', 'Manage identity and compliance', 25), ('1.3', 'Manage, maintain, and protect devices', 30), ('1.4', 'Manage applications', 20)]
    },
    'AZ-104': {
        'name': 'Azure Administrator Associate', 'vendor': 'Microsoft', 'passing_score': 70, 'seed_count': 320,
        'description': 'Azure identities, governance, storage, compute, networking, monitoring, and backup.',
        'objectives': [('2.1', 'Manage Azure identities and governance', 20), ('2.2', 'Implement and manage storage', 15), ('2.3', 'Deploy and manage Azure compute resources', 25), ('2.4', 'Implement virtual networking', 25), ('2.5', 'Monitor and maintain Azure resources', 15)]
    },
    'N10-009': {
        'name': 'CompTIA Network+ N10-009', 'vendor': 'CompTIA', 'passing_score': 80, 'seed_count': 320,
        'description': 'Networking fundamentals, implementation, operations, security, and troubleshooting.',
        'objectives': [('3.1', 'Networking concepts', 23), ('3.2', 'Network implementation', 20), ('3.3', 'Network operations', 19), ('3.4', 'Network security', 14), ('3.5', 'Network troubleshooting', 24)]
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
    explanation = f'The correct answer is {correct}. {topic} maps to {objective_code} - {objective_title}. Use supported controls, least privilege, scoped deployment, logging, and validation. The distractors either weaken security, create manual drift, or avoid the root cause.'
    return text, choices, correct, explanation

def seed():
    init_db()
    with connect() as conn:
        for exam_id, meta in EXAMS.items():
            conn.execute('INSERT OR REPLACE INTO exams(id,name,vendor,duration_minutes,passing_score,description) VALUES(?,?,?,?,?,?)',
                         (exam_id, meta['name'], meta['vendor'], 90, meta['passing_score'], meta['description']))
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
                text, choices, correct, explanation = build_question(exam_id, code, title, topic, i)
                text = f'{text} Case #{i + 1:03d}.'
                fingerprint = fp(exam_id, text)
                conn.execute('''INSERT OR IGNORE INTO questions
                    (exam_id,objective_id,question_text,choices_json,correct_choice,explanation,source,verified,active,difficulty,fingerprint)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                    (exam_id, oid, text, json.dumps(choices), correct, explanation, 'seed', 1, 1, 1 + (i % 3), fingerprint))
                qid = conn.execute('SELECT id FROM questions WHERE fingerprint=?', (fingerprint,)).fetchone()['id']
                conn.execute('INSERT OR IGNORE INTO progress(exam_id,question_id) VALUES(?,?)', (exam_id, qid))

if __name__ == '__main__':
    seed()
    with connect() as conn:
        for row in conn.execute('SELECT exam_id, COUNT(*) c FROM questions GROUP BY exam_id ORDER BY exam_id'):
            print(f"{row['exam_id']}: {row['c']} questions")
