# BETA_CUSTOMER_QUICKSTART

_Last updated: 2026-04-29 (evening)_
_Audience: beta users integrating with Metera for the first time._

This quickstart is intentionally short.
Its job is to answer one question quickly:

**Can I send a request through Metera in 2 minutes?**

If yes, the onboarding is working.

---

## 1. What you need

Your Metera beta credential package includes:
- `base_url`
- bearer token
- optional recommended namespace

You will use those to send an OpenAI-compatible chat request through Metera.

Important:
- for first-request onboarding, namespace is no longer required
- if you omit the namespace header, Metera automatically resolves a default namespace from your authenticated tenant/workspace identity
- if your team was given an explicit namespace and wants to keep using it, that still works

---

## 2. Request format

Metera currently exposes an **OpenAI-compatible** request surface.

Use:
- `POST /v1/chat/completions`

Auth:
- `Authorization: Bearer <your-tenant-api-key>`

Namespace header:
- optional: `x-metera-namespace: <your-namespace>`

Namespace resolution modes:
- explicit mode: send `x-metera-namespace` and Metera uses that exact namespace
- automatic mode: omit the header and Metera derives a default namespace from your authenticated tenant/workspace scope

Content type:
- `Content-Type: application/json`

---

## 3. Copy-paste example

Replace the placeholders below with the values from your credential package.

### Minimal first request (recommended)

#### cURL

```bash
curl -X POST "<base_url>/v1/chat/completions" \
  -H "Authorization: Bearer <your-tenant-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "user", "content": "Reply with exactly: METERA_BETA_OK"}
    ],
    "temperature": 0
  }'
```

#### PowerShell

```powershell
Invoke-WebRequest -Method Post `
  -Uri "<base_url>/v1/chat/completions" `
  -Headers @{ 
    'Authorization' = 'Bearer <your-tenant-api-key>';
    'Content-Type' = 'application/json'
  } `
  -Body '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Reply with exactly: METERA_BETA_OK"}],"temperature":0}'
```

### Optional explicit-namespace request

Use this only if Metera gave your team a specific namespace to use or if you intentionally want to override the automatic default.

#### cURL

```bash
curl -X POST "<base_url>/v1/chat/completions" \
  -H "Authorization: Bearer <your-tenant-api-key>" \
  -H "x-metera-namespace: <your-namespace>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "user", "content": "Reply with exactly: METERA_BETA_OK"}
    ],
    "temperature": 0
  }'
```

#### PowerShell

```powershell
Invoke-WebRequest -Method Post `
  -Uri "<base_url>/v1/chat/completions" `
  -Headers @{ 
    'Authorization' = 'Bearer <your-tenant-api-key>';
    'x-metera-namespace' = '<your-namespace>';
    'Content-Type' = 'application/json'
  } `
  -Body '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Reply with exactly: METERA_BETA_OK"}],"temperature":0}'
```

---

## 4. What success looks like

A successful response should:
- return HTTP success
- include a normal assistant response
- include Metera attribution metadata in the response payload

At a minimum, you should see the model respond with:
- `METERA_BETA_OK`

Depending on your client tooling, you may also see Metera metadata showing request attribution and cache outcome.

---

## 5. What Metera is doing for you

On the current beta path, Metera sits in front of your model traffic and provides:
- request routing through the Metera gateway
- exact cache reuse when applicable
- semantic cache reuse when applicable
- tenant/workspace attribution
- usage and savings visibility in the control plane

You do not need to configure all of that to complete first-request onboarding.
The first goal is simply to confirm that your traffic flows successfully.

---

## 6. Common errors

### 401 Unauthorized
Meaning:
- your bearer token is missing, invalid, or malformed

Check:
- you included `Authorization: Bearer <your-tenant-api-key>` exactly
- the token value was copied correctly

### 402 Payment Required
Meaning:
- your tenant is currently blocked by billing/commercial state in the Metera control plane

What to do:
- contact Metera support
- include your tenant name and a copy of the response

### 403 Forbidden
Meaning:
- your authenticated scope does not match the requested tenant/workspace access pattern

What to do:
- confirm you are using the credential package issued for your tenant
- contact support if the credentials were issued recently and still fail

### 5xx / upstream-style failure
Meaning:
- the request reached Metera but failed due to deployment or upstream conditions

What to do:
- retry once if appropriate
- if it persists, contact support with the response body and approximate request time

---

## 7. Model guidance

Metera currently supports an **OpenAI-compatible** request contract.

Use the same request shape you would use for an OpenAI-compatible chat completion call.
Your team chooses the model inside that request contract.

If you are unsure what to use first, start with:
- `gpt-4o-mini`

That is a good minimal probe model for onboarding.

---

## 8. Support

This is a managed beta.
If your first request does not work, contact Metera support through the path you were given during onboarding.

Current beta support is founder-directed and may include:
- email
- optional Slack/Discord for active users

When reporting a problem, include:
- your tenant name
- approximate timestamp
- request path used
- response body or error text

---

## 9. What comes after first request

Once your first request works, the next useful surfaces are:
- tenant billing scope
- tenant billing overview
- tenant reports
- tenant invoices

Those are part of the broader beta product surface, but they are intentionally not required for the first 2-minute test.

---

## 10. Blunt summary

If you have:
- `base_url`
- bearer token

then you should be able to send an OpenAI-compatible request through Metera immediately.

If you also have a recommended namespace, you can use it explicitly, but you do not need it for first-request success.

If that works, your beta onboarding is real.