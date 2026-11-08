import type { ExpoConfig } from 'expo/config';

const environment = process.env.APP_ENV ?? 'development';
if (!['development', 'staging', 'production'].includes(environment)) {
  throw new Error('APP_ENV must be development, staging or production');
}
const sha = process.env.GIT_SHA ?? 'local';
const apiUrl = process.env.EXPO_PUBLIC_API_URL;
if (environment !== 'development' && (!apiUrl || !apiUrl.startsWith('https://'))) {
  throw new Error('Cloud APK requires EXPO_PUBLIC_API_URL with HTTPS');
}
if (environment !== 'development' && !process.env.ANDROID_PACKAGE_ID) {
  throw new Error('Cloud APK requires a registered ANDROID_PACKAGE_ID');
}

const config: ExpoConfig = {
  name: `Retiro seguro${environment === 'production' ? '' : ' · Desarrollo'}`,
  slug: 'retiro-seguro',
  scheme: process.env.MOBILE_OIDC_SCHEME ?? 'retiro-seguro-dev',
  version: '0.1.0',
  orientation: 'portrait',
  userInterfaceStyle: 'light',
  runtimeVersion: '0.1.0',
  updates: { enabled: false },
  plugins: ['./plugins/withPinnedGradle.cjs', 'expo-web-browser', 'expo-secure-store'],
  android: {
    package: process.env.ANDROID_PACKAGE_ID ?? 'org.example.retiro.development',
    versionCode: 1,
    blockedPermissions: ['android.permission.RECORD_AUDIO', 'android.permission.CAMERA'],
  },
  extra: { environment, gitSha: sha, pickupEnabled: false },
};
export default config;
