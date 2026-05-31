chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.get(["permissions"], (items) => {
    if (items.permissions) {
      return;
    }
    chrome.storage.local.set({
      permissions: {
        insert_restart_pack: false,
        save_conversation_summary: false,
        capture_selected_response: false
      }
    });
  });
});

function rememberRuntimeEvent(entry) {
  chrome.storage.local.get(["runtimeDiagnostics"], (items) => {
    const events = Array.isArray(items.runtimeDiagnostics) ? items.runtimeDiagnostics : [];
    const next = [{ at: new Date().toISOString(), ...entry }, ...events].slice(0, 20);
    chrome.storage.local.set({ runtimeDiagnostics: next });
  });
}

function withTargetTab(sender, explicitTabId, onTab, onMissing) {
  const directTabId = sender.tab?.id ?? explicitTabId;
  if (directTabId) {
    onTab(directTabId);
    return true;
  }
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const tab = tabs[0];
    if (!tab?.id) {
      onMissing();
      return;
    }
    onTab(tab.id);
  });
  return true;
}

function isMissingReceiverError(message) {
  const text = String(message || "").toLowerCase();
  return text.includes("receiving end does not exist")
    || text.includes("message channel closed")
    || text.includes("no receiver")
    || text.includes("could not establish connection");
}

function executeInTab(tabId, func, args, sendResponse, fallbackLabel) {
  chrome.scripting.executeScript(
    {
      target: { tabId },
      func,
      args
    },
    (results) => {
      if (chrome.runtime.lastError) {
        const error = `${fallbackLabel} fallback failed: ${chrome.runtime.lastError.message}`;
        rememberRuntimeEvent({ level: 'error', action: fallbackLabel, path: 'scripting.executeScript', tabId, error });
        sendResponse({
          ok: false,
          error,
          diagnostics: { tabId, path: "scripting.executeScript", fallbackLabel }
        });
        return;
      }
      const result = results?.[0]?.result;
      rememberRuntimeEvent({ level: 'info', action: fallbackLabel, path: 'scripting.executeScript', tabId, ok: !!result?.ok });
      sendResponse(result || {
        ok: false,
        error: `${fallbackLabel} fallback returned no result.`,
        diagnostics: { tabId, path: "scripting.executeScript", fallbackLabel }
      });
    }
  );
}

function inspectPromptTargetInPage() {
  const api = globalThis.MeteraPageAdapters;
  if (api?.inspectPromptTarget) {
    const inspection = api.inspectPromptTarget(document, window.location);
    if (!inspection?.ok || !inspection.targetNode) {
      return { ok: false, surface: api.detectSurface(window.location), error: inspection?.error || 'No prompt target detected.', diagnostics: inspection?.diagnostics || null };
    }
    const target = inspection.targetNode;
    return {
      ok: true,
      surface: api.detectSurface(window.location),
      target: {
        tagName: target.tagName,
        id: target.id || '',
        role: target.getAttribute?.('role') || '',
        contentEditable: !!target.isContentEditable,
        placeholder: target.getAttribute?.('placeholder') || ''
      },
      diagnostics: inspection.diagnostics
    };
  }
  return { ok: false, surface: 'generic', error: 'Page adapter API was unavailable in fallback execution path.' };
}

function injectTextInPage(text) {
  const api = globalThis.MeteraPageAdapters;
  if (!api?.inspectPromptTarget || !api?.injectTextIntoNode) {
    return { ok: false, surface: 'generic', error: 'Page adapter API was unavailable in fallback execution path.' };
  }
  const inspection = api.inspectPromptTarget(document, window.location);
  if (!inspection?.ok || !inspection.targetNode) {
    return { ok: false, surface: api.detectSurface(window.location), error: inspection?.error || 'No prompt target detected.', diagnostics: inspection?.diagnostics || null };
  }
  const injected = api.injectTextIntoNode(inspection.targetNode, text);
  return { ...injected, surface: api.detectSurface(window.location), fallback: true, diagnostics: inspection.diagnostics };
}

function getSelectionInPage() {
  const api = globalThis.MeteraPageAdapters;
  const surface = api?.detectSurface(window.location) || 'generic';
  return { ok: true, surface, selectedText: window.getSelection?.().toString() || '', fallback: true };
}

function captureLatestResponseInPage() {
  const api = globalThis.MeteraPageAdapters;
  if (!api?.captureLatestAssistantResponse) {
    return { ok: false, surface: 'generic', error: 'Page adapter API was unavailable in fallback execution path.' };
  }
  const payload = api.captureLatestAssistantResponse(document, window.location);
  return { ...payload, fallback: true };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "metera:get-tab-context") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tab = tabs[0];
      sendResponse({
        ok: true,
        tab: tab
          ? {
              id: tab.id,
              title: tab.title || "",
              url: tab.url || ""
            }
          : null
      });
    });
    return true;
  }

  if (message?.type === "metera:get-runtime-diagnostics") {
    chrome.storage.local.get(["runtimeDiagnostics"], (items) => {
      sendResponse({ ok: true, events: Array.isArray(items.runtimeDiagnostics) ? items.runtimeDiagnostics : [] });
    });
    return true;
  }

  if (message?.type === "metera:inject-text") {
    return withTargetTab(
      sender,
      message.tabId,
      (tabId) => {
        chrome.tabs.sendMessage(tabId, { type: "metera:inject-text", text: message.text }, (response) => {
          if (chrome.runtime.lastError) {
            const error = chrome.runtime.lastError.message;
            if (isMissingReceiverError(error)) {
              rememberRuntimeEvent({ level: 'warn', action: 'inject-text', path: 'tabs.sendMessage', tabId, error, recovery: 'fallback_executeScript' });
              executeInTab(tabId, injectTextInPage, [message.text], sendResponse, "Injection");
              return;
            }
            rememberRuntimeEvent({ level: 'error', action: 'inject-text', path: 'tabs.sendMessage', tabId, error });
            sendResponse({ ok: false, error, diagnostics: { tabId, path: "tabs.sendMessage" } });
            return;
          }
          rememberRuntimeEvent({ level: 'info', action: 'inject-text', path: 'tabs.sendMessage', tabId, ok: !!response?.ok });
          sendResponse(response || { ok: true });
        });
      },
      () => sendResponse({ ok: false, error: "No active tab was available for injection." })
    );
  }

  if (message?.type === "metera:get-selection") {
    return withTargetTab(
      sender,
      message.tabId,
      (tabId) => {
        chrome.tabs.sendMessage(tabId, { type: "metera:get-selection" }, (response) => {
          if (chrome.runtime.lastError) {
            const error = chrome.runtime.lastError.message;
            if (isMissingReceiverError(error)) {
              rememberRuntimeEvent({ level: 'warn', action: 'get-selection', path: 'tabs.sendMessage', tabId, error, recovery: 'fallback_executeScript' });
              executeInTab(tabId, getSelectionInPage, [], sendResponse, "Selection");
              return;
            }
            rememberRuntimeEvent({ level: 'error', action: 'get-selection', path: 'tabs.sendMessage', tabId, error });
            sendResponse({ ok: false, error, diagnostics: { tabId, path: "tabs.sendMessage" } });
            return;
          }
          rememberRuntimeEvent({ level: 'info', action: 'get-selection', path: 'tabs.sendMessage', tabId, ok: !!response?.ok });
          sendResponse(response || { ok: true, selectedText: "" });
        });
      },
      () => sendResponse({ ok: false, error: "No active tab was available for selection capture." })
    );
  }

  if (message?.type === "metera:capture-latest-response") {
    return withTargetTab(
      sender,
      message.tabId,
      (tabId) => {
        chrome.tabs.sendMessage(tabId, { type: "metera:capture-latest-response" }, (response) => {
          if (chrome.runtime.lastError) {
            const error = chrome.runtime.lastError.message;
            if (isMissingReceiverError(error)) {
              rememberRuntimeEvent({ level: 'warn', action: 'capture-latest-response', path: 'tabs.sendMessage', tabId, error, recovery: 'fallback_executeScript' });
              executeInTab(tabId, captureLatestResponseInPage, [], sendResponse, "Latest response capture");
              return;
            }
            rememberRuntimeEvent({ level: 'error', action: 'capture-latest-response', path: 'tabs.sendMessage', tabId, error });
            sendResponse({ ok: false, error, diagnostics: { tabId, path: "tabs.sendMessage" } });
            return;
          }
          rememberRuntimeEvent({ level: 'info', action: 'capture-latest-response', path: 'tabs.sendMessage', tabId, ok: !!response?.ok });
          sendResponse(response || { ok: false, error: 'No latest response payload was returned.' });
        });
      },
      () => sendResponse({ ok: false, error: "No active tab was available for latest-response capture." })
    );
  }

  if (message?.type === "metera:inspect-prompt-target") {
    return withTargetTab(
      sender,
      message.tabId,
      (tabId) => {
        chrome.tabs.sendMessage(tabId, { type: "metera:inspect-prompt-target" }, (response) => {
          if (chrome.runtime.lastError) {
            const error = chrome.runtime.lastError.message;
            if (isMissingReceiverError(error)) {
              rememberRuntimeEvent({ level: 'warn', action: 'inspect-prompt-target', path: 'tabs.sendMessage', tabId, error, recovery: 'fallback_executeScript' });
              executeInTab(tabId, inspectPromptTargetInPage, [], sendResponse, "Prompt inspection");
              return;
            }
            rememberRuntimeEvent({ level: 'error', action: 'inspect-prompt-target', path: 'tabs.sendMessage', tabId, error });
            sendResponse({ ok: false, error, diagnostics: { tabId, path: "tabs.sendMessage" } });
            return;
          }
          rememberRuntimeEvent({ level: 'info', action: 'inspect-prompt-target', path: 'tabs.sendMessage', tabId, ok: !!response?.ok });
          sendResponse(response || { ok: false, error: "No prompt target response was returned." });
        });
      },
      () => sendResponse({ ok: false, error: "No active tab was available for prompt inspection." })
    );
  }

  return false;
});
