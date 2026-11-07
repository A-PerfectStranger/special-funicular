import type { ExpoConfig } from 'expo/config';

const sha = process.env.RELEASE_SHA ?? 'local';
if (!/^(local|[0-9a-f]{40})$/.test(sha)) throw new Error('RELEASE_SHA inválido');
const config: ExpoConfig = {
  name: 'Retiro seguro · Ensayo',
  slug: 'retiro-seguro-synthetic',
  version: '0.0.1',
  orientation: 'portrait',
  userInterfaceStyle: 'light',
  android: { package: 'org.retiroseguro.synthetic', versionCode: 1, permissions: [], blockedPermissions: ['android.permission.RECORD_AUDIO', 'android.permission.CAMERA'] },
  updates: { enabled: false },
  extra: { releaseSha: sha, syntheticOnly: true, pickupEnabled: false },
};
export default config;
