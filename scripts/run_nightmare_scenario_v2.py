import base64
import concurrent.futures
import json
import statistics
import time
import urllib.request
from pathlib import Path

PROXY_URL = 'http://127.0.0.1:8000/v1/chat/completions'
ADMIN_URL = 'http://127.0.0.1:8000/admin/cache/invalidate'
ADMIN_KEY = 'dev-admin-key'
OUT_PATH = Path('audit/reports/nightmare_scenario_v2_report_2026-04-20.json')


def invalidate(namespace: str):
    req = urllib.request.Request(
        ADMIN_URL,
        data=json.dumps({'namespace': namespace}).encode(),
        headers={'Content-Type': 'application/json', 'x-metera-admin-key': ADMIN_KEY, 'x-metera-namespace': namespace},
        method='POST',
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def send(namespace: str, messages):
    payload = {'model': 'gpt-4o-mini', 'messages': messages, 'stream': False, 'temperature': 0.0}
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


def visual_messages(token: str):
    image_bytes = token.encode() * 32
    image_b64 = base64.b64encode(image_bytes).decode()
    return [{
        'role': 'user',
        'content': [
            {'type': 'text', 'text': 'Inspect this checkout image and describe the action and amount.'},
            {'type': 'input_image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': image_b64}},
        ],
    }]


invalidate('nightmare-visual-v2')
visual_rows = []
for i in range(500):
    changed = (i % 50 == 0)
    token = f"DELETE_{i}_$100" if changed else f"SAVE_{i % 5}_$1"
    row = send('nightmare-visual-v2', visual_messages(token))
    row['changed'] = changed
    visual_rows.append(row)
modified = [r for r in visual_rows if r['changed']]
visual_failures = [r for r in modified if r['cache'] != 'miss']

invalidate('nightmare-race-v2')
race_rows = []
prompts = []
for i in range(200):
    user_id = f'user-{i % 20:02d}'
    prompt = f'Give me my account balance for USER_ID={user_id} ACCOUNT_ID=ACC-{i % 20:02d}.'
    prompts.append((user_id, [{'role': 'user', 'content': prompt}]))
with concurrent.futures.ThreadPoolExecutor(max_workers=32) as ex:
    futures = [ex.submit(send, 'nightmare-race-v2', messages) for _, messages in prompts]
    for (user_id, messages), fut in zip(prompts, futures):
        row = fut.result()
        row['user_id'] = user_id
        race_rows.append(row)
race_leaks = [r for r in race_rows if r['user_id'] not in r['content']]

invalidate('nightmare-shadow-v2')
base_uuid = '123e4567e89b12d3a456426614174000'
shadow_rows = []
seen = set()
for i in range(300):
    mutated = list(base_uuid)
    idx = i % len(mutated)
    mutated[idx] = 'f' if mutated[idx] != 'f' else 'e'
    shifted = ''.join(mutated)
    row = send('nightmare-shadow-v2', [{'role': 'user', 'content': f'Lookup record UUID={shifted} and summarize its state.'}])
    row['uuid'] = shifted
    row['first_seen_variant'] = shifted not in seen
    seen.add(shifted)
    shadow_rows.append(row)
shadow_failures = [r for r in shadow_rows if r['first_seen_variant'] and r['cache'] != 'miss']

all_rows = visual_rows + race_rows + shadow_rows
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
}
OUT_PATH.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
