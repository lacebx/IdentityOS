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
      console.warn('[IdentityRuntime] Could not fetch identity context:', e);
      return null;
    }
  }

  function observePromptSubmit() {
    const observer = new MutationObserver(() => {
      const textarea = document.querySelector('#prompt-textarea');
      if (textarea && !textarea.dataset.irPatched) {
        textarea.dataset.irPatched = 'true';
        patchTextarea(textarea);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function patchTextarea(textarea) {
    const form = textarea.closest('form');
    if (!form) return;

    form.addEventListener('submit', (e) => {
      if (!identityContext || !currentIdentityId) return;
      const original = textarea.value;
      if (!original.includes('[IdentityContext]')) {
        const augmented = `[IdentityContext]\n${identityContext}\n[/IdentityContext]\n\n${original}`;
        const nativeInputSetter = Object.getOwnPropertyDescriptor(
          window.HTMLTextAreaElement.prototype, 'value'
        ).set;
        nativeInputSetter.call(textarea, augmented);
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
      }
    }, { capture: true });
  }

  function observeResponseStream() {
    const observer = new MutationObserver(async (mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (node.nodeType !== Node.ELEMENT_NODE) continue;
          const assistantMsg = node.querySelector
            ? node.querySelector('[data-message-author-role="assistant"]')
            : null;
          if (assistantMsg) {
            const text = assistantMsg.innerText?.trim();
            const userMsg = findUserMessage(assistantMsg);
            if (text && currentIdentityId) {
              await storeExchange(currentIdentityId, userMsg || '', text);
            }
          }
        }
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function findUserMessage(assistantNode) {
    const articles = document.querySelectorAll('[data-message-author-role="user"]');
    if (articles.length > 0) {
      return articles[articles.length - 1].innerText?.trim() || '';
    }
    return '';
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
      console.warn('[IdentityRuntime] Store failed:', e);
    }
  }

  function injectIdentityBadge() {
    if (document.getElementById('ir-identity-badge')) return;
    const badge = document.createElement('div');
    badge.id = 'ir-identity-badge';
    badge.style.cssText = `
      position: fixed; bottom: 80px; right: 16px;
      background: #1a1a2e; color: #e0e0ff;
      border: 1px solid #4444aa; border-radius: 8px;
      padding: 6px 12px; font-size: 12px;
      font-family: monospace; z-index: 9999;
      cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,0.4);
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
