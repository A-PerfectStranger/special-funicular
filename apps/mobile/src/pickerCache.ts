// The user's original library asset must never be deleted by photo cleanup.
export function isTemporaryPhoto(uri: string, cacheUri: string): boolean {
  try {
    if (uri.includes('%') || uri.includes('\\')) return false;
    const selected = new URL(uri), cache = new URL(cacheUri);
    const root = cache.pathname.endsWith('/') ? cache.pathname : cache.pathname + '/';
    return selected.protocol === 'file:' && cache.protocol === 'file:' &&
      selected.host === cache.host && !selected.search && !selected.hash &&
      selected.pathname.startsWith(root) && selected.pathname.length > root.length;
  } catch { return false; }
}
