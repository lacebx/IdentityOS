(function () {
  'use strict';

  const RUNTIME_URL = 'http://localhost:8000';
  let currentIdentityId = null;
  let identityContext = null;

  async function init() {
    const config = await getConfig();
    currentIdentityId = config.activeIdentityId || config.identityId || null;
    if (currentIdentityId) {
      identityContext = await fetchIdentityContext(currentIdentityId);
    }
    observePromptSubmit();
    observeResponseStream();
  }

  function getConfig() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: 'GET_CONFIG' }, (resp) => {
        resolve(resp || {});
      });
    });
  }

  async function fetchIdentityContext(identityId) {
    try {
      const res = await fetch(`${RUNTIME_URL}/context`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: '',
          identity_id: identityId,
          user_id: 'extension-user',
        }),
      });
      const data = await res.json();
      return data.augmented_context || null;
    } catch (e) {
      console.warn('[IdentityRuntime:Grok] Could not fetch identity context:', e);
      return null;
    }
  }

  function observePromptSubmit() {
    const observer = new MutationObserver(() => {
      const input =
        document.querySelector('[data-testid="grok-compose-input"]') ||
        document.querySelector('div[contenteditable="true"][role="textbox"]');
      if (input && !input.dataset.irPatched) {
        input.dataset.irPatched = 'true';
        patchInput(input);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function patchInput(input) {
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey && identityContext && currentIdentityId) {
        const currentText = input.innerText || '';
        if (!currentText.includes('[IdentityContext]')) {
          const prefix = `[IdentityContext]\n${identityContext}\n[/IdentityContext]\n\n`;
          const selection = window.getSelection();
          const range = document.createRange();
          range.selectNodeContents(input);
          range.collapse(true);
          selection.removeAllRanges();
          selection.addRange(range);
          document.execCommand('insertText', false, prefix);
        }
      }
    }, { capture: true });
  }

  function observeResponseStream() {
    const observer = new MutationObserver(async (mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (node.nodeType !== Node.ELEMENT_NODE) continue;
          const assistantMsg =
            node.querySelector
              ? node.querySelector('[data-message-author="assistant"], .assistant-message')
              : null;
          if (assistantMsg) {
            const text = assistantMsg.innerText?.trim();
            if (text && currentIdentityId) {
              await storeExchange(currentIdentityId, '', text);
            }
          }
        }
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  async function storeExchange(identityId, userMsg, assistantMsg) {
    try {
      await fetch(`${RUNTIME_URL}/evaluate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMsg,
          response: assistantMsg,
          identity_id: identityId,
          user_id: 'extension-user',
        }),
      });
    } catch (e) {
      console.warn('[IdentityRuntime:Grok] Store failed:', e);
    }
  }

  function injectIdentityBadge() {
    if (document.getElementById('ir-identity-badge')) return;
    const badge = document.createElement('div');
    badge.id = 'ir-identity-badge';
    badge.style.cssText = `
      position: fixed; bottom: 80px; right: 16px;
      background: #0d0d1a; color: #c8b8ff;
      border: 1px solid #6644cc; border-radius: 8px;
      padding: 6px 12px; font-size: 12px;
      font-family: monospace; z-index: 9999;
      cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,0.5);
    `;
    badge.textContent = currentIdentityId ? `⬡ ${currentIdentityId}` : '⬡ No Identity';
    badge.addEventListener('click', () => {
      chrome.runtime.sendMessage({ type: 'OPEN_POPUP' });
    });
    document.body.appendChild(badge);
  }

  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === 'IDENTITY_CHANGED') {
      currentIdentityId = message.identityId;
      fetchIdentityContext(currentIdentityId).then((ctx) => {
        identityContext = ctx;
        const badge = document.getElementById('ir-identity-badge');
        if (badge) badge.textContent = currentIdentityId ? `⬡ ${currentIdentityId}` : '⬡ No Identity';
      });
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { init(); injectIdentityBadge(); });
  } else {
    init();
    injectIdentityBadge();
  }
})();
