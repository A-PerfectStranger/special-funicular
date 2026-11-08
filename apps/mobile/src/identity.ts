// Credentials persist only through the injected OS secure store; access tokens stay in memory.
export type MobileRole = 'PADRE' | 'GUARDIA';
export type IdentityDependencies = {
  apiUrl: string;
  redirectUri: string;
  request: typeof fetch;
  readRefresh: () => Promise<string | null>;
  writeRefresh: (value: string) => Promise<void>;
  clearRefresh: () => Promise<void>;
  pkce: () => Promise<{ verifier: string; challenge: string }>;
  browser: (url: string, redirect: string) => Promise<string | null>;
};

type Credentials = { access_token: string; refresh_token: string; expires_in: number };
const validSecret = (value: unknown): value is string =>
  typeof value === 'string' && /^[A-Za-z0-9_-]{43}$/.test(value);

export class IdentityClient {
  private access: string | null = null;
  private generation = 0;
  private inFlight: Promise<void> | null = null;
  private role: MobileRole | null = null;
  private storage = Promise.resolve();
  private dependencies: IdentityDependencies;

  constructor(dependencies: IdentityDependencies) {
    this.dependencies = dependencies;
    const endpoint = new URL(dependencies.apiUrl);
    if (endpoint.protocol !== 'https:' && !(
      endpoint.protocol === 'http:' && ['127.0.0.1', 'localhost', '10.0.2.2'].includes(endpoint.hostname)
    )) throw new Error('Secure endpoint required');
  }

  private async post(path: string, payload: object, authenticated = false): Promise<unknown> {
    const response = await this.dependencies.request(`${this.dependencies.apiUrl}${path}`, {
      method: 'POST', cache: 'no-store', credentials: 'omit', redirect: 'error',
      headers: { 'Content-Type': 'application/json', ...(authenticated && this.access
        ? { Authorization: `Bearer ${this.access}` } : {}) },
      body: JSON.stringify(payload), signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) throw new Error('Access denied');
    return response.json();
  }

  private async persist(value: unknown, generation: number): Promise<void> {
    if (!value || typeof value !== 'object') throw new Error('Invalid session');
    const tokens = value as Credentials;
    if (!validSecret(tokens.access_token) || !validSecret(tokens.refresh_token) || tokens.expires_in !== 300) {
      throw new Error('Invalid session');
    }
    // Serialize storage against logout, including a logout during SecureStore.setItemAsync.
    this.storage = this.storage.catch(() => {}).then(async () => {
      if (generation !== this.generation) throw new Error('Session changed');
      await this.dependencies.writeRefresh(tokens.refresh_token);
      if (generation !== this.generation) {
        await this.dependencies.clearRefresh();
        throw new Error('Session changed');
      }
      this.access = tokens.access_token;
    });
    await this.storage;
  }

  async login(reauthenticate = false): Promise<MobileRole> {
    const generation = ++this.generation;
    const pkce = await this.dependencies.pkce();
    const started = await this.post('/v1/auth/mobile/start', {
      code_challenge: pkce.challenge, purpose: reauthenticate ? 'reauth' : 'login',
    }, reauthenticate) as { authorization_url: string; state: string; exchange_key: string };
    if (!validSecret(started.state) || !validSecret(started.exchange_key) ||
        new URL(started.authorization_url).protocol !== 'https:') throw new Error('Invalid login');
    const result = await this.dependencies.browser(started.authorization_url, this.dependencies.redirectUri);
    if (!result || generation !== this.generation) throw new Error('Login cancelled');
    const callback = new URL(result);
    const expected = new URL(this.dependencies.redirectUri);
    if (callback.protocol !== expected.protocol || callback.host !== expected.host ||
        callback.pathname !== expected.pathname || callback.searchParams.has('error') ||
        callback.searchParams.getAll('state').length !== 1 || callback.searchParams.getAll('code').length !== 1 ||
        callback.searchParams.get('state') !== started.state) throw new Error('Invalid callback');
    const exchanged = await this.post('/v1/auth/mobile/exchange', {
      state: started.state, code: callback.searchParams.get('code'),
      code_verifier: pkce.verifier, exchange_key: started.exchange_key,
    });
    if (reauthenticate) {
      if (!(exchanged as { reauthenticated?: boolean }).reauthenticated) throw new Error('MFA required');
    } else {
      await this.persist(exchanged, generation);
    }
    return this.check();
  }

  private async refresh(): Promise<void> {
    if (this.inFlight) return this.inFlight;
    const generation = this.generation;
    this.inFlight = (async () => {
      const refresh = await this.dependencies.readRefresh();
      if (!validSecret(refresh) || generation !== this.generation) throw new Error('Login required');
      await this.persist(await this.post('/v1/auth/refresh', { refresh_token: refresh }), generation);
    })();
    try { await this.inFlight; } finally { this.inFlight = null; }
  }

  async check(): Promise<MobileRole> {
    const generation = this.generation;
    if (!this.access) await this.refresh();
    const read = () => this.dependencies.request(`${this.dependencies.apiUrl}/v1/me`, {
      cache: 'no-store', credentials: 'omit', redirect: 'error',
      headers: { Authorization: `Bearer ${this.access}` }, signal: AbortSignal.timeout(5000),
    });
    let response = await read();
    if (response.status === 401) {
      await this.refresh();
      response = await read();
    }
    if (!response.ok || generation !== this.generation) {
      this.access = null;
      this.role = null;
      throw new Error('Online validation required');
    }
    const data = await response.json();
    if (generation !== this.generation || !['PADRE', 'GUARDIA'].includes(data.role) || data.pickup_enabled !== false) {
      throw new Error('Unsupported role or capability');
    }
    this.role = data.role;
    return data.role;
  }

  async logout(): Promise<boolean> {
    this.generation++;
    this.role = null;
    // Let any storage write finish before clearing or reading a rotated refresh.
    await this.storage.catch(() => {});
    let revoked = false;
    try {
      const refresh = await this.dependencies.readRefresh();
      if (refresh) {
        await this.post('/v1/auth/logout', { refresh_token: refresh });
        revoked = true;
      }
    } finally {
      this.access = null;
      await this.dependencies.clearRefresh();
    }
    return revoked;
  }
}
