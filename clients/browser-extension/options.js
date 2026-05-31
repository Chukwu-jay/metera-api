const apiBaseInput = document.getElementById('apiBase');
const workspaceIdInput = document.getElementById('workspaceId');
const defaultTargetSelect = document.getElementById('defaultTarget');
const saveButton = document.getElementById('saveOptionsButton');
const statusNode = document.getElementById('optionsStatus');

function setStatus(message) {
  statusNode.textContent = message;
}

async function loadOptions() {
  const state = await chrome.storage.local.get(['apiBase', 'workspaceId', 'defaultTarget']);
  apiBaseInput.value = state.apiBase || 'http://localhost:8000';
  workspaceIdInput.value = state.workspaceId || 'workspace_1';
  defaultTargetSelect.value = state.defaultTarget || 'chatgpt';
}

saveButton.addEventListener('click', async () => {
  await chrome.storage.local.set({
    apiBase: apiBaseInput.value.trim(),
    workspaceId: workspaceIdInput.value.trim(),
    defaultTarget: defaultTargetSelect.value
  });
  setStatus('Saved extension defaults.');
});

loadOptions();
