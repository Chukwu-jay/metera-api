(function (globalScope) {
  const ADAPTERS = {
    chatgpt: {
      id: 'chatgpt',
      matches(hostname) {
        return hostname === 'chatgpt.com' || hostname === 'chat.openai.com';
      },
      selectors: [
        'div#prompt-textarea[role="textbox"]',
        '#prompt-textarea',
        'div[role="textbox"][contenteditable="true"]',
        '[contenteditable="true"][data-lexical-editor="true"]',
        'textarea[data-id="root"]',
        'form textarea',
        'textarea'
      ],
      responseSelectors: [
        '[data-message-author-role="assistant"]',
        'article[data-testid*="conversation-turn"] [data-message-author-role="assistant"]',
        'main article',
        'article',
        '.markdown'
      ]
    },
    claude: {
      id: 'claude',
      matches(hostname) {
        return hostname === 'claude.ai';
      },
      selectors: [
        'div[contenteditable="true"][role="textbox"]',
        'fieldset div[contenteditable="true"]',
        'form div[contenteditable="true"]',
        '[contenteditable="true"]',
        'textarea'
      ],
      responseSelectors: [
        '[data-is-streaming="false"] .font-claude-message, .font-claude-message',
        '[data-testid*="message"] .prose',
        'main [data-testid*="message"]',
        'article',
        '.prose'
      ]
    },
    generic: {
      id: 'generic',
      matches() {
        return true;
      },
      selectors: [
        'textarea',
        'div[role="textbox"][contenteditable="true"]',
        '[contenteditable="true"]',
        'input[type="text"]'
      ],
      responseSelectors: [
        'article',
        '[role="article"]',
        '.assistant',
        '.markdown',
        '.prose'
      ]
    }
  };

  function getAdapterForLocation(locationLike) {
    const hostname = String(locationLike?.hostname || '').toLowerCase();
    for (const adapter of [ADAPTERS.chatgpt, ADAPTERS.claude]) {
      if (adapter.matches(hostname)) {
        return adapter;
      }
    }
    return ADAPTERS.generic;
  }

  function isVisibleElement(node) {
    if (!node) {
      return false;
    }
    if (node.hidden || node.getAttribute?.('aria-hidden') === 'true' || node.getAttribute?.('disabled') === 'true') {
      return false;
    }
    const style = globalScope.getComputedStyle ? globalScope.getComputedStyle(node) : null;
    if (style && (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0')) {
      return false;
    }
    const rect = node.getBoundingClientRect ? node.getBoundingClientRect() : { width: 1, height: 1, top: 0 };
    return rect.width > 0 && rect.height > 0;
  }

  function scorePromptTarget(node) {
    if (!node) {
      return -1;
    }
    let score = 0;
    const tag = (node.tagName || '').toLowerCase();
    const id = String(node.id || '');
    const placeholder = String(node.getAttribute?.('placeholder') || '').toLowerCase();
    const ariaLabel = String(node.getAttribute?.('aria-label') || '').toLowerCase();
    const classes = String(node.className || '').toLowerCase();
    if (tag === 'textarea') {
      score += 10;
    }
    if (tag === 'input') {
      score += 3;
    }
    if (tag === 'div' && id === 'prompt-textarea') {
      score += 12;
    }
    if (node.getAttribute?.('role') === 'textbox') {
      score += 6;
    }
    if (node.isContentEditable) {
      score += 6;
    }
    if (id.includes('prompt') || ariaLabel.includes('prompt')) {
      score += 4;
    }
    if (placeholder.includes('message') || placeholder.includes('send')) {
      score += 4;
    }
    if (ariaLabel.includes('message') || ariaLabel.includes('chatgpt') || ariaLabel.includes('claude')) {
      score += 4;
    }
    if (classes.includes('lexical')) {
      score += 2;
    }
    if (node.closest?.('form')) {
      score += 3;
    }
    const rect = node.getBoundingClientRect ? node.getBoundingClientRect() : null;
    if (rect && rect.top > 0) {
      score += Math.max(0, 3 - Math.min(3, Math.round(rect.top / 400)));
    }
    if (!isVisibleElement(node)) {
      score -= 20;
    }
    return score;
  }

  function findPromptCandidates(doc, locationLike) {
    const adapter = getAdapterForLocation(locationLike);
    const seen = new Set();
    const candidates = [];
    for (const selector of adapter.selectors) {
      for (const node of doc.querySelectorAll(selector)) {
        if (seen.has(node)) {
          continue;
        }
        seen.add(node);
        candidates.push({ node, selector, score: scorePromptTarget(node) });
      }
    }
    candidates.sort((left, right) => right.score - left.score || String(left.selector).localeCompare(String(right.selector)));
    return candidates;
  }

  function findPromptTarget(doc, locationLike) {
    const candidates = findPromptCandidates(doc, locationLike);
    return candidates[0]?.node || null;
  }

  function inspectPromptTarget(doc, locationLike) {
    const adapter = getAdapterForLocation(locationLike);
    const candidates = findPromptCandidates(doc, locationLike);
    const top = candidates[0];
    if (!top) {
      return {
        ok: false,
        error: `No prompt target detected on ${adapter.id}.`,
        diagnostics: {
          surface: adapter.id,
          candidateCount: 0,
          selectorsTried: [...adapter.selectors],
          candidates: [],
        },
      };
    }
    return {
      ok: true,
      targetNode: top.node,
      diagnostics: {
        surface: adapter.id,
        candidateCount: candidates.length,
        selectorsTried: [...adapter.selectors],
        candidates: candidates.slice(0, 5).map((candidate) => ({
          selector: candidate.selector,
          score: candidate.score,
          tagName: candidate.node.tagName,
          id: candidate.node.id || '',
          role: candidate.node.getAttribute?.('role') || '',
          placeholder: candidate.node.getAttribute?.('placeholder') || '',
          contentEditable: !!candidate.node.isContentEditable,
        })),
      },
    };
  }

  function compactText(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function captureLatestAssistantResponse(doc, locationLike) {
    const adapter = getAdapterForLocation(locationLike);
    const seen = new Set();
    const candidates = [];
    for (const selector of adapter.responseSelectors || []) {
      for (const node of doc.querySelectorAll(selector)) {
        if (seen.has(node)) {
          continue;
        }
        seen.add(node);
        const text = compactText(node.innerText || node.textContent || '');
        if (!text) {
          continue;
        }
        if (!isVisibleElement(node)) {
          continue;
        }
        candidates.push({ node, selector, text });
      }
    }
    const best = candidates[candidates.length - 1];
    if (!best) {
      return {
        ok: false,
        surface: adapter.id,
        error: `No assistant response block was detected on ${adapter.id}.`,
        diagnostics: {
          surface: adapter.id,
          selectorsTried: [...(adapter.responseSelectors || [])],
          candidateCount: 0,
        },
      };
    }
    return {
      ok: true,
      surface: adapter.id,
      captureMode: 'latest_assistant_response',
      text: best.text,
      selectedText: best.text,
      diagnostics: {
        surface: adapter.id,
        selectorUsed: best.selector,
        candidateCount: candidates.length,
      },
    };
  }

  function setNativeValue(node, value) {
    const prototype = node instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : node instanceof HTMLInputElement
        ? HTMLInputElement.prototype
        : null;
    const descriptor = prototype ? Object.getOwnPropertyDescriptor(prototype, 'value') : null;
    if (descriptor?.set) {
      descriptor.set.call(node, value);
      return true;
    }
    node.value = value;
    return true;
  }

  function injectTextIntoNode(node, text) {
    const value = text || '';
    if (node instanceof HTMLTextAreaElement || node instanceof HTMLInputElement) {
      node.focus();
      setNativeValue(node, value);
      node.dispatchEvent(new Event('input', { bubbles: true }));
      node.dispatchEvent(new Event('change', { bubbles: true }));
      return { ok: true, mode: 'value' };
    }

    node.focus();

    const selection = globalScope.getSelection?.();
    const range = document.createRange();
    range.selectNodeContents(node);
    selection?.removeAllRanges();
    selection?.addRange(range);

    let inserted = false;
    if (globalScope.document?.execCommand) {
      try {
        inserted = !!document.execCommand('selectAll', false) || inserted;
        inserted = !!document.execCommand('insertText', false, value) || inserted;
      } catch {
        inserted = false;
      }
    }

    if (!inserted) {
      node.textContent = value;
    }

    node.dispatchEvent(new InputEvent('beforeinput', { bubbles: true, cancelable: true, data: value, inputType: 'insertText' }));
    node.dispatchEvent(new InputEvent('input', { bubbles: true, data: value, inputType: 'insertText' }));
    node.dispatchEvent(new Event('change', { bubbles: true }));
    return { ok: true, mode: 'contenteditable' };
  }

  function detectSurface(locationLike) {
    return getAdapterForLocation(locationLike).id;
  }

  const api = {
    ADAPTERS,
    detectSurface,
    findPromptCandidates,
    findPromptTarget,
    inspectPromptTarget,
    captureLatestAssistantResponse,
    injectTextIntoNode,
    scorePromptTarget,
    isVisibleElement
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
  globalScope.MeteraPageAdapters = api;
})(typeof window !== 'undefined' ? window : globalThis);
