function adapterApi() {
  return globalThis.MeteraPageAdapters;
}

function currentSurface() {
  const api = adapterApi();
  return api?.detectSurface(window.location) || 'generic';
}

function injectText(text) {
  const api = adapterApi();
  const inspection = api?.inspectPromptTarget(document, window.location);
  if (!inspection?.ok || !inspection.targetNode) {
    return {
      ok: false,
      error: inspection?.error || `No prompt input was found on this page for surface ${currentSurface()}.`,
      diagnostics: inspection?.diagnostics || null,
    };
  }

  const result = api.injectTextIntoNode(inspection.targetNode, text);
  return {
    ...result,
    surface: currentSurface(),
    diagnostics: inspection.diagnostics,
  };
}

function getSelectionPayload() {
  return {
    ok: true,
    surface: currentSurface(),
    selectedText: window.getSelection()?.toString() || ''
  };
}

function inspectPromptTarget() {
  const api = adapterApi();
  const inspection = api?.inspectPromptTarget(document, window.location);
  if (!inspection?.ok || !inspection.targetNode) {
    return {
      ok: false,
      surface: currentSurface(),
      error: inspection?.error || 'No prompt target detected.',
      diagnostics: inspection?.diagnostics || null,
    };
  }
  const target = inspection.targetNode;
  return {
    ok: true,
    surface: currentSurface(),
    target: {
      tagName: target.tagName,
      id: target.id || '',
      role: target.getAttribute?.('role') || '',
      contentEditable: !!target.isContentEditable,
      placeholder: target.getAttribute?.('placeholder') || '',
    },
    diagnostics: inspection.diagnostics,
  };
}

function captureLatestAssistantResponse() {
  const api = adapterApi();
  const payload = api?.captureLatestAssistantResponse(document, window.location);
  if (!payload?.ok) {
    return {
      ok: false,
      surface: currentSurface(),
      error: payload?.error || 'Could not find a latest assistant response on this page.',
      diagnostics: payload?.diagnostics || null,
    };
  }
  return payload;
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === 'metera:inject-text') {
    sendResponse(injectText(message.text));
    return false;
  }

  if (message?.type === 'metera:get-selection') {
    sendResponse(getSelectionPayload());
    return false;
  }

  if (message?.type === 'metera:inspect-prompt-target') {
    sendResponse(inspectPromptTarget());
    return false;
  }

  if (message?.type === 'metera:capture-latest-response') {
    sendResponse(captureLatestAssistantResponse());
    return false;
  }

  return false;
});
