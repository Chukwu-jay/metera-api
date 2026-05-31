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
const LONG_SELECTED_CAPTURE_THRESHOLD = 6000;

let lastPromptInspection = null;
let lastTabContext = null;
let lastCaptureMode = null;

function setStatus(node, message) { node.textContent = message; }
async function getState() { return chrome.storage.local.get(['apiBase', 'email', 'workspaceId', 'challengeId', 'verificationCode', 'apiKey', 'namespace', 'defaultTarget', 'workflowId', 'composeMode', 'composeInstruction', 'newWorkflowGoal', 'useSelectedTextToggle', 'permissions']); }
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
  const retention = (await chrome.storage.local.get(['captureRetentionPolicy'])).captureRetentionPolicy;
  captureRetentionPolicy.value = retention || 'discard_after_save';
  useSelectedTextToggle.checked = state.useSelectedTextToggle !== false;
  const permissions = state.permissions || {};
  permInsert.checked = !!permissions.insert_restart_pack;
  permSaveSummary.checked = !!permissions.save_conversation_summary;
  permCaptureSelection.checked = !!permissions.capture_selected_response;
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
  const apiBase = apiBaseInput.value.trim();
  const email = emailInput.value.trim();
  const workspaceId = workspaceIdInput.value.trim();
  await saveState({ apiBase, email, workspaceId });
  const body = await fetchJson(`${apiBase}/v1/auth/login-code/start`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email, workspace_id: workspaceId, display_name: 'Browser Bridge Login' }) });
  challengeIdInput.value = body.challenge_id;
  verificationCodeInput.value = body.verification_code || '';
  await saveState({ challengeId: body.challenge_id, verificationCode: body.verification_code || '' });
  setStatus(loginStatus, `Login code issued. Challenge: ${body.challenge_id}`);
}

async function exchangeLoginCode() {
  const apiBase = apiBaseInput.value.trim();
  const body = await fetchJson(`${apiBase}/v1/auth/login-code/exchange`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ challenge_id: challengeIdInput.value.trim(), verification_code: verificationCodeInput.value.trim() }) });
  await saveState({ apiBase, apiKey: body.api_key.plaintext_api_key, namespace: body.bootstrap.recommended_namespace, challengeId: challengeIdInput.value.trim(), verificationCode: verificationCodeInput.value.trim(), defaultTarget: targetSelect.value });
  apiKeyInput.value = body.api_key.plaintext_api_key;
  namespaceInput.value = body.bootstrap.recommended_namespace || '';
  setStatus(loginStatus, `Signed in as ${body.account.email}. Namespace: ${body.bootstrap.recommended_namespace}`);
  await refreshWorkflows();
}

async function savePermissions() { await saveState({ permissions: selectedPermissionState() }); setStatus(permissionStatus, 'Saved per-action permissions locally.'); }
function populateWorkflowSelect(workflows, selectedId = '') {
  workflowSelect.innerHTML = '';
  const empty = document.createElement('option');
  empty.value = '';
  empty.textContent = '(none selected)';
  workflowSelect.appendChild(empty);
  for (const workflow of workflows) {
    const option = document.createElement('option');
    option.value = workflow.id;
    option.textContent = `${workflow.goal} [${workflow.id}]`;
    workflowSelect.appendChild(option);
  }
  if (selectedId && workflows.some((workflow) => workflow.id === selectedId)) {
    workflowSelect.value = selectedId;
  }
}
async function loadPermissionHints() { const state = await getState(); if (!state.apiBase) return; try { const body = await fetchJson(`${state.apiBase}/v1/browser-bridge/permissions`); const byId = Object.fromEntries((body.permissions || []).map((item) => [item.id, item])); permInsert.title = byId.insert_restart_pack?.description || ''; permSaveSummary.title = byId.save_conversation_summary?.description || ''; permCaptureSelection.title = byId.capture_selected_response?.description || ''; } catch (error) { setStatus(permissionStatus, `Could not load permission hints: ${error.message}`); } }

async function refreshWorkflows({ preserveWorkflowId } = {}) {
  const state = await getState();
  if (!state.apiBase || !state.apiKey) { populateWorkflowSelect([]); return; }
  const workflows = await fetchJson(`${state.apiBase}/v1/account/workflows`, { headers: authHeaders(state) });
  const selectedId = preserveWorkflowId || workflowSelect.value || state.workflowId || '';
  populateWorkflowSelect(workflows, selectedId);
  await saveState({ workflowId: workflowSelect.value || '' });
  setStatus(handoffStatus, workflows.length ? `Loaded ${workflows.length} workflow(s).` : 'No workflows were available. Create a fresh workflow to start clean.');
  if (workflowSelect.value) {
    await refreshWorkflowIntelligence();
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
  if (diagnostics.length) {
    const recent = diagnostics.slice(0, 4).map((event) => `${event.at} ${event.action} ${event.level}${event.recovery ? ` -> ${event.recovery}` : ''}${event.error ? ` | ${event.error}` : ''}`);
    inspectionLines.push('Recent runtime events:');
    inspectionLines.push(...recent);
  } else {
    inspectionLines.push('No runtime errors recorded yet.');
  }
  diagnosticsOutput.textContent = inspectionLines.join('\n');
}

async function refreshWorkflowIntelligence() {
  const state = await getState();
  if (!workflowSelect.value) { workflowStatus.innerHTML = ''; return; }
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
  const body = await fetchJson(`${state.apiBase}/v1/workflows`, {
    method: 'POST', headers: authHeaders(state), body: JSON.stringify({ goal, metadata: { created_by: 'browser_extension', fresh_workflow: true, target_hint: targetSelect.value } })
  });
  newWorkflowGoal.value = body.goal;
  await saveState({ workflowId: body.id, newWorkflowGoal: newWorkflowGoal.value });
  await refreshWorkflows({ preserveWorkflowId: body.id });
  setStatus(handoffStatus, `Created fresh workflow ${body.id}. You are now starting clean.`);
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
  if (!workflowSelect.value) throw new Error('Choose or create a workflow first.');
  const tab = await getCurrentTab();
  const text = summaryInput.value.trim() || selectedTextPreview.value.trim();
  if (!text) throw new Error('Capture selected text, capture the latest response, or provide a summary first.');
  if (lastCaptureMode === 'selected_response' && text.length > LONG_SELECTED_CAPTURE_THRESHOLD && !window.confirm('This selected/thread capture is long. Save it to the workflow anyway?')) {
    throw new Error('Long selected/thread capture was not saved.');
  }
  const body = await fetchJson(`${state.apiBase}/v1/workflows/${workflowSelect.value}/captures`, {
    method: 'POST', headers: authHeaders(state), body: JSON.stringify({ target: targetSelect.value, title: 'Browser workflow capture', content: text, selected_text: selectedTextPreview.value.trim() || undefined, source_surface: 'browser_extension', page_url: tab?.url, page_title: tab?.title, classifications: selectedClassifications(), metadata: { capture_mode: lastCaptureMode || 'manual_summary', local_capture_retention: activeRetentionPolicy(), local_capture_state: 'saved_to_workflow' } })
  });
  const warningText = (body.warnings || []).length ? ` Warnings: ${body.warnings.join(' | ')}` : '';
  setStatus(captureStatus, `Saved classified capture ${body.capture_id}.${warningText}`);
  setStatus(localCaptureStatus, `Local capture saved_to_workflow. retention=${activeRetentionPolicy()}`);
  if (activeRetentionPolicy() === 'discard_after_save') {
    await clearLocalCapture('saved_to_workflow and deleted locally');
  }
  await refreshWorkflowIntelligence();
}

async function captureSelectedResponse() {
  const payload = await getSelection();
  if (!payload.selectedText) throw new Error('Select response text in the current page first.');
  const capture = await stageLocalCapture({ text: payload.selectedText, captureMode: 'selected_response', surface: payload.surface });
  applyClassifications(['reusable_snippet', 'evidence']);
  const warning = capture.textLength > LONG_SELECTED_CAPTURE_THRESHOLD ? ' Long selected/thread capture: review before saving.' : '';
  setStatus(captureStatus, `Selected/thread text captured locally.${warning}`);
  await refreshProviderStatus();
}

async function captureLatestAssistantResponse() {
  const payload = await captureLatestResponse();
  if (!payload.text) throw new Error('No latest assistant response was found.');
  await stageLocalCapture({ text: payload.text, captureMode: payload.captureMode || 'latest_assistant_response', surface: payload.surface });
  applyClassifications(['summary', 'decision', 'next_action']);
  setStatus(captureStatus, `Latest assistant response captured locally from ${payload.surface}. Review before saving to Metera.`);
  await refreshProviderStatus();
}

saveDirectKeyButton.addEventListener('click', async () => { try { await saveDirectBetaKey(); } catch (error) { setStatus(loginStatus, formatError(error)); } });
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
