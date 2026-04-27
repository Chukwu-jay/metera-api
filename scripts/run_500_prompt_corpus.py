import json
import time
import urllib.request
from collections import Counter, defaultdict

URL = 'http://127.0.0.1:8000/v1/chat/completions'
NAMESPACES = ['faq-billing', 'faq-general', 'support-technical']
CUSTOMERS = ['Jane Doe','John Roe','Maya Lee','Chris Park','Ava Patel','Noah Kim','Liam Chen','Emma Brooks','Olivia Diaz','Lucas Grant','Sophia Reed','Mason Cole','Amelia Ross','Ethan Bell','Isla Ward','Logan Price','Harper Stone','Elijah Fox','Nora Hayes','James Long']
ISSUES = ['password reset failure','MFA lockout','billing mismatch','invoice not received','subscription cancellation error','seat provisioning delay','API key rotation failure','dashboard access denied','SSO redirect loop','export job timeout']
PRODUCTS = ['Metera Core','Metera Billing','Metera Console','Metera API','Metera Teams']
VISUAL_EVERY = 25
TOTAL = 500


def build_prompt(i: int, namespace: str) -> str:
    customer = CUSTOMERS[i % len(CUSTOMERS)]
    issue = ISSUES[i % len(ISSUES)]
    product = PRODUCTS[i % len(PRODUCTS)]
    invoice = f'INV-{1000 + i}'
    ticket = f'TCK-{3000 + i}'
    visual = (i % VISUAL_EVERY == 0)

    if namespace == 'faq-billing':
        base = f'What is the refund status for invoice {invoice} for {customer} in {product}? Include billing state and next action.'
    elif namespace == 'faq-general':
        base = f'Answer a general FAQ for {customer}: how do I resolve {issue} in {product}? Include concise steps.'
    else:
        base = f'Summarize support ticket {ticket} for customer {customer} about {issue} in {product}. Include urgency and next action.'

    if visual:
        base += ' [visual_context image_b64_chars=4096 screenshot=attached]'
    return base


rows = []
started = time.perf_counter()
for i in range(TOTAL):
    namespace = NAMESPACES[i % len(NAMESPACES)]
    prompt = build_prompt(i, namespace)
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
    t0 = time.perf_counter()
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    latency_ms = (time.perf_counter() - t0) * 1000.0
    metera = data.get('metera', {})
    rows.append({
        'namespace': namespace,
        'cache': metera.get('cache'),
        'bypass': metera.get('semantic_bypass_reason'),
        'estimated_cost_usd': float(metera.get('estimated_cost_usd') or 0.0),
        'estimated_savings_usd': float(metera.get('estimated_savings_usd') or 0.0),
        'latency_ms': latency_ms,
        'visual': '[visual_context' in prompt,
    })

total_ms = (time.perf_counter() - started) * 1000.0
cache_counts = Counter(r['cache'] for r in rows)
bypass_counts = Counter((r['bypass'] or 'none') for r in rows)
by_ns = defaultdict(list)
for row in rows:
    by_ns[row['namespace']].append(row)

summary = {
    'total_requests': len(rows),
    'elapsed_ms': total_ms,
    'avg_latency_ms': sum(r['latency_ms'] for r in rows) / len(rows),
    'cache_counts': dict(cache_counts),
    'bypass_counts': dict(bypass_counts),
    'savings_total_usd': round(sum(r['estimated_savings_usd'] for r in rows), 8),
    'upstream_total_usd': round(sum(r['estimated_cost_usd'] for r in rows if r['cache'] == 'miss'), 8),
    'by_namespace': {},
}
for ns, ns_rows in by_ns.items():
    summary['by_namespace'][ns] = {
        'requests': len(ns_rows),
        'avg_latency_ms': sum(r['latency_ms'] for r in ns_rows) / len(ns_rows),
        'cache_counts': dict(Counter(r['cache'] for r in ns_rows)),
        'bypass_counts': dict(Counter((r['bypass'] or 'none') for r in ns_rows)),
        'visual_requests': sum(bool(r['visual']) for r in ns_rows),
        'savings_total_usd': round(sum(r['estimated_savings_usd'] for r in ns_rows), 8),
        'upstream_total_usd': round(sum(r['estimated_cost_usd'] for r in ns_rows if r['cache'] == 'miss'), 8),
    }

print(json.dumps({'summary': summary, 'rows': rows}))
