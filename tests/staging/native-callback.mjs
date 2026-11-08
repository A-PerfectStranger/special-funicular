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
  // Managed Login can return HTML that assigns window.location instead of an HTTP redirect.
  // Observe the requested main-frame navigation before Chromium delegates the native scheme.
  const navigation = event => {
    try {
      if (event.frameId !== mainFrame || completed) return;
      const url = new URL(event.url);
      if (['http:', 'https:'].includes(url.protocol)) return;
      completed = true;
      clearTimeout(timer);
      if (event.url.startsWith(redirect + '?')) resolve(event.url);
      else reject(new Error('Unregistered native callback'));
    } catch { reject(new Error('Native callback capture failed')); }
  };
  await session.send('Page.enable');
  const mainFrame = (await session.send('Page.getFrameTree')).frameTree.frame.id;
  session.on('Page.frameRequestedNavigation', navigation);
  session.on('Page.frameScheduledNavigation', navigation);
  session.on('Fetch.requestPaused', handler);
  await session.send('Fetch.enable', { patterns: [{ resourceType: 'Document', requestStage: 'Response' }] });
  return {
    callback,
    dispose: async () => {
      clearTimeout(timer);
      await session.send('Fetch.disable').catch(() => {});
      session.off('Fetch.requestPaused', handler);
      session.off('Page.frameRequestedNavigation', navigation);
      session.off('Page.frameScheduledNavigation', navigation);
      if (!completed) reject(new Error('Native callback cancelled'));
      await session.detach().catch(() => {});
    },
  };
}
