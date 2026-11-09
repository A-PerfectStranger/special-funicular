// Persist fixed categories only. Browser errors can contain callback codes or credentials.
const networkCodes = new Set([
  'ERR_CONNECTION_CLOSED', 'ERR_CONNECTION_RESET', 'ERR_CONNECTION_REFUSED',
  'ERR_CONNECTION_TIMED_OUT', 'ERR_TIMED_OUT', 'ERR_NAME_NOT_RESOLVED',
  'ERR_HTTP2_PROTOCOL_ERROR', 'ERR_CERT_AUTHORITY_INVALID', 'ERR_CERT_COMMON_NAME_INVALID',
  'ERR_CERT_DATE_INVALID', 'ERR_ABORTED', 'ERR_NETWORK_CHANGED', 'ERR_SSL_PROTOCOL_ERROR',
]);

export function safeFailure(error) {
  const message = typeof error?.message === 'string' ? error.message : '';
  const code = message.match(/net::(ERR_[A-Z_]+)\b/)?.[1];
  return {
    failure_kind: code ? 'browser_network' : error?.name === 'TimeoutError' ? 'timeout'
      : ['Acceptance assertion failed', 'Trial assertion failed'].includes(message) ? 'assertion' : 'unknown',
    network_error: code ? networkCodes.has(code) ? code : 'OTHER_NETWORK_ERROR' : null,
  };
}

export function documentScope(url, apiOrigin, providerOrigin) {
  try {
    const origin = new URL(url).origin;
    return origin === apiOrigin ? 'api' : origin === providerOrigin ? 'provider' : 'other';
  } catch { return 'other'; }
}
