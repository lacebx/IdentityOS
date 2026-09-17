/**
 * IdentityOS Live Browser Bridge - Content Script
 * 
 * This content script runs in all pages and provides page-level functionality
 * for the IdentityOS Live Browser Bridge.
 */

// Page state
let pageObserver = null;
let isInitialized = false;

// Initialize page interaction capabilities
function initializePage() {
  if (isInitialized) return;
  isInitialized = true;

  // Add keyboard event listener for press key simulation
  document.addEventListener("keydown", (e) => {
    // Could be used for press key detection if needed
  }, true);

  // Observe DOM changes for dynamic content
  pageObserver = new MutationObserver((mutations) => {
    // Could notify bridge of significant changes
  });
  pageObserver.observe(document.body, {
    childList: true,
    subtree: true,
    attributes: true,
    characterData: true
  });
}

// Get page snapshot (text, interactive elements, etc.)
function getSnapshot(maxChars = 4000) {
  const text = document.body.innerText || "";
  const truncatedText = text.length > maxChars ? text.substring(0, maxChars) + "..." : text;

  // Get interactive elements
  const interactiveElements = [];
  const selectors = [
    "a[href]",
    "button",
    "input",
    "select",
    "textarea",
    "[role='button']",
    "[role='link']",
    "[onclick]",
    "[role='tab']",
    "[role='menuitem']"
  ];

  for (const selector of selectors) {
    const elements = document.querySelectorAll(selector);
    for (const el of elements) {
      if (interactiveElements.length >= 50) break;
      const rect = el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        interactiveElements.push({
          tag: el.tagName.toLowerCase(),
          type: el.type || "",
          role: el.getAttribute("role") || "",
          text: el.innerText ? el.innerText.trim().substring(0, 100) : "",
          value: el.value || "",
          placeholder: el.placeholder || "",
          id: el.id || "",
          name: el.name || "",
          class: el.className || "",
          selector: getUniqueSelector(el),
          visible: isElementVisible(el)
        });
      }
    }
    if (interactiveElements.length >= 50) break;
  }

  return {
    url: window.location.href,
    title: document.title,
    text: truncatedText,
    interactive: interactiveElements,
    timestamp: Date.now()
  };
}

function getUniqueSelector(element) {
  if (element.id) return `#${element.id}`;
  if (element.name) return `[name="${element.name}"]`;
  
  let selector = element.tagName.toLowerCase();
  if (element.className) {
    const classes = element.className.split(/\s+/).filter(c => c.length > 0);
    if (classes.length > 0) {
      selector += "." + classes.join(".");
    }
  }
  
  let current = element;
  while (current.parentElement && current !== document.body) {
    const parent = current.parentElement;
    const siblings = Array.from(parent.querySelectorAll(selector));
    if (siblings.length > 1) {
      const index = siblings.indexOf(current) + 1;
      selector = `${selector}:nth-of-type(${index})`;
    }
    selector = `${parent.tagName.toLowerCase()} > ${selector}`;
    current = parent;
  }
  return selector;
}

function isElementVisible(element) {
  const style = window.getComputedStyle(element);
  if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {
    return false;
  }
  const rect = element.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
}

// Navigation
function navigate(url, waitUntil = "domcontentloaded") {
  return new Promise((resolve, reject) => {
    const originalUrl = window.location.href;
    window.location.href = url;
    
    const checkLoaded = setInterval(() => {
      if (document.readyState === "complete" || 
          (waitUntil === "domcontentloaded" && document.readyState === "interactive") ||
          (waitUntil === "networkidle" && performance.getEntriesByType("resource").every(r => r.responseEnd > 0))) {
        clearInterval(checkLoaded);
        resolve({ url: window.location.href, title: document.title });
      }
    }, 100);
    
    setTimeout(() => {
      clearInterval(checkLoaded);
      reject(new Error("Navigation timeout"));
    }, 30000);
  }
}

// Click element
function clickElement(selector) {
  const element = document.querySelector(selector);
  if (!element) {
    throw new Error(`Element not found: ${selector}`);
  }
  
  // Check if element is visible
  const rect = element.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) {
    throw new Error(`Element not visible: ${selector}`);
  }
  
  element.click();
  return { ok: true, selector, url: window.location.href };
}

// Fill form field
function fillElement(selector, value) {
  const element = document.querySelector(selector);
  if (!element) {
    throw new Error(`Element not found: ${selector}`);
  }
  
  // Focus and fill
  element.focus();
  element.value = value;
  
  // Trigger input events
  element.dispatchEvent(new Event("input", { bubbles: true }));
  element.dispatchEvent(new Event("change", { bubbles: true }));
  
  return { ok: true, selector, value: value.length, url: window.location.href };
}

// Type into element
function typeElement(selector, text) {
  const element = document.querySelector(selector);
  if (!element) {
    throw new Error(`Element not found: ${selector}`);
  }
  
  element.focus();
  element.value += text;
  
  // Trigger input events
  element.dispatchEvent(new Event("input", { bubbles: true }));
  element.dispatchEvent(new Event("change", { bubbles: true }));
  
  return { ok: true, selector, text: text.length, url: window.location.href };
}

// Press key
function pressKey(key) {
  const event = new KeyboardEvent("keydown", {
    key,
    code: key.length === 1 ? `Key${key.toUpperCase()}` : key,
    bubbles: true
  });
  document.dispatchEvent(event);
  
  return { ok: true, key, url: window.location.href };
}

// Initialize on load
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializePage);
} else {
  initializePage();
}

// Listen for messages from background script
browser.runtime.onMessage.addListener((message, sender, sendResponse) => {
  try {
    switch (message.method) {
      case "snapshot":
        sendResponse({ success: true, result: getSnapshot(message.maxChars) });
        break;
      case "navigate":
        navigate(message.url, message.waitUntil)
          .then(result => sendResponse({ success: true, result }))
          .catch(err => sendResponse({ success: false, error: err.message }));
        break;
      case "click":
        try {
          const result = clickElement(message.selector);
          sendResponse({ success: true, result });
        } catch (err) {
          sendResponse({ success: false, error: err.message });
        }
        break;
      case "fill":
        try {
          const result = fillElement(message.selector, message.value);
          sendResponse({ success: true, result });
        } catch (err) {
          sendResponse({ success: false, error: err.message });
        }
        break;
      case "type":
        try {
          const result = typeElement(message.selector, message.text);
          sendResponse({ success: true, result });
        } catch (err) {
          sendResponse({ success: false, error: err.message });
        }
        break;
      case "press":
        try {
          const result = pressKey(message.key);
          sendResponse({ success: true, result });
        } catch (err) {
          sendResponse({ success: false, error: err.message });
        }
        break;
      case "status":
        sendResponse({ 
          success: true, 
          result: { 
            url: window.location.href, 
            title: document.title,
            readyState: document.readyState
          } 
        });
        break;
      default:
        sendResponse({ success: false, error: `Unknown method: ${message.method}` });
    }
  } catch (err) {
    sendResponse({ success: false, error: err.message });
  }
  return true; // async response
});