'use strict';

class IdentityClientError extends Error {
  constructor(status, detail) {
    super(`IdentityOS API returned ${status}: ${detail}`);
    this.name = 'IdentityClientError';
    this.status = status;
  }
}

class IdentityClient {
  constructor(options = {}) {
    this.baseUrl = (options.baseUrl || 'http://localhost:8000').replace(/\/$/, '');
    this.apiKey = options.apiKey || '';
    this.fetch = options.fetch || globalThis.fetch;
    if (!this.fetch) throw new Error('IdentityClient requires fetch (Node.js 18 or newer).');
  }

  async request(path, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    if (this.apiKey) headers['X-API-Key'] = this.apiKey;
    let response;
    try {
      response = await this.fetch(`${this.baseUrl}${path}`, { ...options, headers });
    } catch (error) {
      throw new IdentityClientError(0, `runtime unavailable: ${error.message}`);
    }
    const text = await response.text();
    let data = {};
    if (text) {
      try { data = JSON.parse(text); } catch (_error) { data = { detail: text }; }
    }
    if (!response.ok) throw new IdentityClientError(response.status, data.detail || text || 'request failed');
    return data;
  }

  health() { return this.request('/health'); }

  async listIdentities() {
    const data = await this.request('/identity');
    return (data.identities || []).map((item) =>
      typeof item === 'string' ? { id: item, name: item } : item
    );
  }

  getIdentity(identityId) {
    return this.request(`/identity/${encodeURIComponent(identityId)}`);
  }

  exportIdentity(identityId) {
    return this.request('/export', {
      method: 'POST',
      body: JSON.stringify({ identity_id: identityId }),
    });
  }

  createIdentity(identityId, name, options = {}) {
    return this.request('/identity', {
      method: 'POST',
      body: JSON.stringify({ identity_id: identityId, name: name || identityId, ...options }),
    });
  }

  chat(identityId, message, options = {}) {
    return this.request('/chat', {
      method: 'POST',
      body: JSON.stringify({
        identity_id: identityId,
        message,
        user_id: options.userId || '',
        session_id: options.sessionId || null,
      }),
    });
  }

  remember(identityId, content, options = {}) {
    return this.request('/memory', {
      method: 'POST',
      body: JSON.stringify({
        identity_id: identityId,
        content,
        user_id: options.userId || '',
        memory_type: options.memoryType || 'semantic',
        tags: options.tags || [],
      }),
    });
  }

  addGoal(identityId, title, options = {}) {
    return this.request('/goal', {
      method: 'POST',
      body: JSON.stringify({
        identity_id: identityId,
        title,
        description: options.description || '',
        priority: options.priority || 'medium',
        scope: options.scope || 'persistent',
        success_criteria: options.successCriteria || '',
      }),
    });
  }
}

module.exports = { IdentityClient, IdentityClientError };
