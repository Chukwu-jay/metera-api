import concurrent.futures
import json
import statistics
import time
import urllib.request
from pathlib import Path

PROXY_URL = 'http://127.0.0.1:8000/v1/chat/completions'
ADMIN_URL = 'http://127.0.0.1:8000/admin/cache/invalidate'
ADMIN_KEY = 'dev-admin-key'
OUT_PATH = Path('audit/reports/identity_nightmare_report_2026-04-20.json')


def invalidate(namespace: str):
    req = urllib.request.Request(
        ADMIN_URL,
        data=json.dumps({'namespace': namespace}).encode(),
        headers={'Content-Type': 'application/json', 'x-metera-admin-key': ADMIN_KEY, 'x-metera-namespace': namespace},
        method='POST',
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def send(namespace: str, prompt: str):
    payload = {'model': 'gpt-4o-mini', 'messages': [{'role': 'user', 'content': prompt}], 'stream': False, 'temperature': 0.0}
    req = urllib.request.Request(
        PROXY_URL,
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', 'x-metera-namespace': namespace},
        method='POST',
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    latency_ms = (time.perf_counter() - t0) * 1000.0
    metera = data.get('metera', {})
    return {
        'cache': metera.get('cache'),
        'bypass': metera.get('semantic_bypass_reason'),
        'latency_ms': latency_ms,
        'content': data['choices'][0]['message']['content'],
        'timings_ms': metera.get('timings_ms') or {},
        'estimated_cost_usd': float(metera.get('estimated_cost_usd') or 0.0),
        'estimated_savings_usd': float(metera.get('estimated_savings_usd') or 0.0),
    }

invalidate('nightmare-race-v2')
invalidate('nightmare-shadow-v2')

race_rows = []
prompts = []
for i in range(200):
    user_id = f'user-{i % 20:02d}'
    prompt = f'Give me my account balance for USER_ID={user_id} ACCOUNT_ID=ACC-{i % 20:02d}.'
    prompts.append((user_id, prompt))
with concurrent.futures.ThreadPoolExecutor(max_workers=32) as ex:
    futures = [ex.submit(send, 'nightmare-race-v2', prompt) for _, prompt in prompts]
    for (user_id, prompt), fut in zip(prompts, futures):
        row = fut.result()
        row['user_id'] = user_id
        row['prompt'] = prompt
        race_rows.append(row)
race_leaks = [r for r in race_rows if r['user_id'] not in r['content']]

base_uuid = '123e4567e89b12d3a456426614174000'
shadow_rows = []
seen = set()
for i in range(300):
    mutated = list(base_uuid)
    idx = i % len(mutated)
    mutated[idx] = 'f' if mutated[idx] != 'f' else 'e'
    shifted = ''.join(mutated)
    row = send('nightmare-shadow-v2', f'Lookup record UUID={shifted} and summarize its state.')
    row['uuid'] = shifted
    row['first_seen_variant'] = shifted not in seen
    seen.add(shifted)
    shadow_rows.append(row)
shadow_failures = [r for r in shadow_rows if r['first_seen_variant'] and r['cache'] != 'miss']

all_rows = race_rows + shadow_rows
report = {
    'concurrent_entity_race': {
        'total_requests': len(race_rows),
        'unique_users': 20,
        'cross_user_leaks': len(race_leaks),
    },
    'shadow_mode_integrity': {
        'total_requests': len(shadow_rows),
        'unique_variants': len({r['uuid'] for r in shadow_rows}),
        'first_seen_upstream_miss_rate': 1.0 - (len(shadow_failures) / len([r for r in shadow_rows if r['first_seen_variant']]) if shadow_rows else 0.0),
        'false_negatives': len(shadow_failures),
    },
    'latency_audit': {
        'average_latency_ms': statistics.mean(r['latency_ms'] for r in all_rows),
        'max_latency_ms': max(r['latency_ms'] for r in all_rows),
        'requests_over_50ms': sum(r['latency_ms'] > 50.0 for r in all_rows),
        'avg_profile_build_ms': statistics.mean((r['timings_ms'].get('profile_build_ms') or 0.0) for r in all_rows),
        'avg_semantic_lookup_ms': statistics.mean((r['timings_ms'].get('semantic_lookup_ms') or 0.0) for r in all_rows),
        'avg_compatibility_validation_ms': statistics.mean((r['timings_ms'].get('compatibility_validation_ms') or 0.0) for r in all_rows),
        'avg_upstream_ms': statistics.mean((r['timings_ms'].get('upstream_ms') or 0.0) for r in all_rows),
    },
    'savings': {
        'upstream_total_usd': round(sum(r['estimated_cost_usd'] for r in all_rows if r['cache'] == 'miss'), 8),
        'savings_total_usd': round(sum(r['estimated_savings_usd'] for r in all_rows), 8),
    },
}
OUT_PATH.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
