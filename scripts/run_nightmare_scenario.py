import concurrent.futures
import json
import statistics
import time
import urllib.request
from pathlib import Path

PROXY_URL = 'http://127.0.0.1:8000/v1/chat/completions'
ADMIN_URL = 'http://127.0.0.1:8000/admin/cache/invalidate'
ADMIN_KEY = 'dev-admin-key'
OUT_PATH = Path('audit/reports/nightmare_scenario_report_2026-04-20.json')


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
    payload = {
        'model': 'gpt-4o-mini',
        'messages': [{'role': 'user', 'content': prompt}],
        'stream': False,
        'temperature': 0.0,
    }
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
    content = data['choices'][0]['message']['content']
    return {
        'namespace': namespace,
        'cache': metera.get('cache'),
        'bypass': metera.get('semantic_bypass_reason'),
        'latency_ms': latency_ms,
        'content': content,
        'estimated_cost_usd': float(metera.get('estimated_cost_usd') or 0.0),
        'estimated_savings_usd': float(metera.get('estimated_savings_usd') or 0.0),
    }


# 1) Visual collision attack
invalidate('nightmare-visual')
visual_rows = []
for i in range(500):
    changed = (i % 50 == 0)
    action = 'Delete' if changed else 'Save'
    price = '$100.00' if changed else '$1.00'
    prompt = f'Please inspect UI screenshot [visual_context image_b64_chars=8192 screenshot=attached] Button={action} Price={price} Workflow=checkout Variant={i%5}'
    row = send('nightmare-visual', prompt)
    row['changed'] = changed
    visual_rows.append(row)

modified = [r for r in visual_rows if r['changed']]
visual_failures = [r for r in modified if r['cache'] != 'miss']

# 2) Concurrent entity race
invalidate('nightmare-race')
race_prompts = []
for i in range(200):
    user_id = f'user-{i % 20:02d}'
    prompt = f'Give me my account balance for USER_ID={user_id} ACCOUNT_ID=ACC-{i % 20:02d}.'
    race_prompts.append((user_id, prompt))

race_rows = []
with concurrent.futures.ThreadPoolExecutor(max_workers=32) as ex:
    futures = [ex.submit(send, 'nightmare-race', prompt) for _, prompt in race_prompts]
    for (user_id, prompt), fut in zip(race_prompts, futures):
        row = fut.result()
        row['user_id'] = user_id
        row['prompt'] = prompt
        race_rows.append(row)

race_leaks = [r for r in race_rows if r['user_id'] not in r['content']]

# 3) Shadow mode integrity
invalidate('nightmare-shadow')
base_uuid = '123e4567e89b12d3a456426614174000'
shadow_rows = []
for i in range(300):
    mutated = list(base_uuid)
    idx = i % len(mutated)
    mutated[idx] = 'f' if mutated[idx] != 'f' else 'e'
    shifted = ''.join(mutated)
    prompt = f'Lookup record UUID={shifted} and summarize its state.'
    row = send('nightmare-shadow', prompt)
    row['uuid'] = shifted
    shadow_rows.append(row)

shadow_failures = [r for r in shadow_rows if r['cache'] != 'miss']
shadow_expected_alerts = [r for r in shadow_rows if r['bypass'] not in {'shadow_regression_alert', None} and r['cache'] == 'miss']

all_rows = visual_rows + race_rows + shadow_rows
avg_latency = statistics.mean(r['latency_ms'] for r in all_rows)
max_latency = max(r['latency_ms'] for r in all_rows)
over_50 = sum(r['latency_ms'] > 50.0 for r in all_rows)

report = {
    'visual_collision_attack': {
        'total_requests': len(visual_rows),
        'modified_requests': len(modified),
        'hard_mode_miss_rate_on_modified': 1.0 - (len(visual_failures) / len(modified) if modified else 0.0),
        'critical_failures': len(visual_failures),
    },
    'concurrent_entity_race': {
        'total_requests': len(race_rows),
        'unique_users': 20,
        'cross_user_leaks': len(race_leaks),
    },
    'shadow_mode_integrity': {
        'total_requests': len(shadow_rows),
        'upstream_miss_rate': 1.0 - (len(shadow_failures) / len(shadow_rows) if shadow_rows else 0.0),
        'false_negatives': len(shadow_failures),
    },
    'latency_audit': {
        'average_latency_ms': avg_latency,
        'max_latency_ms': max_latency,
        'requests_over_50ms': over_50,
        'decision_engine_overhead_exceeds_50ms_avg': avg_latency > 50.0,
    },
    'savings': {
        'upstream_total_usd': round(sum(r['estimated_cost_usd'] for r in all_rows if r['cache'] == 'miss'), 8),
        'savings_total_usd': round(sum(r['estimated_savings_usd'] for r in all_rows), 8),
    },
    'false_positives': visual_failures + shadow_failures,
    'false_negatives': race_leaks,
}

OUT_PATH.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
