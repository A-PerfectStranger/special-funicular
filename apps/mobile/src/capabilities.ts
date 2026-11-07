export type Capabilities = { api_version: 'v1'; pickup_enabled: false };

// Fail closed on network errors, invalid JSON, or a future unsupported capability.
// E0 never grants permission to hand over a child.
export function readCapabilities(value: unknown): Capabilities | null {
  if (typeof value !== 'object' || value === null) return null;
  const data = value as Record<string, unknown>;
  return data.api_version === 'v1' && data.pickup_enabled === false
    ? { api_version: 'v1', pickup_enabled: false }
    : null;
}
