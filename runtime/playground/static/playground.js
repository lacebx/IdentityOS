/* IdentityOS Playground - Runtime visualization */

let currentIdentity = null;
let pipelinePlayTimeout = null;
let pipelineStages = [];

document.addEventListener('DOMContentLoaded', () => {
  loadIdentityList();
  document.getElementById('identity-select').addEventListener('change', onIdentityChange);
  document.getElementById('chat-form').addEventListener('submit', onChatSubmit);
  document.getElementById('chat-input').addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); document.getElementById('chat-send').click(); }
  });
  document.getElementById('btn-create').addEventListener('click', showCreateModal);
  document.getElementById('btn-restart').addEventListener('click', restartRuntime);
  document.getElementById('btn-configure-adapter').addEventListener('click', showAdapterModal);

  // Clear log via double-click on log panel header
  const logPanel = document.querySelector('#panel-log-body')?.closest('.panel');
  const logHeader = logPanel?.querySelector('.panel-header');
  if (logHeader) {
    logHeader.addEventListener('dblclick', clearLog);
    logHeader.title = 'Double-click to clear';
  }
});

function loadIdentityList() {
  fetch('/playground/api/identities')
    .then(r => r.json())
    .then(ids => {
      const sel = document.getElementById('identity-select');
      const current = sel.value;
      sel.innerHTML = '<option value="">-- Select identity --</option>';
      ids.forEach(id => {
        const opt = document.createElement('option');
        opt.value = id;
        opt.textContent = id;
        sel.appendChild(opt);
      });
      if (current && ids.includes(current)) sel.value = current;
    });
}

function onIdentityChange() {
  const id = document.getElementById('identity-select').value;
  currentIdentity = id;
  if (!id) {
    document.querySelectorAll('.panel-body').forEach(p => { p.innerHTML = '<div class="empty">Select an identity to begin.</div>'; });
    document.getElementById('chat-messages').innerHTML = '';
    return;
  }
  // Hide identity-chooser help text
  document.getElementById('help-text')?.remove();
  loadIdentity(id);
}

function loadIdentity(id) {
  fetch(`/playground/api/identity/${encodeURIComponent(id)}`)
    .then(r => r.json())
    .then(data => {
      if (data.error) { return; }
      renderIdentity(data.identity);
      renderEvolution(data.evolution);
      renderIdentityEvolution(data.identity_evolution);
      renderMemories(data.memories);
      renderTimeline(data.timeline);
      renderGoals(data.goals);
      renderRelationships(data.relationships);
      renderAdapter(data.adapter);
      renderEvaluation(data.evaluation);
      renderPersistence(data.persistence);
      renderContext(data.context_sections || null, data.context);
      updateAllCounts(data);
    });
}

function updateAllCounts(data) {
  setCount('memories', data.memories?.length);
  setCount('timeline', data.timeline?.length);
  setCount('goals', data.goals?.length);
  setCount('relationships', data.relationships?.length);
  setCount('persistence', data.persistence?.length);
  if (data.evolution) {
    setCount('evolution', data.evolution.timeline_count);
  }
}

function setCount(id, n) {
  const el = document.getElementById(`count-${id}`);
  if (!el) return;
  el.textContent = (n != null && n > 0) ? `(${n})` : '';
}

function renderEvolution(evo) {
  const el = document.getElementById('panel-evolution-body');
  if (!evo || !evo.created_at) {
    el.innerHTML = '<div class="empty">No evolution data yet.</div>';
    return;
  }
  const age = evo.age_seconds || 0;
  const days = Math.floor(age / 86400);
  const hours = Math.floor((age % 86400) / 3600);
  const ageStr = days > 0 ? `${days}d ${hours}h` : `${hours}h`;
  const interactions = evo.interaction_count || 0;
  const mems = evo.memory_count || 0;
  const rels = evo.relationship_count || 0;
  const goals = evo.goal_count || 0;

  el.innerHTML = `
    <div class="evo-grid">
      <div class="evo-item">
        <span class="evo-value">${ageStr}</span>
        <span class="evo-label">Age</span>
      </div>
      <div class="evo-item">
        <span class="evo-value">${interactions}</span>
        <span class="evo-label">Interactions</span>
      </div>
      <div class="evo-item">
        <span class="evo-value">${mems}</span>
        <span class="evo-label">Memories</span>
      </div>
      <div class="evo-item">
        <span class="evo-value">${rels}</span>
        <span class="evo-label">Relationships</span>
      </div>
      <div class="evo-item">
        <span class="evo-value">${goals}</span>
        <span class="evo-label">Goals</span>
      </div>
      <div class="evo-item">
        <span class="evo-value">${interactions > 0 ? (mems / interactions).toFixed(1) : '-'}</span>
        <span class="evo-label">Mem/Int</span>
      </div>
    </div>
    <div class="evo-created">Created ${new Date(evo.created_at).toLocaleString()}</div>
  `;
}

function renderIdentity(identity) {
  const el = document.getElementById('panel-identity-body');
  if (!identity) { el.innerHTML = '<div class="empty">No identity loaded.</div>'; return; }
  el.innerHTML = `
    <div class="identity-field"><span class="identity-field-label">Name</span><span>${esc(identity.name)}</span></div>
    <div class="identity-field"><span class="identity-field-label">ID</span><span style="color:var(--text2);font-size:11px">${esc(identity.id)}</span></div>
    <div class="identity-field"><span class="identity-field-label">Version</span><span>${esc(identity.version||'0.1.0')}</span></div>
    <div class="identity-field"><span class="identity-field-label">Persona</span><span>${esc(identity.persona||'-')}</span></div>
    <div class="identity-field"><span class="identity-field-label">Created</span><span style="color:var(--text2)">${identity.created_at ? new Date(identity.created_at).toLocaleString() : '-'}</span></div>
    ${identity.system_prompt ? `<div class="identity-field"><span class="identity-field-label">System</span><span style="font-size:11px;color:var(--text2);white-space:pre-wrap">${esc(identity.system_prompt)}</span></div>` : ''}
  `;
}

let _knownMemoryIds = new Set();

function renderIdentityEvolution(evo) {
  const el = document.getElementById('panel-evolution-body');
  if (!evo) { el.innerHTML = '<div class="empty">No evolution data.</div>'; return; }
  let html = '';

  // Preferences
  const prefs = evo.preferences || {};
  const prefKeys = Object.keys(prefs);
  if (prefKeys.length) {
    html += '<div style="margin-bottom:8px"><div class="ctx-section-header" style="border-left:3px solid var(--accent);padding:4px 6px;font-size:11px;font-weight:600;color:var(--accent);cursor:pointer" onclick="this.nextElementSibling.classList.toggle(\'collapsed\')">Preferences (Evolved) <span style="float:right">&#x25BC;</span></div><div class="ctx-section-body" style="padding:4px 8px">';
    prefKeys.forEach(k => {
      const label = k.replace(/_/g, ' ').replace(/\./g, ' \u2192 ');
      html += `<div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid var(--surface2)"><span style="color:var(--text2);font-size:11px">${esc(label)}</span><span style="font-size:12px;font-weight:500">${esc(String(prefs[k]))}</span></div>`;
    });
    html += '</div></div>';
  }

  // Beliefs
  const beliefs = evo.beliefs || {};
  const beliefKeys = Object.keys(beliefs);
  if (beliefKeys.length) {
    html += '<div style="margin-bottom:8px"><div class="ctx-section-header" style="border-left:3px solid var(--purple);padding:4px 6px;font-size:11px;font-weight:600;color:var(--purple);cursor:pointer" onclick="this.nextElementSibling.classList.toggle(\'collapsed\')">Beliefs <span style="float:right">&#x25BC;</span></div><div class="ctx-section-body" style="padding:4px 8px">';
    beliefKeys.forEach(k => {
      html += `<div style="padding:2px 0;font-size:11px;border-bottom:1px solid var(--surface2)">${esc(beliefs[k])}</div>`;
    });
    html += '</div></div>';
  }

  // Traits
  const traits = evo.traits || [];
  if (traits.length) {
    html += '<div style="margin-bottom:8px"><div class="ctx-section-header" style="border-left:3px solid var(--green);padding:4px 6px;font-size:11px;font-weight:600;color:var(--green);cursor:pointer" onclick="this.nextElementSibling.classList.toggle(\'collapsed\')">Traits <span style="float:right">&#x25BC;</span></div><div class="ctx-section-body" style="padding:4px 8px">';
    traits.forEach(t => {
      const pct = Math.round((t.score || 0) * 100);
      html += `<div style="display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid var(--surface2)"><span style="font-size:11px">${esc(t.name)}</span><span style="font-size:11px">${pct}%</span></div>`;
    });
    html += '</div></div>';
  }

  // Like / Dislike
  const likes = evo.likes || [];
  const dislikes = evo.dislikes || [];
  if (likes.length || dislikes.length) {
    html += '<div style="margin-bottom:8px"><div class="ctx-section-header" style="border-left:3px solid var(--yellow);padding:4px 6px;font-size:11px;font-weight:600;color:var(--yellow);cursor:pointer" onclick="this.nextElementSibling.classList.toggle(\'collapsed\')">Likes / Dislikes <span style="float:right">&#x25BC;</span></div><div class="ctx-section-body" style="padding:4px 8px">';
    if (likes.length) html += `<div style="font-size:11px;color:var(--green)">Likes: ${likes.map(l => esc(l)).join(', ')}</div>`;
    if (dislikes.length) html += `<div style="font-size:11px;color:var(--red)">Dislikes: ${dislikes.map(d => esc(d)).join(', ')}</div>`;
    html += '</div></div>';
  }

  // Mutation history
  const mutations = evo.mutation_history || [];
  if (mutations.length) {
    html += '<div style="margin-bottom:8px"><div class="ctx-section-header" style="border-left:3px solid var(--orange);padding:4px 6px;font-size:11px;font-weight:600;color:var(--orange);cursor:pointer" onclick="this.nextElementSibling.classList.toggle(\'collapsed\')">Mutation History <span style="float:right">&#x25BC;</span></div><div class="ctx-section-body" style="padding:4px 8px">';
    [...mutations].reverse().forEach(m => {
      const status = m.status || 'unknown';
      const statusColor = status === 'accepted' ? 'var(--green)' : status === 'conflict' ? 'var(--orange)' : 'var(--red)';
      const field = m.field || '';
      const label = field.split('.').pop().replace(/_/g, ' ');
      const oldVal = m.old_value != null ? esc(String(m.old_value)) : '<em>none</em>';
      const newVal = m.new_value != null ? esc(String(m.new_value)) : '<em>none</em>';
      html += `<div style="padding:4px 0;border-bottom:1px solid var(--surface2);font-size:11px">
        <div style="display:flex;justify-content:space-between">
          <span style="font-weight:500">${esc(label)}</span>
          <span style="color:${statusColor};font-weight:600">${esc(status)}</span>
        </div>
        <div style="color:var(--text2);font-size:10px">${oldVal} \u2192 ${newVal}</div>
        <div style="color:var(--text2);font-size:10px">${esc(m.reason||'')}</div>
      </div>`;
    });
    html += '</div></div>';
  }

  if (!html) {
    el.innerHTML = '<div class="empty">No evolved attributes yet. Chat with the identity to begin the evolution process.</div>';
    return;
  }
  el.innerHTML = html;
}

function renderMemories(memories) {
  const el = document.getElementById('panel-memories-body');
  if (!memories || memories.length === 0) { el.innerHTML = '<div class="empty">No memories yet.</div>'; return; }
  const semantic = memories.filter(m => m.memory_type === 'semantic');
  const episodic = memories.filter(m => m.memory_type === 'episodic');
  let html = '';
  if (semantic.length) {
    html += '<div style="margin-bottom:6px;font-size:10px;color:var(--purple);font-weight:600;text-transform:uppercase;letter-spacing:0.3px">Semantic</div>';
    semantic.forEach(m => {
      html += `<div class="mem-item" data-id="${esc(m.id)}">
        <span class="mem-icon">&#x2713;</span>
        <span class="mem-type semantic">&#x25B6;</span>
        <span class="mem-content">${esc(m.content)}</span>
        <span class="mem-meta">${esc(m.tags?.join(', ') || '')}</span>
      </div>`;
    });
  }
  if (episodic.length) {
    html += '<div style="margin-top:6px;font-size:10px;color:var(--yellow);font-weight:600;text-transform:uppercase;letter-spacing:0.3px">Episodic</div>';
    [...episodic].reverse().forEach(m => {
      html += `<div class="mem-item" data-id="${esc(m.id)}">
        <span class="mem-icon">&#x1F4AC;</span>
        <span class="mem-type episodic">&#x25B6;</span>
        <span class="mem-content" style="font-size:11px">${esc(truncate(m.content, 120))}</span>
      </div>`;
    });
  }
  el.innerHTML = html;

  // Glow new memories
  memories.forEach(m => {
    if (!_knownMemoryIds.has(m.id)) {
      _knownMemoryIds.add(m.id);
      const item = el.querySelector(`[data-id="${esc(m.id)}"]`);
      if (item) {
        item.classList.add('glow');
        setTimeout(() => item.classList.remove('glow'), 2000);
      }
    }
  });
}

function renderTimeline(events) {
  const el = document.getElementById('panel-timeline-body');
  if (!events || events.length === 0) { el.innerHTML = '<div class="empty">No timeline events.</div>'; return; }
  el.innerHTML = events.map(e => `
    <div class="tl-item" data-id="${esc(e.id)}">
      <span class="tl-icon">&#x25CF;</span>
      <span class="tl-type ${esc(e.event_type)}">[${esc(e.event_type)}]</span>
      <span class="tl-title">${esc(e.title||'')}</span>
      <span class="tl-time">${e.occurred_at ? timeAgo(e.occurred_at) : ''}</span>
    </div>
  `).join('');
}

function renderGoals(goals) {
  const el = document.getElementById('panel-goals-body');
  if (!goals || goals.length === 0) { el.innerHTML = '<div class="empty">No goals.</div>'; return; }
  el.innerHTML = goals.map(g => {
    const pct = Math.round((g.progress || 0) * 100);
    return `<div class="goal-item" data-id="${esc(g.id)}">
      <span class="goal-priority ${esc(g.priority)}">[${esc(g.priority)}]</span>
      <span class="goal-title">${esc(g.title)}</span>
      <div class="goal-bar"><div class="goal-bar-fill" style="width:${pct}%"></div></div>
      <span class="goal-progress">${pct}%</span>
    </div>`;
  }).join('');

  // Glow new goals
  if (!window._knownGoalIds) window._knownGoalIds = new Set();
  goals.forEach(g => {
    if (!window._knownGoalIds.has(g.id)) {
      window._knownGoalIds.add(g.id);
      const item = el.querySelector(`[data-id="${esc(g.id)}"]`);
      if (item) {
        item.classList.add('glow');
        setTimeout(() => item.classList.remove('glow'), 2000);
      }
    }
  });
}

/* Edge type colors */
const EDGE_COLORS = {
  PEER: '#58a6ff',
  TRUSTED: '#3fb950',
  MENTOR: '#bc8cff',
  COLLABORATOR: '#d29922',
  ADVERSARIAL: '#f85149',
  NEUTRAL: '#8b949e',
};

function renderRelationships(edges) {
  const el = document.getElementById('panel-relationships-body');
  el.innerHTML = '<svg class="relation-graph" id="relation-svg"></svg><div class="rel-tooltip" id="rel-tooltip-div"></div>';
  if (!edges || edges.length === 0) {
    el.innerHTML = '<div class="empty">No relationships yet.</div>';
    return;
  }
  drawGraph(edges);
}

function drawGraph(edges) {
  const svg = document.getElementById('relation-svg');
  if (!svg) return;
  const w = svg.parentElement.clientWidth || 300;
  const h = 140;
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);

  const nodes = new Map();
  edges.forEach(e => {
    if (!nodes.has(e.source_id)) nodes.set(e.source_id, { id: e.source_id, x: 0, y: 0, degree: 0 });
    if (!nodes.has(e.target_id)) nodes.set(e.target_id, { id: e.target_id, x: 0, y: 0, degree: 0 });
    nodes.get(e.source_id).degree++;
    nodes.get(e.target_id).degree++;
  });
  const ids = [...nodes.keys()];
  if (ids.length === 0) return;

  const cx = w / 2, cy = h / 2;
  if (ids.length === 1) {
    nodes.get(ids[0]).x = cx;
    nodes.get(ids[0]).y = cy;
  } else if (ids.length === 2) {
    nodes.get(ids[0]).x = cx - 80;
    nodes.get(ids[0]).y = cy;
    nodes.get(ids[1]).x = cx + 80;
    nodes.get(ids[1]).y = cy;
  } else {
    const angleStep = (2 * Math.PI) / ids.length;
    ids.forEach((id, i) => {
      const a = i * angleStep - Math.PI / 2;
      nodes.get(id).x = cx + 80 * Math.cos(a);
      nodes.get(id).y = cy + 60 * Math.sin(a);
    });
  }

  let html = `<defs>
    <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="var(--border)"/></marker>
  </defs>`;

  edges.forEach(e => {
    const src = nodes.get(e.source_id);
    const dst = nodes.get(e.target_id);
    if (!src || !dst) return;

    const strength = e.strength || 0.5;
    const sw = Math.max(1, Math.min(6, 1 + strength * 5));
    const color = EDGE_COLORS[e.edge_type] || '#8b949e';
    const opacity = 0.4 + strength * 0.6;
    const mx = (src.x + dst.x) / 2;
    const my = (src.y + dst.y) / 2;

    html += `<line class="relation-edge" x1="${src.x}" y1="${src.y}" x2="${dst.x}" y2="${dst.y}"
      stroke="${color}" stroke-width="${sw}" stroke-opacity="${opacity}"
      marker-end="url(#arrowhead)"
      data-source="${esc(e.source_id)}" data-target="${esc(e.target_id)}"
      onmouseenter="showRelTooltip(event, '${esc(e.source_id)}', '${esc(e.target_id)}', '${esc(e.edge_type)}', ${strength}, ${e.interaction_count || 0}, '${esc(e.trust_level||'unknown')}', ${e.strength || 0.5})"
      onmouseleave="hideRelTooltip(event)"
      onmousemove="moveRelTooltip(event)" />

    <!-- Strength bar below edge middle -->
    <rect x="${mx - 24}" y="${my + 8}" width="48" height="4" rx="2" fill="var(--surface2)" />
    <rect x="${mx - 24}" y="${my + 8}" width="${Math.round(48 * strength)}" height="4" rx="2" fill="${color}" opacity="0.8" />

    <!-- Edge label -->
    <text class="relation-edge-text" x="${mx}" y="${my - 6}" text-anchor="middle" fill="${color}">${esc(e.edge_type)}</text>
    <text class="relation-edge-text" x="${mx}" y="${my - 16}" text-anchor="middle">${e.interaction_count || 0} interactions</text>`;
  });

  nodes.forEach((n, id) => {
    const isIdentity = id === currentIdentity;
    const maxDegree = Math.max(1, ...ids.map(i => nodes.get(i).degree));
    const r = isIdentity ? 10 : Math.max(5, 5 + (n.degree / maxDegree) * 8);
    html += `<circle class="relation-node" cx="${n.x}" cy="${n.y}" r="${r}"
      data-id="${esc(id)}"
      onmouseenter="showRelTooltip(event, '${esc(currentIdentity)}', '${esc(id)}', '', 0, 0, '', 0)"
      onmouseleave="hideRelTooltip(event)"
      onmousemove="moveRelTooltip(event)" />
    <text class="relation-node-label" x="${n.x}" y="${n.y + r + 12}" text-anchor="middle"
      font-weight="${isIdentity ? 'bold' : 'normal'}"
      fill="${isIdentity ? 'var(--accent)' : 'var(--text)'}">${isIdentity ? truncate(id, 12) + ' (self)' : truncate(id, 14)}</text>`;
  });

  svg.innerHTML = html;
}

function showRelTooltip(evt, src, target, edgeType, strength, interactions, trustLevel) {
  const div = document.getElementById('rel-tooltip-div');
  if (!div) return;
  let html = '';
  if (edgeType) {
    html = `<div class="rel-tt-edge">
      <div class="rel-tt-row"><span class="rel-tt-label">From</span><span class="rel-tt-val">${esc(src)}</span></div>
      <div class="rel-tt-row"><span class="rel-tt-label">To</span><span class="rel-tt-val">${esc(target)}</span></div>
      <div class="rel-tt-row"><span class="rel-tt-label">Type</span><span class="rel-tt-val" style="color:${EDGE_COLORS[edgeType]||'var(--text)'}">${esc(edgeType)}</span></div>
      <div class="rel-tt-row"><span class="rel-tt-label">Strength</span><span class="rel-tt-val">${(strength * 100).toFixed(0)}%</span></div>
      <div class="rel-tt-row"><span class="rel-tt-label">Interactions</span><span class="rel-tt-val">${interactions}</span></div>
      <div class="rel-tt-row"><span class="rel-tt-label">Trust</span><span class="rel-tt-val">${esc(trustLevel)}</span></div>
    </div>`;
  } else {
    html = `<div class="rel-tt-node">
      <div class="rel-tt-row"><span class="rel-tt-label">Identity</span><span class="rel-tt-val">${esc(target)}</span></div>
      ${target === currentIdentity ? '<div class="rel-tt-row"><span class="rel-tt-label" style="color:var(--accent)">Self</span></div>' : ''}
    </div>`;
  }
  div.innerHTML = html;
  div.style.display = 'block';
  positionTooltip(evt);
}

function hideRelTooltip(evt) {
  const div = document.getElementById('rel-tooltip-div');
  if (div) div.style.display = 'none';
}

function moveRelTooltip(evt) {
  positionTooltip(evt);
}

function positionTooltip(evt) {
  const div = document.getElementById('rel-tooltip-div');
  if (!div) return;
  const panel = document.getElementById('panel-relationships-body');
  if (!panel) return;
  const rect = panel.getBoundingClientRect();
  let x = evt.clientX - rect.left + 12;
  let y = evt.clientY - rect.top - 10;
  if (x + 180 > rect.width) x = evt.clientX - rect.left - 180;
  if (y < 0) y = 10;
  div.style.left = x + 'px';
  div.style.top = y + 'px';
}

function renderAdapter(adapter) {
  const el = document.getElementById('panel-adapter-body');
  if (!adapter) { el.innerHTML = '<div class="empty">No adapter configured.</div>'; return; }
  el.innerHTML = `
    <div class="adapter-info">
      <div class="ai-item"><span class="ai-label">Adapter:</span><span class="ai-value">${esc(adapter.type||'unknown')}</span></div>
      <div class="ai-item"><span class="ai-label">Model:</span><span class="ai-value">${esc(adapter.model||'-')}</span></div>
      ${adapter.latency ? `<div class="ai-item"><span class="ai-label">Latency:</span><span class="ai-value">${adapter.latency}</span></div>` : ''}
      ${adapter.provider ? `<div class="ai-item"><span class="ai-label">Provider:</span><span class="ai-value">${esc(adapter.provider)}</span></div>` : ''}
      <div class="ai-item"><span class="ai-label">Streaming:</span><span class="ai-value">${adapter.streaming ? 'Yes' : 'N/A'}</span></div>
    </div>
  `;
}

function renderContext(sections, fallbackText) {
  const el = document.getElementById('panel-context-body');
  if ((!sections || sections.length === 0) && !fallbackText) {
    el.innerHTML = '<div class="empty">No context yet. Send a message.</div>';
    return;
  }
  if (!sections || sections.length === 0) {
    // Fallback: render as raw text
    el.innerHTML = `<pre>${esc(fallbackText)}</pre>`;
    return;
  }
  let html = '';
  sections.forEach(s => {
    const chars = s.chars || 0;
    const tokens = Math.round(chars / 4);
    html += `<div class="ctx-section">
      <div class="ctx-section-header" style="border-left:3px solid ${esc(s.color)}">
        <span class="ctx-section-badge" style="background:${esc(s.color)}20;color:${esc(s.color)}">${esc(s.name)}</span>
        <span class="ctx-section-meta">${chars}B / ~${tokens} tok</span>
        <span class="ctx-toggle">&#x25BC;</span>
      </div>
      <div class="ctx-section-body"><pre>${esc(s.content)}</pre></div>
    </div>`;
  });
  el.innerHTML = html;

  // Toggle section expand/collapse
  el.querySelectorAll('.ctx-section-header').forEach(hdr => {
    hdr.addEventListener('click', () => {
      const body = hdr.nextElementSibling;
      const toggle = hdr.querySelector('.ctx-toggle');
      body.classList.toggle('collapsed');
      toggle.textContent = body.classList.contains('collapsed') ? '\u25B6' : '\u25BC';
    });
  });
}

function renderEvaluation(evalData) {
  const el = document.getElementById('panel-evaluation-body');
  if (!evalData) { el.innerHTML = '<div class="empty">No evaluations yet.</div>'; return; }
  const score = evalData.score != null ? evalData.score : '-';
  const passed = evalData.passed;
  const scoreClass = passed ? 'pass' : 'fail';
  const statusText = passed ? 'PASS' : 'FAIL';
  el.innerHTML = `
    <div><span class="eval-score ${scoreClass}">${typeof score === 'number' ? score.toFixed(2) : score}</span>
    <span style="font-size:12px;color:var(--text2);margin-left:8px">${statusText}</span></div>
    ${evalData.details ? `<div class="eval-detail">${esc(evalData.details)}</div>` : ''}
    ${evalData.criteria ? `<div class="eval-grid" style="margin-top:6px">${evalData.criteria.map(c => `<span class="eval-criterion">${esc(c.name)}</span><span></span><span class="eval-criterion-score" style="color:${c.score >= 0.5 ? 'var(--green)' : 'var(--red)'}">${c.score.toFixed(2)}</span>`).join('')}</div>` : ''}
  `;
}

function renderPersistence(persistEvents) {
  const el = document.getElementById('panel-persistence-body');
  if (!persistEvents || persistEvents.length === 0) { el.innerHTML = '<div class="empty">No persistence events yet.</div>'; return; }
  el.innerHTML = persistEvents.map(e => `
    <div class="persist-event">
      <span class="check">&#x2713;</span>
      <span>${esc(e)}</span>
    </div>
  `).join('');
}

function onChatSubmit(e) {
  e.preventDefault();
  if (!currentIdentity) { alert('Select an identity first.'); return; }
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;

  // Add user message
  addChatMessage('user', text);
  input.value = '';
  input.style.height = 'auto';

  // Show pending assistant message
  const pendingId = addPendingMessage();

  // Reset pipeline
  resetPipeline();
  document.getElementById('chat-send').disabled = true;
  document.getElementById('chat-send').textContent = 'Sending...';

  fetch('/playground/api/chat', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ identity_id: currentIdentity, user_input: text }),
  })
  .then(r => r.json())
  .then(data => {
    removePendingMessage(pendingId);
    document.getElementById('chat-send').disabled = false;
    document.getElementById('chat-send').textContent = 'Send';
    if (data.error) {
      addChatMessage('assistant', `Error: ${data.error}`);
      return;
    }

    // Play pipeline stages
    if (data.events && data.events.length) {
      playPipeline(data.events);
    }

    // Show response
    setTimeout(() => {
      addChatMessage('assistant', data.output || '[Empty response]');
      // Update context panel with structured sections
      renderContext(data.context_sections || null, data.context);
      // Refresh all panels
      loadIdentity(currentIdentity);
    }, data.events ? Math.min(data.events.length * 250, 2500) : 200);
  })
  .catch(err => {
    removePendingMessage(pendingId);
    document.getElementById('chat-send').disabled = false;
    document.getElementById('chat-send').textContent = 'Send';
    addChatMessage('assistant', `Request failed: ${err.message}`);
  });
}

function addChatMessage(role, text) {
  const container = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = `chat-msg ${role}`;
  const ts = new Date().toLocaleTimeString();
  div.innerHTML = `<div class="msg-label">${role === 'user' ? 'You' : (currentIdentity || 'Assistant')} <span class="msg-time">${ts}</span></div><div class="msg-content">${esc(text)}</div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function addPendingMessage() {
  const id = 'pending-' + Date.now();
  const container = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'chat-msg assistant';
  div.id = id;
  div.innerHTML = `<div class="msg-label">${currentIdentity || 'Assistant'}</div><div class="msg-content" style="color:var(--text2)"><span class="htmx-indicator" style="display:inline">Processing...</span></div>`;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return id;
}

function removePendingMessage(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

/* Pipeline animation */
const PIPELINE_STAGES = [
  'receive', 'policy_in', 'compose', 'adapter', 'policy_out',
  'evaluate', 'memory', 'timeline', 'relationship', 'persist', 'response'
];

function resetPipeline() {
  if (pipelinePlayTimeout) {
    clearTimeout(pipelinePlayTimeout);
    pipelinePlayTimeout = null;
  }
  PIPELINE_STAGES.forEach(s => {
    const el = document.getElementById(`stage-${s}`);
    if (el) { el.className = 'stage-badge pending'; el.textContent = s.replace('_',' '); }
  });
  // Reset arrows
  document.querySelectorAll('.stage-arrow').forEach(a => a.className = 'stage-arrow');
}

function formatStageDiagnostic(stage, data) {
  if (!data || Object.keys(data).length === 0) return '';
  switch (stage) {
    case 'receive':
      return data.content ? `${data.content.length}B` : '';
    case 'policy_in':
    case 'policy_out':
      if (data.allowed === false) return 'BLOCKED';
      const n = data.policies ? data.policies.length : 0;
      return `${n} policies`;
    case 'compose':
      return `${data.section_count || '?'} sections / ${data.token_estimate || '?'} tok`;
    case 'adapter':
      if (data.model && data.latency_ms) return `${data.model} ${data.latency_ms}ms`;
      if (data.model) return data.model;
      if (data.response_length) return `${data.response_length}B`;
      return '';
    case 'evaluate':
      if (data.passed === false) return 'FAIL';
      return data.score != null ? (data.score * 100).toFixed(0) + '%' : '';
    case 'memory':
      return data.memory_type || '';
    case 'timeline':
      return data.title || '';
    case 'relationship':
      return data.edge_count ? `${data.edge_count} edges` : '';
    case 'persist':
      return data.namespaces ? `${data.namespaces} ns` : '';
    case 'response':
      return data.output_length ? `${data.output_length}B` : '';
    default:
      return '';
  }
}

function playPipeline(events) {
  resetPipeline();
  pipelineStages = events;
  let idx = 0;
  function showNext() {
    if (idx >= pipelineStages.length) {
      return;
    }
    const evt = pipelineStages[idx];
    const stageName = evt.stage || evt.label?.toLowerCase().replace(/\s+/g,'_') || '';
    const badge = document.getElementById(`stage-${stageName}`);
    if (badge) {
      badge.className = 'stage-badge active';
      badge.textContent = evt.label || stageName.replace('_',' ');
      badge.title = '';
    }
    // Show diagnostic text in a sub-label
    const diag = formatStageDiagnostic(stageName, evt.data);
    if (diag) {
      badge.title = diag;
      // Insert as sub-element
      let sub = badge.querySelector('.stage-diag');
      if (!sub) {
        sub = document.createElement('span');
        sub.className = 'stage-diag';
        badge.appendChild(sub);
      }
      sub.textContent = diag;
    }

    // Activate arrow
    const arrow = document.getElementById(`arrow-${stageName}`);
    if (arrow) arrow.className = 'stage-arrow active';

    const delay = pipelineStages.length === idx + 1 ? 500 : 250;
    pipelinePlayTimeout = setTimeout(() => {
      if (badge) {
        badge.className = 'stage-badge done';
        badge.textContent = evt.label || stageName.replace('_',' ');
        // Show sub-label on done
        const diagFinal = formatStageDiagnostic(stageName, evt.data);
        if (diagFinal) {
          let sub = badge.querySelector('.stage-diag');
          if (!sub) {
            sub = document.createElement('span');
            sub.className = 'stage-diag';
            badge.appendChild(sub);
          }
          sub.textContent = diagFinal;
        }
      }
      idx++;
      showNext();
    }, delay);
  }
  showNext();
}

/* Esc */
function esc(s) {
  if (s == null) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function truncate(s, n) {
  if (!s) return '';
  return s.length > n ? s.substring(0, n) + '...' : s;
}

function timeAgo(iso) {
  const d = new Date(iso);
  const now = new Date();
  const sec = Math.floor((now - d) / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  return d.toLocaleTimeString();
}

/* Model suggestions per adapter */
const MODEL_SUGGESTIONS = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
  anthropic: ['claude-3-5-sonnet-20241022', 'claude-3-opus-20240229', 'claude-3-haiku-20240307'],
  ollama: ['llama3.2', 'llama3.1', 'mistral', 'codellama', 'mixtral'],
  openrouter: [
    'openai/gpt-4o',
    'openai/gpt-4o-mini',
    'openai/gpt-4-turbo',
    'anthropic/claude-3.5-sonnet',
    'google/gemini-2.0-flash-001',
    'google/gemini-2.0-flash-lite-001',
    'meta-llama/llama-3.2-3b-instruct',
    'meta-llama/llama-3.1-8b-instruct',
    'deepseek/deepseek-chat',
    'mistralai/mistral-7b-instruct',
    'xai/grok-2-20241218',
    'xai/grok-beta',
  ],
};

function updateModelSuggestions() {
  const adapter = document.getElementById('cfg-adapter').value;
  const datalist = document.getElementById('model-suggestions');
  const models = MODEL_SUGGESTIONS[adapter] || [];
  datalist.innerHTML = models.map(m => `<option value="${m}">`).join('');
}

/* Adapter configure modal */
function showAdapterModal() {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.id = 'adapter-modal';
  overlay.innerHTML = `
    <div class="modal">
      <h2>Configure Adapter</h2>
      <p style="font-size:12px;color:var(--text2);margin-bottom:12px">
        Also reads from env: IDENTITY_ADAPTER, IDENTITY_ADAPTER_CONFIG, OPENAI_API_KEY, ANTHROPIC_API_KEY
      </p>
      <label>Adapter</label>
      <select id="cfg-adapter" style="width:100%;background:var(--bg);color:var(--text);border:1px solid var(--border);padding:6px 8px;border-radius:4px;margin-bottom:10px" onchange="updateModelSuggestions()">
        <option value="">None (no LLM)</option>
        <option value="openai">OpenAI</option>
        <option value="anthropic">Anthropic</option>
        <option value="ollama">Ollama (local)</option>
        <option value="openrouter">OpenRouter</option>
      </select>
      <label>Model (select or type custom)</label>
      <input id="cfg-model" list="model-suggestions" placeholder="e.g. gpt-4o" />
      <datalist id="model-suggestions"></datalist>
      <label>API Key (optional)</label>
      <input id="cfg-api-key" type="password" placeholder="sk-... or leave blank for env var" />
      <label>Base URL (optional — for custom endpoints)</label>
      <input id="cfg-base-url" placeholder="e.g. http://localhost:11434/v1" />
      <div class="modal-actions">
        <button class="btn" onclick="closeAdapterModal()">Cancel</button>
        <button class="btn btn-primary" onclick="submitAdapterConfig()">Apply</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
}

function closeAdapterModal() {
  document.getElementById('adapter-modal')?.remove();
}

function submitAdapterConfig() {
  const adapter = document.getElementById('cfg-adapter').value;
  const model = document.getElementById('cfg-model').value.trim() || undefined;
  const apiKey = document.getElementById('cfg-api-key').value.trim() || undefined;
  const baseUrl = document.getElementById('cfg-base-url').value.trim() || undefined;

  const body = {};
  if (adapter) body.adapter = adapter;
  if (model) body.model = model;
  if (apiKey) body.api_key = apiKey;
  if (baseUrl) body.base_url = baseUrl;

  fetch('/playground/api/configure-adapter', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  })
  .then(r => r.json())
  .then(data => {
    closeAdapterModal();
    if (data.configured) {
      addLog('done', `Adapter: ${data.adapter} (${data.model})`);
    } else {
      addLog('err', `Adapter config issue: ${data.message || 'unknown'}`);
      alert(data.message || 'Adapter could not be configured.');
    }
    if (currentIdentity) loadIdentity(currentIdentity);
  })
  .catch(err => alert('Failed: ' + err.message));
}

function updateCreateModelSuggestions() {
  const adapter = document.getElementById('create-adapter').value;
  const datalist = document.getElementById('create-model-suggestions');
  const models = MODEL_SUGGESTIONS[adapter] || [];
  datalist.innerHTML = models.map(m => `<option value="${m}">`).join('');
}

/* Create identity modal */
function showCreateModal() {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.id = 'create-modal';
  overlay.innerHTML = `
    <div class="modal">
      <h2>Create Identity</h2>
      <label>Name</label>
      <input id="create-name" placeholder="e.g. Mentor" value="Mentor-${Date.now().toString(36)}" />
      <label>Identity ID (optional)</label>
      <input id="create-id" placeholder="Leave empty for auto-generated" />
      <label>Persona (optional)</label>
      <textarea id="create-persona" placeholder="A brief description of this identity's personality..."></textarea>
      <label>System Prompt (optional)</label>
      <textarea id="create-prompt" placeholder="Custom system prompt..."></textarea>
      <label>Adapter</label>
      <select id="create-adapter" style="width:100%;background:var(--bg);color:var(--text);border:1px solid var(--border);padding:6px 8px;border-radius:4px;margin-bottom:10px" onchange="updateCreateModelSuggestions()">
        <option value="">None (no LLM)</option>
        <option value="openai">OpenAI</option>
        <option value="anthropic">Anthropic</option>
        <option value="ollama">Ollama (local)</option>
        <option value="openrouter">OpenRouter</option>
      </select>
      <label>Model (select or type custom)</label>
      <input id="create-model" list="create-model-suggestions" placeholder="e.g. gpt-4o" />
      <datalist id="create-model-suggestions"></datalist>
      <label>API Key (optional — also reads OPENAI_API_KEY / ANTHROPIC_API_KEY env)</label>
      <input id="create-api-key" type="password" placeholder="sk-..." />
      <div class="modal-actions">
        <button class="btn" onclick="closeCreateModal()">Cancel</button>
        <button class="btn btn-primary" onclick="submitCreate()">Create</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
  setTimeout(() => document.getElementById('create-name')?.focus(), 100);
}

function closeCreateModal() {
  document.getElementById('create-modal')?.remove();
}

function submitCreate() {
  const name = document.getElementById('create-name').value.trim();
  const id = document.getElementById('create-id').value.trim() || undefined;
  const persona = document.getElementById('create-persona').value.trim() || undefined;
  const systemPrompt = document.getElementById('create-prompt').value.trim() || undefined;
  const adapter = document.getElementById('create-adapter').value;
  const model = document.getElementById('create-model').value.trim() || undefined;
  if (!name) { alert('Name is required'); return; }

  const apiKey = document.getElementById('create-api-key')?.value?.trim() || undefined;
  const body = { name, persona, system_prompt: systemPrompt };
  if (id) body.identity_id = id;
  if (adapter) body.adapter = adapter;
  if (model) body.model = model;

  fetch('/playground/api/identities', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  })
  .then(r => r.json())
  .then(data => {
    // Configure adapter with API key if provided
    if (adapter && apiKey) {
      fetch('/playground/api/configure-adapter', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ adapter, model, api_key: apiKey }),
      }).catch(() => {});
    }
    closeCreateModal();
    loadIdentityList();
    setTimeout(() => {
      document.getElementById('identity-select').value = data.id || id;
      onIdentityChange();
    }, 100);
  })
  .catch(err => alert('Create failed: ' + err.message));
}

/* Restart runtime */
function restartRuntime() {
  if (!currentIdentity) { alert('Select an identity first.'); return; }
  fetch('/playground/api/restart', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ identity_id: currentIdentity }),
  })
  .then(r => r.json())
  .then(data => {
    addChatMessage('assistant', 'Runtime restarted. Verifying persistence...');
    addLog('info', 'Runtime restarted');
    if (data.memories_restored) addLog('done', `Memories restored: ${data.memories_count}`);
    if (data.timeline_restored) addLog('done', `Timeline restored: ${data.timeline_count} events`);
    if (data.goals_restored) addLog('done', `Goals restored: ${data.goals_count}`);
    if (data.relationships_restored) addLog('done', `Relationships restored: ${data.relationships_count}`);
    setTimeout(() => loadIdentity(currentIdentity), 500);
  })
  .catch(err => alert('Restart failed: ' + err.message));
}

function addLog(level, text) {
  const el = document.getElementById('panel-log-body');
  const div = document.createElement('div');
  div.className = 'log-entry';
  div.innerHTML = `<span class="log-level ${level}">[${level}]</span><span>${esc(text)}</span>`;
  el.appendChild(div);
  el.scrollTop = el.scrollHeight;
  updateLogCount();
}

function updateLogCount() {
  const el = document.getElementById('panel-log-body');
  const n = el.querySelectorAll('.log-entry').length;
  setCount('log', n);
}

function clearLog() {
  const el = document.getElementById('panel-log-body');
  el.innerHTML = '<div class="empty">Runtime log cleared.</div>';
  updateLogCount();
}
