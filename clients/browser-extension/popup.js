const apiBaseInput = document.getElementById('apiBase');
const apiKeyInput = document.getElementById('apiKey');
const namespaceInput = document.getElementById('namespace');
const emailInput = document.getElementById('email');
const workspaceIdInput = document.getElementById('workspaceId');
const challengeIdInput = document.getElementById('challengeId');
const verificationCodeInput = document.getElementById('verificationCode');
const saveDirectKeyButton = document.getElementById('saveDirectKeyButton');
const requestCodeButton = document.getElementById('requestCodeButton');
const exchangeCodeButton = document.getElementById('exchangeCodeButton');
const loginStatus = document.getElementById('loginStatus');
const understandChatButton = document.getElementById('understandChatButton');
const generateHandoffButton = document.getElementById('generateHandoffButton');
const exportContextButton = document.getElementById('exportContextButton');
const insertHandoffButton = document.getElementById('insertHandoffButton');
const sessionStatus = document.getElementById('sessionStatus');
const handoffOutput = document.getElementById('handoffOutput');
const permInsert = document.getElementById('permInsert');
const permSaveSummary = document.getElementById('permSaveSummary');
const permCaptureSelection = document.getElementById('permCaptureSelection');
const savePermissionsButton = document.getElementById('savePermissionsButton');
const permissionStatus = document.getElementById('permissionStatus');
const refreshWorkflowsButton = document.getElementById('refreshWorkflowsButton');
const workflowSelect = document.getElementById('workflowSelect');
const newWorkflowGoal = document.getElementById('newWorkflowGoal');
const createWorkflowButton = document.getElementById('createWorkflowButton');
const clearWorkflowSelectionButton = document.getElementById('clearWorkflowSelectionButton');
const targetSelect = document.getElementById('targetSelect');
const modeSelect = document.getElementById('modeSelect');
const composeInstruction = document.getElementById('composeInstruction');
const useSelectedTextToggle = document.getElementById('useSelectedTextToggle');
const composePreviewButton = document.getElementById('composePreviewButton');
const composeInsertButton = document.getElementById('composeInsertButton');
const inspectPromptButton = document.getElementById('inspectPromptButton');
const restartPackOutput = document.getElementById('restartPackOutput');
const sourceTraceOutput = document.getElementById('sourceTraceOutput');
const workflowStatus = document.getElementById('workflowStatus');
const providerStatus = document.getElementById('providerStatus');
const diagnosticsOutput = document.getElementById('diagnosticsOutput');
const handoffStatus = document.getElementById('handoffStatus');
const selectedTextPreview = document.getElementById('selectedTextPreview');
const localCaptureStatus = document.getElementById('localCaptureStatus');
const captureRetentionPolicy = document.getElementById('captureRetentionPolicy');
const summaryInput = document.getElementById('summaryInput');
const classificationSelect = document.getElementById('classificationSelect');
const saveSummaryButton = document.getElementById('saveSummaryButton');
const captureSelectionButton = document.getElementById('captureSelectionButton');
const captureLatestResponseButton = document.getElementById('captureLatestResponseButton');
const clearLocalCaptureButton = document.getElementById('clearLocalCaptureButton');
const captureStatus = document.getElementById('captureStatus');

const WORKFLOW_COMPOSE_ROUTE = '/compose';
const WORKFLOW_COMPOSE_PREVIEW_ROUTE = '/compose/preview';
const LOCAL_CAPTURE_KEY = 'localCapturePreview';
const SESSION_CONTEXT_KEY = 'meteraSessionContext';
const LOCAL_WORKFLOWS_KEY = 'localBetaWorkflows';
const LOCAL_CAPTURES_KEY = 'localBetaCaptures';
const LONG_SELECTED_CAPTURE_THRESHOLD = 6000;

let lastPromptInspection = null;
let lastTabContext = null;
let lastCaptureMode = null;

function setStatus(node, message) { node.textContent = message; }
async function getState() { return chrome.storage.local.get(['apiBase', 'email', 'workspaceId', 'challengeId', 'verificationCode', 'apiKey', 'namespace', 'defaultTarget', 'workflowId', 'composeMode', 'composeInstruction', 'newWorkflowGoal', 'useSelectedTextToggle', 'permissions', LOCAL_WORKFLOWS_KEY, LOCAL_CAPTURES_KEY, SESSION_CONTEXT_KEY]); }
async function saveState(patch) { await chrome.storage.local.set(patch); }
function sessionStorageArea() { return chrome.storage.session || chrome.storage.local; }
async function storageGet(area, keys) { return area.get(keys); }
async function storageSet(area, patch) { return area.set(patch); }
async function storageRemove(area, keys) { return area.remove(keys); }
function authHeaders(state) { const headers = { 'content-type': 'application/json' }; if (state.apiKey) headers.authorization = `Bearer ${state.apiKey}`; if (state.namespace) headers['x-metera-namespace'] = state.namespace; return headers; }
async function fetchJson(url, options = {}) { const response = await fetch(url, options); const body = await response.json().catch(() => ({})); if (!response.ok) throw new Error(body.detail || body.message || `Request failed (${response.status})`); return body; }
function selectedPermissionState() { return { insert_restart_pack: !!permInsert.checked, save_conversation_summary: !!permSaveSummary.checked, capture_selected_response: !!permCaptureSelection.checked }; }
function selectedClassifications() { return Array.from(classificationSelect.selectedOptions).map((option) => option.value); }
function applyClassifications(values) {
  const wanted = new Set(values || []);
  Array.from(classificationSelect.options).forEach((option) => { option.selected = wanted.has(option.value); });
}
function defaultWorkflowGoal() {
  const surface = (targetSelect.value || 'generic').trim();
  return `${surface} smoke workflow - ${new Date().toISOString().slice(0, 16).replace('T', ' ')}`;
}
function formatError(error) {
  if (!error) return 'Unknown error.';
  const details = [];
  if (error.message) details.push(error.message);
  if (error.diagnostics?.path) details.push(`path=${error.diagnostics.path}`);
  if (error.diagnostics?.tabId) details.push(`tab=${error.diagnostics.tabId}`);
  return details.join(' | ');
}
function safeParseUrl(url) { try { return new URL(url); } catch { return null; } }
function isLocalWorkflowId(id) { return String(id || '').startsWith('local_'); }
function nowIso() { return new Date().toISOString(); }
function slugPart(value) { return String(value || 'metera').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 48) || 'metera'; }

async function getLocalWorkflows() {
  const state = await getState();
  return Array.isArray(state[LOCAL_WORKFLOWS_KEY]) ? state[LOCAL_WORKFLOWS_KEY] : [];
}

async function saveLocalWorkflows(workflows) {
  await chrome.storage.local.set({ [LOCAL_WORKFLOWS_KEY]: workflows });
}

async function getLocalCaptures() {
  const state = await getState();
  return Array.isArray(state[LOCAL_CAPTURES_KEY]) ? state[LOCAL_CAPTURES_KEY] : [];
}

async function saveLocalCaptures(captures) {
  await chrome.storage.local.set({ [LOCAL_CAPTURES_KEY]: captures });
}

async function getSessionContext() {
  const state = await getState();
  return state[SESSION_CONTEXT_KEY] || {};
}

async function saveSessionContext(patch) {
  const current = await getSessionContext();
  const next = { ...current, ...patch, updated_at: nowIso() };
  await chrome.storage.local.set({ [SESSION_CONTEXT_KEY]: next });
  return next;
}

function currentProviderName() {
  const url = safeParseUrl(lastTabContext?.url || '');
  if (!url) return targetSelect.value || 'generic';
  if (url.hostname.includes('chatgpt') || url.hostname.includes('openai')) return 'ChatGPT';
  if (url.hostname.includes('claude')) return 'Claude';
  return url.hostname;
}

function cleanCapturedText(text) {
  return String(text || '')
    .replace(/\r/g, '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .join('\n');
}

function splitSentences(text) {
  return cleanCapturedText(text)
    .replace(/\s+/g, ' ')
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => sentence.trim())
    .filter(Boolean);
}

function truncateText(text, maxChars) {
  const clean = cleanCapturedText(text);
  if (clean.length <= maxChars) return clean;
  return `${clean.slice(0, maxChars).trim()}...`;
}

function summarizeCapture(text) {
  const sentences = splitSentences(text);
  if (!sentences.length) return 'No captured context yet.';
  return sentences.slice(0, 3).map((sentence) => `- ${truncateText(sentence, 220)}`).join('\n');
}

function extractUsefulLines(text, patterns, limit) {
  const lines = cleanCapturedText(text).split('\n');
  const matches = [];
  for (const line of lines) {
    const compact = line.trim();
    if (!compact || compact.length < 8) continue;
    if (patterns.some((pattern) => pattern.test(compact))) {
      matches.push(`- ${truncateText(compact, 180)}`);
    }
    if (matches.length >= limit) break;
  }
  return matches;
}

function fallbackList(text, label) {
  const summary = summarizeCapture(text);
  if (summary !== 'No captured context yet.') return summary;
  return `- ${label}`;
}

function buildHandoffMarkdown(context = {}) {
  const provider = context.provider || currentProviderName();
  const title = context.title || lastTabContext?.title || `${provider} session`;
  const url = context.url || lastTabContext?.url || '';
  const goal = newWorkflowGoal.value.trim() || context.goal || 'Continue this AI work without losing context';
  const captured = selectedTextPreview.value.trim() || context.latest_response || '';
  const manual = summaryInput.value.trim();
  const instruction = composeInstruction.value.trim();
  const worked = extractUsefulLines(captured, [/\b(worked|works|passed|pass|success|successful|fixed|resolved|confirmed|verified|green)\b/i], 5);
  const didNotWork = extractUsefulLines(captured, [/\b(failed|fail|error|blocked|not working|did not work|doesn't work|broken|404|500|timeout|cannot|can't)\b/i], 5);
  const alreadyTried = extractUsefulLines(captured, [/\b(tried|ran|tested|checked|attempted|used|opened|clicked|installed|configured|deployed|reloaded)\b/i], 6);
  const preserve = extractUsefulLines(captured, [/\b(important|remember|preserve|must|should|namespace|api key|url|domain|commit|version|path|file|command|decision|constraint)\b/i], 6);
  const openQuestions = extractUsefulLines(captured, [/\?|open question|unclear|todo|next|follow up|blocked/i], 4);
  const evidenceExcerpt = truncateText(captured, 700);
  const lines = [
    `# Metera Handoff - ${title}`,
    '',
    `- Provider: ${provider}`,
    `- Source: ${url || 'not recorded'}`,
    `- Namespace: ${namespaceInput.value.trim() || 'not set'}`,
    `- Created: ${nowIso()}`,
    '',
    '## Thread About',
    goal,
    '',
    '## What Worked',
    worked.length ? worked.join('\n') : fallbackList(captured, 'No confirmed working steps were identified.'),
    '',
    '## What Did Not Work',
    didNotWork.length ? didNotWork.join('\n') : '- No explicit failures were identified.',
    '',
    '## Already Tried',
    alreadyTried.length ? alreadyTried.join('\n') : '- No explicit attempts were identified.',
    '',
    '## Preserve',
    preserve.length ? preserve.join('\n') : fallbackList(captured, 'Keep the captured context and source URL/title available.'),
  ];
  if (openQuestions.length) lines.push('', '## Open Questions / Follow-ups', openQuestions.join('\n'));
  if (manual) lines.push('', '## Operator Notes', manual);
  lines.push(
    '',
    '## Next Best Step',
    instruction || `Continue from the preserved context and produce the next useful step for: ${goal}`,
    '',
    '## Prompt For Next LLM',
    `Continue from this handoff. Do not ask for details already listed. Do not repeat failed attempts. Do not restate the original thread. Start with the next best step for: ${goal}`,
    '',
    '## Evidence Excerpt',
    evidenceExcerpt || 'No evidence excerpt captured.',
    '',
    '## Metera Notes',
    '- This handoff is a compressed summary of user-approved visible page context.',
    '- It can be pasted into another LLM session for migration or continuation.',
  );
  return lines.join('\n');
}

function activeRetentionPolicy() {
  return captureRetentionPolicy.value || 'discard_after_save';
}

function localCaptureAreaFor(policy) {
  if (policy === 'discard_on_popup_close') return null;
  if (policy === 'discard_on_browser_close') return sessionStorageArea();
  return chrome.storage.local;
}

function localCaptureSummary(capture) {
  if (!capture) return 'No local capture is currently staged.';
  const mode = capture.captureMode || 'manual_summary';
  const state = capture.saveState || 'local_only';
  const length = capture.textLength || (capture.text || '').length;
  return `Local capture: ${state} | ${mode} | ${length} chars | retention=${capture.retentionPolicy}`;
}

async function persistLocalCapture(capture) {
  const policy = capture.retentionPolicy || activeRetentionPolicy();
  const area = localCaptureAreaFor(policy);
  if (!area) return;
  await storageSet(area, { [LOCAL_CAPTURE_KEY]: capture });
}

async function removePersistedLocalCapture() {
  await storageRemove(chrome.storage.local, [LOCAL_CAPTURE_KEY]);
  if (chrome.storage.session) {
    await storageRemove(chrome.storage.session, [LOCAL_CAPTURE_KEY]);
  }
}

async function stageLocalCapture({ text, captureMode, surface, sourceUrl, sourceTitle }) {
  const trimmed = text || '';
  const policy = activeRetentionPolicy();
  const capture = {
    captureId: `local_${Date.now()}`,
    captureMode,
    provider: targetSelect.value || 'generic',
    surface: surface || 'generic',
    sourceUrl: sourceUrl || lastTabContext?.url || '',
    sourceTitle: sourceTitle || lastTabContext?.title || '',
    capturedAt: new Date().toISOString(),
    text: trimmed,
    textLength: trimmed.length,
    retentionPolicy: policy,
    saveState: 'local_only',
  };
  selectedTextPreview.value = capture.text;
  lastCaptureMode = capture.captureMode;
  await removePersistedLocalCapture();
  await persistLocalCapture(capture);
  setStatus(localCaptureStatus, localCaptureSummary(capture));
  return capture;
}

async function restoreLocalCapturePreview() {
  const localCapture = (await storageGet(chrome.storage.local, [LOCAL_CAPTURE_KEY]))[LOCAL_CAPTURE_KEY];
  const sessionCapture = chrome.storage.session ? (await storageGet(chrome.storage.session, [LOCAL_CAPTURE_KEY]))[LOCAL_CAPTURE_KEY] : null;
  const capture = sessionCapture || localCapture;
  if (!capture || capture.saveState !== 'local_only') {
    setStatus(localCaptureStatus, localCaptureSummary(null));
    return;
  }
  selectedTextPreview.value = capture.text || '';
  lastCaptureMode = capture.captureMode || null;
  setStatus(localCaptureStatus, localCaptureSummary(capture));
}

async function clearLocalCapture(saveState = 'discarded') {
  const text = selectedTextPreview.value.trim();
  selectedTextPreview.value = '';
  lastCaptureMode = null;
  await removePersistedLocalCapture();
  setStatus(localCaptureStatus, text ? `Local capture ${saveState}.` : localCaptureSummary(null));
}

async function loadStateIntoUi() {
  const state = await getState();
  apiBaseInput.value = state.apiBase || 'https://api.getmetera.com';
  apiKeyInput.value = state.apiKey || '';
  namespaceInput.value = state.namespace || '';
  emailInput.value = state.email || '';
  workspaceIdInput.value = state.workspaceId || 'workspace_1';
  challengeIdInput.value = state.challengeId || '';
  verificationCodeInput.value = state.verificationCode || '';
  targetSelect.value = state.defaultTarget || 'chatgpt';
  modeSelect.value = state.composeMode || 'resume';
  composeInstruction.value = state.composeInstruction || '';
  newWorkflowGoal.value = state.newWorkflowGoal || '';
  handoffOutput.value = state[SESSION_CONTEXT_KEY]?.handoff_markdown || '';
  const retention = (await chrome.storage.local.get(['captureRetentionPolicy'])).captureRetentionPolicy;
  captureRetentionPolicy.value = retention || 'discard_after_save';
  useSelectedTextToggle.checked = state.useSelectedTextToggle !== false;
  const permissions = state.permissions || {};
  permInsert.checked = permissions.insert_restart_pack !== false;
  permSaveSummary.checked = permissions.save_conversation_summary !== false;
  permCaptureSelection.checked = permissions.capture_selected_response !== false;
  if (state.apiKey) setStatus(loginStatus, `Signed into Metera. Namespace: ${state.namespace || '(none)'}`);
  await loadPermissionHints();
  await restoreLocalCapturePreview();
  try {
    await refreshWorkflows({ preserveWorkflowId: state.workflowId || '' });
  } catch (error) {
    setStatus(handoffStatus, `Workflow list unavailable: ${formatError(error)}`);
    populateWorkflowSelect([]);
  }
  await refreshProviderStatus();
}

async function understandChat() {
  const tab = await getCurrentTab();
  lastTabContext = tab || lastTabContext;
  let inspection = null;
  let latest = null;
  try {
    inspection = await inspectPromptTarget();
    lastPromptInspection = inspection;
  } catch (error) {
    inspection = { ok: false, error: formatError(error) };
  }
  try {
    latest = await captureLatestResponse();
    if (latest?.text) {
      selectedTextPreview.value = latest.text;
      lastCaptureMode = latest.captureMode || 'latest_assistant_response';
    }
  } catch (error) {
    latest = { ok: false, error: formatError(error) };
  }
  const context = await saveSessionContext({
    provider: inspection?.surface || currentProviderName(),
    title: tab?.title || '',
    url: tab?.url || '',
    prompt_detected: !!inspection?.ok,
    latest_response: latest?.text || selectedTextPreview.value.trim() || '',
    latest_response_length: (latest?.text || '').length,
  });
  await refreshProviderStatus();
  const parts = [
    `Provider: ${context.provider || currentProviderName()}`,
    inspection?.ok ? 'Prompt target: found' : `Prompt target: ${inspection?.error || 'not found'}`,
    context.latest_response ? `Latest response: captured ${context.latest_response.length} chars` : 'Latest response: not captured yet',
  ];
  setStatus(sessionStatus, parts.join('\n'));
}

async function saveDirectBetaKey() {
  const apiBase = apiBaseInput.value.trim().replace(/\/+$/, '');
  const apiKey = apiKeyInput.value.trim();
  const namespace = namespaceInput.value.trim();
  if (!apiBase) throw new Error('Enter the Metera API base, for example https://api.getmetera.com.');
  if (!safeParseUrl(apiBase)) throw new Error('Metera API base must be a full URL, for example https://api.getmetera.com.');
  if (!apiKey) throw new Error('Paste the beta API key provided by Metera.');
  if (!namespace) throw new Error('Enter the namespace provided by Metera.');
  await saveState({ apiBase, apiKey, namespace, defaultTarget: targetSelect.value });
  setStatus(loginStatus, `Signed into Metera with beta key. Namespace: ${namespace}`);
  try {
    await refreshWorkflows();
  } catch (error) {
    setStatus(handoffStatus, `Signed in. Workflow list unavailable: ${formatError(error)}`);
    populateWorkflowSelect([]);
  }
}

async function requestLoginCode() {
  setStatus(loginStatus, 'Login codes are not enabled for Beta 001. Use "Sign in with beta key" with the API key and namespace provided by Metera.');
}

async function exchangeLoginCode() {
  setStatus(loginStatus, 'Exchange code is not used in Beta 001. Paste the beta API key and namespace, then click "Sign in with beta key".');
}

async function savePermissions() {
  const permissions = selectedPermissionState();
  await saveState({ permissions });
  const selected = Object.values(permissions).filter(Boolean).length;
  setStatus(permissionStatus, selected ? `Saved ${selected} permission setting(s) locally.` : 'Saved. No action permissions are enabled yet.');
}
function populateWorkflowSelect(workflows, selectedId = '') {
  workflowSelect.innerHTML = '';
  const empty = document.createElement('option');
  empty.value = '';
  empty.textContent = '(none selected)';
  workflowSelect.appendChild(empty);
  for (const workflow of workflows) {
    const option = document.createElement('option');
    option.value = workflow.id;
    option.textContent = `${workflow.goal} [${isLocalWorkflowId(workflow.id) ? 'local beta' : workflow.id}]`;
    workflowSelect.appendChild(option);
  }
  if (selectedId && workflows.some((workflow) => workflow.id === selectedId)) {
    workflowSelect.value = selectedId;
  }
}
async function loadPermissionHints() { const state = await getState(); if (!state.apiBase) return; try { const body = await fetchJson(`${state.apiBase}/v1/browser-bridge/permissions`); const byId = Object.fromEntries((body.permissions || []).map((item) => [item.id, item])); permInsert.title = byId.insert_restart_pack?.description || ''; permSaveSummary.title = byId.save_conversation_summary?.description || ''; permCaptureSelection.title = byId.capture_selected_response?.description || ''; } catch (error) { setStatus(permissionStatus, `Could not load permission hints: ${error.message}`); } }

async function refreshWorkflows({ preserveWorkflowId } = {}) {
  const state = await getState();
  const localWorkflows = await getLocalWorkflows();
  if (!state.apiBase || !state.apiKey) {
    populateWorkflowSelect(localWorkflows, preserveWorkflowId || state.workflowId || '');
    setStatus(handoffStatus, localWorkflows.length ? `Loaded ${localWorkflows.length} local beta workflow(s). Sign in to sync later.` : 'No workflows yet. Type a goal and click Create fresh workflow.');
    return;
  }
  let remoteWorkflows = [];
  let remoteUnavailable = false;
  try {
    remoteWorkflows = await fetchJson(`${state.apiBase}/v1/account/workflows`, { headers: authHeaders(state) });
  } catch (error) {
    remoteUnavailable = true;
  }
  const workflows = [...remoteWorkflows, ...localWorkflows];
  const selectedId = preserveWorkflowId || workflowSelect.value || state.workflowId || '';
  populateWorkflowSelect(workflows, selectedId);
  await saveState({ workflowId: workflowSelect.value || '' });
  if (remoteUnavailable) {
    setStatus(handoffStatus, workflows.length ? `Loaded ${workflows.length} local beta workflow(s). Cloud workflow sync is not enabled on this API yet.` : 'Cloud workflow sync is not enabled on this API yet. Type a goal and click Create fresh workflow to continue locally.');
  } else {
    setStatus(handoffStatus, workflows.length ? `Loaded ${workflows.length} workflow(s).` : 'No workflows were available. Create a fresh workflow to start clean.');
  }
  if (workflowSelect.value) {
    await refreshWorkflowIntelligence().catch((error) => setStatus(handoffStatus, `Workflow selected. Intelligence unavailable: ${formatError(error)}`));
  } else {
    workflowStatus.innerHTML = '';
  }
}

async function getCurrentTab() {
  return new Promise((resolve) => chrome.runtime.sendMessage({ type: 'metera:get-tab-context' }, (response) => resolve(response?.tab || null)));
}
async function getRuntimeDiagnostics() {
  return new Promise((resolve) => chrome.runtime.sendMessage({ type: 'metera:get-runtime-diagnostics' }, (response) => resolve(Array.isArray(response?.events) ? response.events : [])));
}
async function getSelection() {
  return new Promise((resolve, reject) => chrome.runtime.sendMessage({ type: 'metera:get-selection' }, (response) => {
    if (!response?.ok) return reject(Object.assign(new Error(response?.error || 'Selection capture failed.'), { diagnostics: response?.diagnostics }));
    resolve(response);
  }));
}
async function captureLatestResponse() {
  return new Promise((resolve, reject) => chrome.runtime.sendMessage({ type: 'metera:capture-latest-response' }, (response) => {
    if (!response?.ok) return reject(Object.assign(new Error(response?.error || 'Latest assistant response capture failed.'), { diagnostics: response?.diagnostics }));
    resolve(response);
  }));
}
async function injectIntoPage(text) {
  return new Promise((resolve, reject) => chrome.runtime.sendMessage({ type: 'metera:inject-text', text }, (response) => {
    if (!response?.ok) return reject(Object.assign(new Error(response?.error || 'Prompt injection failed.'), { diagnostics: response?.diagnostics }));
    resolve(response);
  }));
}
async function inspectPromptTarget() {
  return new Promise((resolve, reject) => chrome.runtime.sendMessage({ type: 'metera:inspect-prompt-target' }, (response) => {
    if (!response?.ok) return reject(Object.assign(new Error(response?.error || 'Prompt inspection failed.'), { diagnostics: response?.diagnostics }));
    resolve(response);
  }));
}

function renderPills(node, items) {
  node.innerHTML = '';
  for (const item of items) {
    const div = document.createElement('div');
    div.className = 'pill';
    div.textContent = item;
    node.appendChild(div);
  }
}

async function refreshProviderStatus() {
  lastTabContext = await getCurrentTab();
  const diagnostics = await getRuntimeDiagnostics();
  const inspectionLines = [];
  const pills = [];
  const url = safeParseUrl(lastTabContext?.url || '');
  pills.push(`Tab: ${lastTabContext?.title || '(no active tab)'}`);
  pills.push(`Surface: ${url?.hostname || 'unknown'}`);
  if (lastPromptInspection?.surface) pills.push(`Detected target: ${lastPromptInspection.surface}`);
  if (lastCaptureMode) pills.push(`Last capture: ${lastCaptureMode}`);
  renderPills(providerStatus, pills);

  if (lastPromptInspection?.diagnostics?.candidates?.length) {
    inspectionLines.push(`Prompt candidates: ${lastPromptInspection.diagnostics.candidates.map((item) => `${item.tagName}${item.id ? `#${item.id}` : ''}@${item.score}`).join(', ')}`);
  }
  const visibleDiagnostics = diagnostics.filter((event) => event.level === 'error' || !event.recovery);
  if (visibleDiagnostics.length) {
    const recent = visibleDiagnostics.slice(0, 4).map((event) => `${event.at} ${event.action} ${event.level}${event.error ? ` | ${event.error}` : ''}`);
    inspectionLines.push('Recent runtime events:');
    inspectionLines.push(...recent);
  } else {
    inspectionLines.push('No unrecovered runtime errors recorded.');
  }
  diagnosticsOutput.textContent = inspectionLines.join('\n');
}

async function refreshWorkflowIntelligence() {
  const state = await getState();
  if (!workflowSelect.value) { workflowStatus.innerHTML = ''; return; }
  if (isLocalWorkflowId(workflowSelect.value)) {
    const workflows = await getLocalWorkflows();
    const workflow = workflows.find((item) => item.id === workflowSelect.value);
    const captures = (await getLocalCaptures()).filter((item) => item.workflow_id === workflowSelect.value);
    renderPills(workflowStatus, [
      'Freshness: local beta',
      `Goal: ${workflow?.goal || '(unknown)'}`,
      `Recent captures: ${captures.length}`,
      'Sync: not yet sent to Metera cloud',
    ]);
    return;
  }
  const body = await fetchJson(`${state.apiBase}/v1/workflows/${workflowSelect.value}/intelligence`, { headers: authHeaders(state) });
  const lines = [
    `Freshness: ${body.staleness_state}`,
    `Current focus: ${body.current_focus || '(none)'}`,
    `Next action: ${body.next_action || '(none)'}`,
    `Blockers: ${body.blocker_count}`,
    `Recent captures: ${body.recent_capture_count}`,
    `Active context packs: ${(body.active_context_pack_ids || []).length}`,
  ];
  renderPills(workflowStatus, lines);
  if (body.warnings?.length) {
    setStatus(handoffStatus, `Workflow loaded with warnings: ${body.warnings.join(' | ')}`);
  }
}

function buildLocalPrompt({ workflow, instruction, selectedText }) {
  const parts = [
    `You are continuing this Metera workflow: ${workflow.goal}`,
    '',
    `Mode: ${modeSelect.value || 'resume'}`,
  ];
  if (instruction) parts.push('', `Current instruction: ${instruction}`);
  if (selectedText) parts.push('', 'Relevant selected context:', selectedText);
  parts.push('', 'Use the existing context, avoid repeating setup already captured, and give the next useful action.');
  return parts.join('\n');
}

function tracePrefix(item) {
  if (item.kind === 'context_pack') return 'active context pack';
  if (item.kind === 'capture') return item.reason?.includes('duplicate') ? 'duplicate capture' : 'recent capture';
  return item.kind;
}

function renderTrace(result) {
  sourceTraceOutput.innerHTML = '';
  const warnings = (result.warnings || []).map((item) => `Warning: ${item}`);
  const sources = (result.included_sources || []).map((item) => `+ ${tracePrefix(item)}: ${item.title} (${item.reason || 'included'})`);
  const omitted = (result.omitted_sources || []).map((item) => `- ${tracePrefix(item)}: ${item.title} (${item.reason || 'omitted'})`);
  const workflowSummary = result.workflow_summary
    ? [`Goal: ${result.workflow_summary.goal}`, `Next action: ${result.workflow_summary.next_action || '(none)'}`]
    : [];
  sourceTraceOutput.textContent = [...workflowSummary, ...warnings, ...sources, ...omitted].join('\n');
}

async function composePrompt(previewOnly) {
  const state = await getState();
  if (!workflowSelect.value) throw new Error('Choose or create a workflow first.');
  const selectedTextPayload = useSelectedTextToggle.checked ? await getSelection().catch(() => null) : null;
  const selectedText = selectedTextPayload?.selectedText || '';
  if (selectedText) selectedTextPreview.value = selectedText;
  if (isLocalWorkflowId(workflowSelect.value)) {
    const workflow = (await getLocalWorkflows()).find((item) => item.id === workflowSelect.value);
    const content = buildLocalPrompt({ workflow: workflow || { goal: newWorkflowGoal.value.trim() || defaultWorkflowGoal() }, instruction: composeInstruction.value.trim(), selectedText });
    restartPackOutput.value = content;
    sourceTraceOutput.textContent = 'Local beta compose\n+ workflow goal\n+ optional instruction\n+ optional selected page text';
    setStatus(handoffStatus, previewOnly ? 'Local compose preview loaded.' : 'Local composed prompt ready.');
    await saveState({ workflowId: workflowSelect.value, defaultTarget: targetSelect.value, composeMode: modeSelect.value, composeInstruction: composeInstruction.value, useSelectedTextToggle: useSelectedTextToggle.checked });
    return { content, local: true };
  }
  const route = previewOnly ? WORKFLOW_COMPOSE_PREVIEW_ROUTE : WORKFLOW_COMPOSE_ROUTE;
  const body = await fetchJson(`${state.apiBase}/v1/workflows/${workflowSelect.value}${route}`, {
    method: 'POST', headers: authHeaders(state), body: JSON.stringify({ target: targetSelect.value, mode: modeSelect.value, instruction: composeInstruction.value.trim() || undefined, selected_text: selectedText || undefined })
  });
  restartPackOutput.value = body.content;
  renderTrace(body);
  setStatus(handoffStatus, previewOnly ? 'Compose preview loaded.' : 'Composed prompt ready.');
  await saveState({ workflowId: workflowSelect.value, defaultTarget: targetSelect.value, composeMode: modeSelect.value, composeInstruction: composeInstruction.value, useSelectedTextToggle: useSelectedTextToggle.checked });
  return body;
}

async function composeAndInsert() {
  const state = await getState();
  if (!(state.permissions || {}).insert_restart_pack) throw new Error('Enable the insert permission first.');
  const result = await composePrompt(false);
  const injection = await injectIntoPage(result.content);
  setStatus(handoffStatus, `Inserted the ${targetSelect.value} composed prompt using ${injection.mode} on ${injection.surface}${injection.fallback ? ' via fallback recovery' : ''}.`);
  await refreshProviderStatus();
}

async function createFreshWorkflow() {
  const state = await getState();
  const goal = newWorkflowGoal.value.trim() || defaultWorkflowGoal();
  if (!goal) throw new Error('Type a workflow goal first.');
  let body = null;
  if (state.apiBase && state.apiKey) {
    try {
      body = await fetchJson(`${state.apiBase}/v1/workflows`, {
        method: 'POST', headers: authHeaders(state), body: JSON.stringify({ goal, metadata: { created_by: 'browser_extension', fresh_workflow: true, target_hint: targetSelect.value } })
      });
    } catch (error) {
      body = null;
    }
  }
  if (!body) {
    body = {
      id: `local_${Date.now()}`,
      goal,
      status: 'local_beta',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      target_hint: targetSelect.value,
    };
    const workflows = await getLocalWorkflows();
    await saveLocalWorkflows([body, ...workflows.filter((item) => item.id !== body.id)]);
  }
  newWorkflowGoal.value = body.goal;
  await saveState({ workflowId: body.id, newWorkflowGoal: newWorkflowGoal.value });
  await refreshWorkflows({ preserveWorkflowId: body.id });
  setStatus(handoffStatus, isLocalWorkflowId(body.id) ? `Created local beta workflow. Compose and capture are now enabled.` : `Created fresh workflow ${body.id}. You are now starting clean.`);
}

async function clearWorkflowSelection() {
  workflowSelect.value = '';
  workflowStatus.innerHTML = '';
  await saveState({ workflowId: '' });
  setStatus(handoffStatus, 'Workflow selection cleared. Compose is disabled until you choose or create a workflow.');
}

async function saveStructuredCapture() {
  const state = await getState();
  if (!(state.permissions || {}).save_conversation_summary && !(state.permissions || {}).capture_selected_response) throw new Error('Enable a save or capture permission first.');
  if (!workflowSelect.value) {
    await createFreshWorkflow();
  }
  const tab = await getCurrentTab();
  const text = summaryInput.value.trim() || selectedTextPreview.value.trim();
  if (!text) throw new Error('Capture selected text, capture the latest response, or provide a summary first.');
  if (lastCaptureMode === 'selected_response' && text.length > LONG_SELECTED_CAPTURE_THRESHOLD && !window.confirm('This selected/thread capture is long. Save it to the workflow anyway?')) {
    throw new Error('Long selected/thread capture was not saved.');
  }
  let savedRemote = false;
  let captureId = `local_capture_${Date.now()}`;
  let warningText = '';
  if (!isLocalWorkflowId(workflowSelect.value) && state.apiBase && state.apiKey) {
    try {
      const body = await fetchJson(`${state.apiBase}/v1/workflows/${workflowSelect.value}/captures`, {
        method: 'POST', headers: authHeaders(state), body: JSON.stringify({ target: targetSelect.value, title: 'Browser workflow capture', content: text, selected_text: selectedTextPreview.value.trim() || undefined, source_surface: 'browser_extension', page_url: tab?.url, page_title: tab?.title, classifications: selectedClassifications(), metadata: { capture_mode: lastCaptureMode || 'manual_summary', local_capture_retention: activeRetentionPolicy(), local_capture_state: 'saved_to_workflow' } })
      });
      savedRemote = true;
      captureId = body.capture_id;
      warningText = (body.warnings || []).length ? ` Warnings: ${body.warnings.join(' | ')}` : '';
    } catch (error) {
      savedRemote = false;
    }
  }
  if (!savedRemote) {
    const captures = await getLocalCaptures();
    await saveLocalCaptures([
      {
        id: captureId,
        workflow_id: workflowSelect.value,
        target: targetSelect.value,
        text,
        selected_text: selectedTextPreview.value.trim() || '',
        classifications: selectedClassifications(),
        page_url: tab?.url || '',
        page_title: tab?.title || '',
        created_at: new Date().toISOString(),
      },
      ...captures,
    ]);
  }
  setStatus(captureStatus, savedRemote ? `Saved classified capture ${captureId}.${warningText}` : `Saved capture locally to this beta workflow. Cloud workflow sync is not enabled on this API yet.`);
  setStatus(localCaptureStatus, `Local capture ${savedRemote ? 'saved_to_workflow' : 'saved_locally'}. retention=${activeRetentionPolicy()}`);
  if (activeRetentionPolicy() === 'discard_after_save') {
    await clearLocalCapture('saved_to_workflow and deleted locally');
  }
  await refreshWorkflowIntelligence().catch(() => {});
}

async function captureSelectedResponse() {
  const payload = await getSelection();
  if (!payload.selectedText) throw new Error('Select response text in the current page first.');
  const capture = await stageLocalCapture({ text: payload.selectedText, captureMode: 'selected_response', surface: payload.surface });
  applyClassifications(['reusable_snippet', 'evidence']);
  const warning = capture.textLength > LONG_SELECTED_CAPTURE_THRESHOLD ? ' Long selected/thread capture: review before saving.' : '';
  setStatus(captureStatus, `Selected/thread text captured locally.${warning}`);
  await saveSessionContext({ provider: payload.surface || currentProviderName(), latest_response: payload.selectedText, latest_response_length: payload.selectedText.length, title: lastTabContext?.title || '', url: lastTabContext?.url || '' });
  setStatus(sessionStatus, `Captured selected text (${payload.selectedText.length} chars). Generate a handoff note next.`);
  await refreshProviderStatus();
}

async function captureLatestAssistantResponse() {
  const payload = await captureLatestResponse();
  if (!payload.text) throw new Error('No latest assistant response was found.');
  await stageLocalCapture({ text: payload.text, captureMode: payload.captureMode || 'latest_assistant_response', surface: payload.surface });
  applyClassifications(['summary', 'decision', 'next_action']);
  setStatus(captureStatus, `Latest assistant response captured locally from ${payload.surface}. Review before saving to Metera.`);
  await saveSessionContext({ provider: payload.surface || currentProviderName(), latest_response: payload.text, latest_response_length: payload.text.length, title: lastTabContext?.title || '', url: lastTabContext?.url || '' });
  setStatus(sessionStatus, `Captured latest response (${payload.text.length} chars). Generate a handoff note next.`);
  await refreshProviderStatus();
}

async function generateHandoffNote() {
  let context = await getSessionContext();
  if (!selectedTextPreview.value.trim() && context.latest_response) {
    selectedTextPreview.value = context.latest_response;
  }
  if (!selectedTextPreview.value.trim()) {
    const selection = await getSelection().catch(() => null);
    if (selection?.selectedText) {
      await stageLocalCapture({ text: selection.selectedText, captureMode: 'selected_response', surface: selection.surface });
      context = await saveSessionContext({ provider: selection.surface || currentProviderName(), latest_response: selection.selectedText, latest_response_length: selection.selectedText.length, title: lastTabContext?.title || '', url: lastTabContext?.url || '' });
    }
  }
  const markdown = buildHandoffMarkdown(context);
  handoffOutput.value = markdown;
  await saveSessionContext({ handoff_markdown: markdown, goal: newWorkflowGoal.value.trim() });
  setStatus(sessionStatus, 'Handoff note generated. You can export it or insert it into the current prompt.');
}

async function exportContextDocument() {
  let markdown = handoffOutput.value.trim();
  if (!markdown) {
    await generateHandoffNote();
    markdown = handoffOutput.value.trim();
  }
  const context = await getSessionContext();
  const filename = `metera-handoff-${slugPart(context.provider || currentProviderName())}-${new Date().toISOString().slice(0, 10)}.md`;
  const blob = new Blob([markdown + '\n'], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  setStatus(sessionStatus, `Exported ${filename}`);
}

async function insertHandoffIntoPrompt() {
  const state = await getState();
  if (!(state.permissions || {}).insert_restart_pack) throw new Error('Prompt insertion is disabled in Advanced permissions.');
  let markdown = handoffOutput.value.trim();
  if (!markdown) {
    await generateHandoffNote();
    markdown = handoffOutput.value.trim();
  }
  const injection = await injectIntoPage(markdown);
  setStatus(sessionStatus, `Inserted handoff into ${injection.surface || currentProviderName()} prompt. Review it before sending.`);
  await refreshProviderStatus();
}

saveDirectKeyButton.addEventListener('click', async () => { try { await saveDirectBetaKey(); } catch (error) { setStatus(loginStatus, formatError(error)); } });
understandChatButton.addEventListener('click', async () => { try { await understandChat(); } catch (error) { setStatus(sessionStatus, formatError(error)); } });
generateHandoffButton.addEventListener('click', async () => { try { await generateHandoffNote(); } catch (error) { setStatus(sessionStatus, formatError(error)); } });
exportContextButton.addEventListener('click', async () => { try { await exportContextDocument(); } catch (error) { setStatus(sessionStatus, formatError(error)); } });
insertHandoffButton.addEventListener('click', async () => { try { await insertHandoffIntoPrompt(); } catch (error) { setStatus(sessionStatus, formatError(error)); } });
requestCodeButton.addEventListener('click', async () => { try { await requestLoginCode(); } catch (error) { setStatus(loginStatus, formatError(error)); } });
exchangeCodeButton.addEventListener('click', async () => { try { await exchangeLoginCode(); } catch (error) { setStatus(loginStatus, formatError(error)); } });
savePermissionsButton.addEventListener('click', async () => { await savePermissions(); });
refreshWorkflowsButton.addEventListener('click', async () => { try { await refreshWorkflows(); } catch (error) { setStatus(handoffStatus, formatError(error)); } });
workflowSelect.addEventListener('change', async () => { try { await saveState({ workflowId: workflowSelect.value || '' }); await refreshWorkflowIntelligence(); } catch (error) { setStatus(handoffStatus, formatError(error)); } });
createWorkflowButton.addEventListener('click', async () => { try { await createFreshWorkflow(); } catch (error) { setStatus(handoffStatus, formatError(error)); } });
clearWorkflowSelectionButton.addEventListener('click', async () => { try { await clearWorkflowSelection(); } catch (error) { setStatus(handoffStatus, formatError(error)); } });
composePreviewButton.addEventListener('click', async () => { try { await composePrompt(true); } catch (error) { setStatus(handoffStatus, formatError(error)); } });
composeInsertButton.addEventListener('click', async () => { try { await composeAndInsert(); } catch (error) { setStatus(handoffStatus, formatError(error)); } });
inspectPromptButton.addEventListener('click', async () => {
  try {
    const result = await inspectPromptTarget();
    lastPromptInspection = result;
    setStatus(handoffStatus, `Detected ${result.surface} prompt target: ${result.target.tagName}${result.target.id ? `#${result.target.id}` : ''}${result.target.role ? ` role=${result.target.role}` : ''}`);
    await refreshProviderStatus();
  } catch (error) {
    setStatus(handoffStatus, formatError(error));
    await refreshProviderStatus();
  }
});
captureSelectionButton.addEventListener('click', async () => { try { await captureSelectedResponse(); } catch (error) { setStatus(captureStatus, formatError(error)); } });
captureLatestResponseButton.addEventListener('click', async () => { try { await captureLatestAssistantResponse(); } catch (error) { setStatus(captureStatus, formatError(error)); } });
clearLocalCaptureButton.addEventListener('click', async () => { try { await clearLocalCapture(); setStatus(captureStatus, 'Local capture cleared.'); } catch (error) { setStatus(captureStatus, formatError(error)); } });
saveSummaryButton.addEventListener('click', async () => { try { await saveStructuredCapture(); } catch (error) { setStatus(captureStatus, formatError(error)); } });
[targetSelect, modeSelect, composeInstruction, useSelectedTextToggle, newWorkflowGoal].forEach((node) => node.addEventListener('change', async () => { await saveState({ defaultTarget: targetSelect.value, composeMode: modeSelect.value, composeInstruction: composeInstruction.value, useSelectedTextToggle: useSelectedTextToggle.checked, newWorkflowGoal: newWorkflowGoal.value }); }));
captureRetentionPolicy.addEventListener('change', async () => {
  await chrome.storage.local.set({ captureRetentionPolicy: activeRetentionPolicy() });
  const text = selectedTextPreview.value.trim();
  if (text) {
    await stageLocalCapture({ text, captureMode: lastCaptureMode || 'manual_summary' });
  }
});

loadStateIntoUi();
