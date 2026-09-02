'use strict';

const assert = require('assert');
const { IdentityClient, IdentityClientError } = require('./index');

const calls = [];
const mockFetch = async (url, options = {}) => {
  calls.push({ url, options });
  return {
    ok: true,
    status: 200,
    text: async () => JSON.stringify(url.endsWith('/identity')
      ? { identities: ['adam'] }
      : { output: 'hello', status: 'ok' }),
  };
};

(async () => {
  const client = new IdentityClient({
    baseUrl: 'http://runtime.test/', apiKey: 'test-key', fetch: mockFetch,
  });
  assert.deepStrictEqual(await client.listIdentities(), [{ id: 'adam', name: 'adam' }]);
  await client.exportIdentity('adam');
  await client.chat('adam', 'hello', { userId: 'vscode:project:abc' });
  await client.remember('adam', 'Use type hints', { tags: ['coding-style'] });
  await client.addGoal('adam', 'Ship the parser');
  assert.strictEqual(calls.length, 5);
  assert(calls.every((call) => call.options.headers['X-API-Key'] === 'test-key'));
  assert(JSON.parse(calls[2].options.body).user_id === 'vscode:project:abc');

  const unavailable = new IdentityClient({
    fetch: async () => { throw new Error('offline'); },
  });
  await assert.rejects(() => unavailable.health(), (error) =>
    error instanceof IdentityClientError && error.status === 0
  );
  process.stdout.write('JavaScript SDK contract passed.\n');
})().catch((error) => {
  process.stderr.write(`${error.stack}\n`);
  process.exitCode = 1;
});
