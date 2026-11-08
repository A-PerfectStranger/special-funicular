// Chromium can suppress response events for redirects to native schemes.
// Capture the response headers before external-protocol navigation, without logging codes.
export async function nativeCallback(page, redirect, timeoutMs = 90000) {
  const session = await page.context().newCDPSession(page);
  let resolve;
  let reject;
  let completed = false;
  const callback = new Promise((accept, deny) => { resolve = accept; reject = deny; });
  callback.catch(() => {});
  const timer = setTimeout(() => reject(new Error('Native callback timeout')), timeoutMs);
  const handler = async event => {
    try {
      const location = event.responseHeaders?.find(header => header.name.toLowerCase() === 'location')?.value;
      if (event.responseStatusCode >= 300 && event.responseStatusCode < 400 &&
          location?.startsWith(redirect + '?')) {
        await session.send('Fetch.failRequest', { requestId: event.requestId, errorReason: 'Aborted' });
        completed = true;
        clearTimeout(timer);
        resolve(location);
      } else if (location && !['http:', 'https:'].includes(new URL(location, event.request.url).protocol)) {
        await session.send('Fetch.failRequest', { requestId: event.requestId, errorReason: 'Aborted' });
        completed = true;
        clearTimeout(timer);
        reject(new Error('Unregistered native callback'));
      } else {
        await session.send('Fetch.continueRequest', { requestId: event.requestId });
      }
    } catch { reject(new Error('Native callback capture failed')); }
  };
  session.on('Fetch.requestPaused', handler);
  await session.send('Fetch.enable', { patterns: [{ resourceType: 'Document', requestStage: 'Response' }] });
  return {
    callback,
    dispose: async () => {
      clearTimeout(timer);
      await session.send('Fetch.disable').catch(() => {});
      session.off('Fetch.requestPaused', handler);
      if (!completed) reject(new Error('Native callback cancelled'));
      await session.detach().catch(() => {});
    },
  };
}
