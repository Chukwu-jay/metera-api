import json
import urllib.request

URL = 'http://127.0.0.1:8000/v1/chat/completions'
REQUESTS = [
    ('faq-billing', 'What is the refund status for invoice INV-1001 for Acme North?'),
    ('faq-billing', 'What is the refund status for invoice INV-1002 for Acme South?'),
    ('faq-billing', 'What is the refund status for invoice INV-1003 for Acme East?'),
    ('support-tickets', 'Summarize support ticket TCK-2001 for customer Jane Doe about password reset failure.'),
    ('support-tickets', 'Summarize support ticket TCK-2002 for customer John Roe about MFA lockout.'),
    ('support-tickets', 'Summarize support ticket TCK-2003 for customer Maya Lee about billing mismatch.'),
]

for namespace, prompt in REQUESTS:
    payload = {
        'model': 'gpt-4o-mini',
        'messages': [{'role': 'user', 'content': prompt}],
        'stream': False,
        'temperature': 0.0,
    }
    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', 'x-metera-namespace': namespace},
        method='POST',
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    print(json.dumps({
        'namespace': namespace,
        'cache': data.get('metera', {}).get('cache'),
        'bypass': data.get('metera', {}).get('semantic_bypass_reason'),
        'content': data['choices'][0]['message']['content'][:100],
    }))
