# IdentityOS JavaScript SDK

A zero-dependency Node.js client for the public IdentityOS REST API.

```js
const { IdentityClient } = require('@identityos/sdk');

const client = new IdentityClient({ baseUrl: 'http://localhost:8000' });
const reply = await client.chat('adam', 'Help me review this file.', {
  userId: 'vscode:my-project',
});
console.log(reply.output);
```

The client supports API-key authentication and exposes identity listing,
creation, chat, memory, and goal operations. It requires Node.js 18+ for the
built-in `fetch` implementation.
