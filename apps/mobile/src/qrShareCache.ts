// Match only this app's QR share files in its own cache directory.
export function isQrShareFile(name: string): boolean {
  return /^pickup-share-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.png$/.test(name);
}
