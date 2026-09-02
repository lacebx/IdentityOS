export interface ClientOptions {
  baseUrl?: string;
  apiKey?: string;
  fetch?: typeof globalThis.fetch;
}

export class IdentityClientError extends Error {
  status: number;
}

export class IdentityClient {
  constructor(options?: ClientOptions);
  health(): Promise<Record<string, unknown>>;
  listIdentities(): Promise<Array<{id: string; name: string}>>;
  getIdentity(identityId: string): Promise<Record<string, unknown>>;
  exportIdentity(identityId: string): Promise<Record<string, unknown>>;
  createIdentity(identityId: string, name?: string, options?: Record<string, unknown>): Promise<Record<string, unknown>>;
  chat(identityId: string, message: string, options?: {userId?: string; sessionId?: string}): Promise<Record<string, unknown>>;
  remember(identityId: string, content: string, options?: {userId?: string; memoryType?: string; tags?: string[]}): Promise<Record<string, unknown>>;
  addGoal(identityId: string, title: string, options?: {description?: string; priority?: string; scope?: string; successCriteria?: string}): Promise<Record<string, unknown>>;
}
