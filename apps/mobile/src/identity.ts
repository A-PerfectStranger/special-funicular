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

export class PickupRequestError extends Error {
  readonly status: number;
  constructor(status: number) { super('Online pickup request failed'); this.status = status; }
}

export class IdentityClient {
  private access: string | null = null;
  private generation = 0;
  private inFlight: Promise<void> | null = null;
  private role: MobileRole | null = null;
  private authenticating = false;
  private closing = false;
  private requiresLogin = false;
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
      this.requiresLogin = false;
    });
    await this.storage;
  }

  async login(reauthenticate = false): Promise<MobileRole> {
    if (this.authenticating || this.closing) throw new Error('Authentication in progress');
    if (reauthenticate) await this.check();
    this.authenticating = true;
    try {
      if (!reauthenticate) await this.logout();
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
      this.authenticating = false;
      return await this.check();
    } finally { this.authenticating = false; }
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
    if (this.authenticating || this.closing || this.requiresLogin) throw new Error('Login required');
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

  async familyRequest<T>(path: string, payload?: object, key?: string): Promise<T> {
    if (!/^\/v1\/(students|caregivers|authorizations)(\/|$)/.test(path)) throw new Error('Invalid route');
    await this.check();
    const generation = this.generation;
    const response = await this.dependencies.request(`${this.dependencies.apiUrl}${path}`, {
      method: payload ? 'POST' : 'GET', cache: 'no-store', credentials: 'omit', redirect: 'error',
      headers: { Authorization: `Bearer ${this.access}`, ...(payload
        ? { 'Content-Type': 'application/json', 'Idempotency-Key': key ?? '' } : {}) },
      ...(payload ? { body: JSON.stringify(payload) } : {}), signal: AbortSignal.timeout(10000),
    });
    if (!response.ok || generation !== this.generation) throw new Error('Online family request failed');
    const result = await response.json();
    if (generation !== this.generation) throw new Error('Session changed');
    return result as T;
  }

  async pickupRequest<T>(path: string, payload?: object, key?: string): Promise<T> {
    if (!/^\/v1\/(guard\/(resolve-qr|confirm-pickup|operations\/[0-9a-f-]+(?:\/report-handover)?)|authorizations\/[0-9a-f-]+\/(issue-qr|reschedule))$/.test(path)) throw new Error('Invalid route');
    await this.check();
    const generation = this.generation;
    const response = await this.dependencies.request(`${this.dependencies.apiUrl}${path}`, {
      method: payload ? 'POST' : 'GET', cache: 'no-store', credentials: 'omit', redirect: 'error',
      headers: { Authorization: `Bearer ${this.access}`, ...(payload
        ? { 'Content-Type': 'application/json', 'Idempotency-Key': key ?? '' } : {}) },
      ...(payload ? { body: JSON.stringify(payload) } : {}), signal: AbortSignal.timeout(7000),
    });
    if (!response.ok) throw new PickupRequestError(response.status);
    if (generation !== this.generation) throw new Error('Session changed');
    const result = await response.json();
    if (generation !== this.generation) throw new Error('Session changed');
    return result as T;
  }

  async pickupPhoto(token: string): Promise<string> {
    await this.check();
    const generation = this.generation;
    const response = await this.dependencies.request(`${this.dependencies.apiUrl}/v1/guard/caregiver-photo`, {
      method: 'POST', cache: 'no-store', credentials: 'omit', redirect: 'error',
      headers: { Authorization: `Bearer ${this.access}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }), signal: AbortSignal.timeout(5000),
    });
    if (!response.ok || generation !== this.generation) throw new Error('Photo unavailable');
    const bytes = new Uint8Array(await response.arrayBuffer());
    if (bytes.length > 300000 || generation !== this.generation) throw new Error('Photo unavailable');
    let raw = '';
    for (const byte of bytes) raw += String.fromCharCode(byte);
    return `data:image/jpeg;base64,${btoa(raw)}`;
  }

  async activate(invitation: string): Promise<void> {
    if (!validSecret(invitation) || this.authenticating || this.closing) throw new Error('Invalid invitation');
    this.authenticating = true;
    try {
      await this.logout();
      const generation = ++this.generation;
      const pkce = await this.dependencies.pkce();
      const started = await this.post('/v1/auth/mobile/start', {
        code_challenge: pkce.challenge, purpose: 'activate',
      }) as { authorization_url: string; state: string; exchange_key: string };
      if (!validSecret(started.state) || !validSecret(started.exchange_key) ||
          new URL(started.authorization_url).protocol !== 'https:') throw new Error('Invalid login');
      const result = await this.dependencies.browser(started.authorization_url, this.dependencies.redirectUri);
      if (!result || generation !== this.generation) throw new Error('Activation cancelled');
      const callback = new URL(result);
      const expected = new URL(this.dependencies.redirectUri);
      if (callback.protocol !== expected.protocol || callback.host !== expected.host ||
          callback.pathname !== expected.pathname || callback.searchParams.has('error') ||
          callback.searchParams.getAll('state').length !== 1 || callback.searchParams.getAll('code').length !== 1 ||
          callback.searchParams.get('state') !== started.state) throw new Error('Invalid callback');
      const response = await this.post('/v1/activation/redeem', {
        state: started.state, exchange_key: started.exchange_key, code: callback.searchParams.get('code'),
        code_verifier: pkce.verifier, invitation,
      }) as { status: string };
      if (response.status !== 'activated' || generation !== this.generation) throw new Error('Activation denied');
    } finally { this.authenticating = false; }
  }

  async logout(): Promise<boolean> {
    this.closing = true;
    this.requiresLogin = true;
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
      try { await this.dependencies.clearRefresh(); } finally { this.closing = false; }
    }
    return revoked;
  }
}
