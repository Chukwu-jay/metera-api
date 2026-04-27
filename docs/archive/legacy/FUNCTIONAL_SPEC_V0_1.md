# Metera Functional Specification v0.1

## Purpose
Define the request lifecycle, policy precedence, cache behavior, and observability outputs for Metera v1.

## Request lifecycle
1. receive request
2. authenticate tenant / key
3. resolve namespace
4. derive request profile
   - modality
   - intent
   - module
   - entity fingerprint
5. resolve policy mode
   - hard
   - soft
   - exact-only
6. evaluate exact cache
7. evaluate semantic candidate if policy allows
8. validate compatibility
9. choose outcome
   - exact hit
   - semantic hit
   - shadow alert + upstream miss
   - hard reject to upstream miss
10. persist telemetry
11. return response

## Policy precedence
Highest precedence first:
1. explicit request opt-out / exact-only override
2. visual context auto-hard
3. strict enforcement namespace match
4. explicit high-risk namespace match
5. agentic / DOM / workflow detection
6. soft namespace default

## Safety modes
### Hard mode
- semantic reuse is disallowed or hard-rejected on mismatch
- exact cache may be allowed if request identity is safely exact
- visual and browser/agentic traffic belong here

### Soft mode
- semantic reuse allowed when compatible
- incompatible candidate triggers shadow regression alert
- flagged candidate falls through to upstream miss
- flagged candidate is never served

### Exact-only mode
- exact cache allowed
- semantic reuse disabled

## Compatibility rules
A semantic candidate is incompatible if any of these mismatch:
- intent
- module
- visual-context presence
- DOM-context presence
- agentic mode
- entity fingerprint

## Observability outputs
Per request, emit:
- cache outcome
- semantic bypass reason
- estimated cost USD
- estimated savings USD
- namespace
- request id
- semantic metadata when applicable

## Promotion rule
If a soft namespace exceeds 5% shadow alert rate over a meaningful sample, flag it for hardening review.

## Success conditions
- visual requests always auto-hard
- browser/agentic requests never serve semantic reuse
- soft mismatches never serve flagged hits
- savings remain measurable and attributable
