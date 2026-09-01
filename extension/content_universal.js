/** Privacy-aware IdentityOS bridge for supported AI and social platforms. */

(function () {
  'use strict';

  const PROFILES = {
    'chatgpt.com': {
      platform: 'chatgpt', inject: true, inputs: ['#prompt-textarea', 'textarea'],
      assistants: ['[data-message-author-role="assistant"]'], users: ['[data-message-author-role="user"]'],
    },
    'chat.openai.com': {
      platform: 'chatgpt', inject: true, inputs: ['#prompt-textarea', 'textarea'],
      assistants: ['[data-message-author-role="assistant"]'], users: ['[data-message-author-role="user"]'],
    },
    'claude.ai': {
      platform: 'claude', inject: true, inputs: ['div[contenteditable="true"]'],
      assistants: ['[data-is-streaming="false"]', '.font-claude-message'], users: ['[data-testid="user-message"]'],
    },
    'gemini.google.com': {
      platform: 'gemini', inject: true,
      inputs: ['div[contenteditable="true"][role="textbox"]', '.ql-editor'],
      assistants: ['model-response', '.model-response-text'], users: ['user-query', '.query-text'],
    },
    'grok.com': {
      platform: 'grok', inject: true,
      inputs: ['[data-testid="grok-compose-input"]', 'div[contenteditable="true"][role="textbox"]'],
      assistants: ['[data-message-author="assistant"]', '.assistant-message'], users: [],
    },
    'x.com': {
      platform: 'grok', inject: true, inputs: ['[data-testid="grok-compose-input"]'],
      assistants: ['.assistant-message'], users: [],
    },
    'github.com': { platform: 'github', inject: false, inputs: [], assistants: [], users: [] },
    'www.reddit.com': { platform: 'reddit', inject: false, inputs: [], assistants: [], users: [] },
    'old.reddit.com': { platform: 'reddit', inject: false, inputs: [], assistants: [], users: [] },
    'www.youtube.com': { platform: 'youtube', inject: false, inputs: [], assistants: [], users: [] },
  };

  const profile = PROFILES[location.hostname];
  if (!profile) return;
  let config = null;
  let lastUserMessage = '';
  const capturedResponses = new Set();
  const bypassOnce = new WeakSet();

  function send(message) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(message, (response) => resolve(response || {}));
    });
  }

  function first(selectors, root = document) {
    for (const selector of selectors) {
      const match = root.querySelector(selector);
      if (match) return match;
    }
    return null;
  }

  function inputText(input) {
    return input.value !== undefined ? input.value : input.innerText || '';
  }

  function replaceInput(input, value) {
    if (input.value !== undefined) {
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype,
        'value',
      )?.set;
      if (setter) setter.call(input, value);
      else input.value = value;
    } else {
      input.textContent = value;
    }
    input.dispatchEvent(new InputEvent('input', {
      bubbles: true,
      inputType: 'insertText',
      data: value,
    }));
  }

  async function augment(input) {
    const original = inputText(input).trim();
    if (!original || original.includes('[IdentityContext]')) return false;
    const result = await send({
      type: 'GET_CONTEXT',
      platform: profile.platform,
      message: original,
    });
    if (!result.success || !result.data?.context) return false;
    lastUserMessage = original;
    replaceInput(
      input,
      `[IdentityContext]\n${result.data.context}\n[/IdentityContext]\n\n${original}`,
    );
    updateBadge(result.data.offline ? 'cached' : 'online');
    return true;
  }

  function patchInput(input) {
    if (input.dataset.identityOsPatched) return;
    input.dataset.identityOsPatched = 'true';
    input.addEventListener('keydown', async (event) => {
      if (event.key !== 'Enter' || event.shiftKey) return;
      if (bypassOnce.delete(input)) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      await augment(input);
      bypassOnce.add(input);
      input.dispatchEvent(new KeyboardEvent('keydown', {
        key: 'Enter', code: 'Enter', keyCode: 13, which: 13,
        bubbles: true, cancelable: true,
      }));
    }, { capture: true });
    const form = input.closest('form');
    if (form && !form.dataset.identityOsPatched) {
      form.dataset.identityOsPatched = 'true';
      form.addEventListener('submit', async (event) => {
        if (bypassOnce.delete(form)) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        await augment(input);
        bypassOnce.add(form);
        form.requestSubmit();
      }, { capture: true });
    }
  }

  async function captureResponses(root) {
    for (const selector of profile.assistants) {
      const nodes = root.querySelectorAll ? root.querySelectorAll(selector) : [];
      for (const node of nodes) {
        const text = node.innerText?.trim();
        if (!text || capturedResponses.has(text)) continue;
        capturedResponses.add(text);
        await send({
          type: 'SUBMIT_EVAL',
          platform: profile.platform,
          message: lastUserMessage,
          response: text,
        });
      }
    }
  }

  function updateBadge(state = '') {
    const badge = document.getElementById('identity-os-badge');
    if (!badge) return;
    const identity = config?.activeIdentityId || 'No identity';
    badge.textContent = `⬡ ${identity}${state ? ` · ${state}` : ''}`;
  }

  function injectBadge() {
    if (document.getElementById('identity-os-badge')) return;
    const badge = document.createElement('button');
    badge.id = 'identity-os-badge';
    badge.type = 'button';
    badge.title = profile.inject
      ? 'Identity context is private and injected only into this AI chat.'
      : 'Identity context stays private on this social site and is never inserted into posts.';
    badge.style.cssText = 'position:fixed;right:16px;bottom:80px;z-index:2147483647;padding:7px 11px;border:1px solid #6655cc;border-radius:8px;background:#17172b;color:#ddd9ff;font:12px monospace;box-shadow:0 2px 10px #0008';
    badge.addEventListener('click', async () => {
      const result = await send({
        type: 'GET_CONTEXT',
        platform: profile.platform,
        message: '',
      });
      if (result.success) {
        badge.title = result.data.context;
        updateBadge(result.data.offline ? 'cached' : 'ready');
      }
    });
    document.body.appendChild(badge);
    updateBadge(profile.inject ? 'ready' : 'private');
  }

  async function initialize() {
    config = await send({ type: 'GET_CONFIG' });
    if (!config.enabled || config.siteAccess?.[profile.platform] !== true) return;
    injectBadge();
    if (!profile.inject) return;
    const observer = new MutationObserver((mutations) => {
      const input = first(profile.inputs);
      if (input) patchInput(input);
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (node.nodeType === Node.ELEMENT_NODE) captureResponses(node);
        }
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
    const input = first(profile.inputs);
    if (input) patchInput(input);
  }

  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === 'IDENTITY_CHANGED') {
      config = { ...config, activeIdentityId: message.identityId };
      updateBadge('ready');
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, { once: true });
  } else {
    initialize();
  }
})();
