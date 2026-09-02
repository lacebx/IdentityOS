'use strict';

const crypto = require('crypto');
const vscode = require('vscode');
const { IdentityClient, IdentityClientError } = require('@identityos/sdk');

const SELECTED_KEY = 'identityos.selectedIdentity';
const CACHE_PREFIX = 'identityos.cachedIdentity.';

function workspacePartition() {
  const folder = vscode.workspace.workspaceFolders?.[0];
  if (!folder) return { label: 'no-workspace', userId: 'vscode:no-workspace' };
  const digest = crypto.createHash('sha256').update(folder.uri.toString()).digest('hex').slice(0, 16);
  return { label: folder.name, userId: `vscode:project:${digest}` };
}

function client() {
  const config = vscode.workspace.getConfiguration('identityos');
  return new IdentityClient({
    baseUrl: config.get('runtimeUrl'),
    apiKey: config.get('apiKey'),
  });
}

async function selectIdentity(context) {
  const identities = await client().listIdentities();
  if (!identities.length) {
    vscode.window.showWarningMessage('No IdentityOS identities exist yet.');
    return null;
  }
  const picked = await vscode.window.showQuickPick(
    identities.map((identity) => ({ label: identity.name || identity.id, description: identity.id })),
    { placeHolder: 'Choose the identity for this workspace' },
  );
  if (!picked) return null;
  await context.workspaceState.update(SELECTED_KEY, picked.description);
  await refreshCache(context, picked.description);
  vscode.window.showInformationMessage(`IdentityOS: ${picked.label} now follows this project.`);
  return picked.description;
}

async function selectedIdentity(context) {
  return context.workspaceState.get(SELECTED_KEY) || selectIdentity(context);
}

async function refreshCache(context, identityId) {
  const snapshot = await client().exportIdentity(identityId);
  await context.globalState.update(`${CACHE_PREFIX}${identityId}`, {
    snapshot,
    cachedAt: new Date().toISOString(),
  });
  return snapshot;
}

function offlineMessage(error) {
  return error instanceof IdentityClientError && error.status === 0
    ? 'IdentityOS runtime is offline. Cached identity state remains available with “Show Cached Identity Status”.'
    : `IdentityOS request failed: ${error.message}`;
}

function activate(context) {
  const output = vscode.window.createOutputChannel('IdentityOS');
  context.subscriptions.push(output);

  context.subscriptions.push(vscode.commands.registerCommand('identityos.selectIdentity', async () => {
    try { await selectIdentity(context); } catch (error) { vscode.window.showErrorMessage(offlineMessage(error)); }
  }));

  context.subscriptions.push(vscode.commands.registerCommand('identityos.chat', async () => {
    const identityId = await selectedIdentity(context);
    if (!identityId) return;
    const question = await vscode.window.showInputBox({ prompt: `Ask ${identityId} about this project` });
    if (!question) return;
    const project = workspacePartition();
    try {
      const result = await client().chat(identityId, question, {
        userId: project.userId,
        sessionId: `${project.userId}:${identityId}`,
      });
      output.appendLine(`\nYou (${project.label}): ${question}\n\n${identityId}: ${result.output}\n`);
      output.show(true);
      await refreshCache(context, identityId);
    } catch (error) {
      vscode.window.showErrorMessage(offlineMessage(error));
    }
  }));

  context.subscriptions.push(vscode.commands.registerCommand('identityos.rememberSelection', async () => {
    const identityId = await selectedIdentity(context);
    const editor = vscode.window.activeTextEditor;
    const selection = editor?.document.getText(editor.selection).trim();
    if (!identityId || !selection) return;
    const note = await vscode.window.showInputBox({
      prompt: 'What coding preference should this selection demonstrate?',
      value: selection.slice(0, 160),
    });
    if (!note) return;
    const project = workspacePartition();
    try {
      await client().remember(identityId, `[${project.label} coding preference] ${note}`, {
        userId: project.userId,
        tags: ['vscode', 'coding-style', project.label],
      });
      await refreshCache(context, identityId);
      vscode.window.showInformationMessage('IdentityOS remembered this coding preference.');
    } catch (error) { vscode.window.showErrorMessage(offlineMessage(error)); }
  }));

  context.subscriptions.push(vscode.commands.registerCommand('identityos.addProjectGoal', async () => {
    const identityId = await selectedIdentity(context);
    if (!identityId) return;
    const title = await vscode.window.showInputBox({ prompt: 'Long-term software goal' });
    if (!title) return;
    const project = workspacePartition();
    try {
      await client().addGoal(identityId, title, {
        description: `VS Code project: ${project.label}`,
        priority: 'high',
        scope: 'persistent',
      });
      await refreshCache(context, identityId);
      vscode.window.showInformationMessage('IdentityOS saved the project goal.');
    } catch (error) { vscode.window.showErrorMessage(offlineMessage(error)); }
  }));

  context.subscriptions.push(vscode.commands.registerCommand('identityos.showStatus', async () => {
    const identityId = context.workspaceState.get(SELECTED_KEY);
    if (!identityId) return vscode.window.showInformationMessage('No identity selected for this workspace.');
    const cached = context.globalState.get(`${CACHE_PREFIX}${identityId}`);
    const detail = cached
      ? `${cached.snapshot.name || identityId}, cached ${cached.cachedAt}`
      : `${identityId}, no offline snapshot cached yet`;
    return vscode.window.showInformationMessage(`IdentityOS: ${detail}`);
  }));
}

function deactivate() {}

module.exports = { activate, deactivate, workspacePartition };
