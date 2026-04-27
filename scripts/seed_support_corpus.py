import json
import urllib.request

URL = 'http://127.0.0.1:8000/v1/chat/completions'
NAMESPACE = 'support-bulk'
CUSTOMERS = [
    'Jane Doe','John Roe','Maya Lee','Chris Park','Ava Patel','Noah Kim','Liam Chen','Emma Brooks','Olivia Diaz','Lucas Grant',
    'Sophia Reed','Mason Cole','Amelia Ross','Ethan Bell','Isla Ward','Logan Price','Harper Stone','Elijah Fox','Nora Hayes','James Long'
]
ISSUES = [
    'password reset failure','MFA lockout','billing mismatch','invoice not received','subscription cancellation error',
    'seat provisioning delay','API key rotation failure','dashboard access denied','SSO redirect loop','export job timeout'
]
PRODUCTS = ['Metera Core','Metera Billing','Metera Console','Metera API','Metera Teams']
results = []
for i in range(150):
    customer = CUSTOMERS[i % len(CUSTOMERS)]
    issue = ISSUES[i % len(ISSUES)]
    product = PRODUCTS[i % len(PRODUCTS)]
    ticket = f'TCK-{3000 + i}'
    prompt = f'Summarize support ticket {ticket} for customer {customer} about {issue} in {product}. Include next action and urgency.'
    payload = {
        'model': 'gpt-4o-mini',
        'messages': [{'role': 'user', 'content': prompt}],
        'stream': False,
        'temperature': 0.0,
    }
    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', 'x-metera-namespace': NAMESPACE},
        method='POST',
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    results.append({
        'ticket': ticket,
        'customer': customer,
        'issue': issue,
        'cache': data.get('metera', {}).get('cache'),
        'bypass': data.get('metera', {}).get('semantic_bypass_reason'),
        'estimated_cost_usd': data.get('metera', {}).get('estimated_cost_usd'),
        'estimated_savings_usd': data.get('metera', {}).get('estimated_savings_usd'),
    })
print(json.dumps(results))
