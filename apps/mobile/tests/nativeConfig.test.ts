import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

// Execute the actual Expo plugins together. Image-picker's cameraPermission=false
// blocks every camera module, even when expo-camera requests CAMERA separately.
for (const environment of ['development', 'staging']) {
  test(`${environment} native manifest allows QR camera and excludes microphone`, () => {
    const cwd = fileURLToPath(new URL('..', import.meta.url));
    const cli = fileURLToPath(new URL('../../../node_modules/expo/bin/cli', import.meta.url));
    const config = JSON.parse(execFileSync(process.execPath, [cli, 'config', '--type', 'introspect', '--json'], {
      cwd, encoding: 'utf8', env: { ...process.env, EXPO_NO_DOTENV: '1', APP_ENV: environment,
        EXPO_PUBLIC_API_URL: 'https://synthetic.invalid', ANDROID_PACKAGE_ID: 'org.retiroseguro.staging',
        MOBILE_OIDC_SCHEME: 'retiro-seguro-staging', EXPO_PUBLIC_OIDC_REDIRECT_URI: 'retiro-seguro-staging://auth/callback' },
      stdio: ['ignore', 'pipe', 'pipe'],
    }));
    const entries: { $: Record<string, string> }[] = config._internal.modResults.android.manifest.manifest['uses-permission'];
    const active = entries.filter(e => e.$['tools:node'] !== 'remove').map(e => e.$['android:name']);
    assert(active.includes('android.permission.CAMERA'));
    assert(!active.includes('android.permission.RECORD_AUDIO'));
    assert(!entries.some(e => e.$['android:name'] === 'android.permission.CAMERA' && e.$['tools:node'] === 'remove'));
  });
}
