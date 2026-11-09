import { File, Paths } from 'expo-file-system';
import { isQrShareFile } from './qrShareCache';

export function clearQrShares() {
  for (const entry of Paths.cache.list()) {
    if (entry instanceof File && isQrShareFile(entry.name)) entry.delete();
  }
}

export function finishQrShare(file: File, handedOff: boolean) {
  if (!handedOff) { if (file.exists) file.delete(); return; }
  // Android resolves the chooser before every receiving app has read its URI.
  // Keep the source available briefly; never use it to recover an operation.
  setTimeout(() => { try { if (file.exists) file.delete(); } catch { /* Next launch retries cache removal. */ } }, 10 * 60000);
}
