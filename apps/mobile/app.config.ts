import type { ExpoConfig } from 'expo/config';

const environment = process.env.APP_ENV ?? 'development';
if (!['development', 'staging', 'production'].includes(environment)) {
  throw new Error('APP_ENV must be development, staging or production');
}
const sha = process.env.GIT_SHA ?? 'local';
const apiUrl = process.env.EXPO_PUBLIC_API_URL;
const projectId = process.env.EAS_PROJECT_ID ?? '8d55d0cb-2d9f-4a73-bac3-6ad7cab1f04f';
if (environment !== 'development' && (!apiUrl || !apiUrl.startsWith('https://'))) {
  throw new Error('Cloud APK requires EXPO_PUBLIC_API_URL with HTTPS');
}
if (environment !== 'development' && !process.env.ANDROID_PACKAGE_ID) {
  throw new Error('Cloud APK requires a registered ANDROID_PACKAGE_ID');
}
if (environment === 'staging' && (
  process.env.ANDROID_PACKAGE_ID !== 'org.retiroseguro.staging' ||
  process.env.MOBILE_OIDC_SCHEME !== 'retiro-seguro-staging' ||
  process.env.EXPO_PUBLIC_OIDC_REDIRECT_URI !== 'retiro-seguro-staging://auth/callback'
)) throw new Error('Staging APK requires the registered OIDC scheme and callback');
if (environment === 'production' && (
  process.env.ANDROID_PACKAGE_ID !== 'org.retiroseguro.app' ||
  process.env.MOBILE_OIDC_SCHEME !== 'retiro-seguro' ||
  process.env.EXPO_PUBLIC_OIDC_REDIRECT_URI !== 'retiro-seguro://auth/callback'
)) throw new Error('Production requires its separate package, OIDC scheme and callback');

const config: ExpoConfig = {
  owner: '43s1r',
  name: `Retiro seguro${environment === 'production' ? '' : environment === 'staging' ? ' · Ensayo' : ' · Desarrollo'}`,
  slug: 'retiro-seguro',
  scheme: process.env.MOBILE_OIDC_SCHEME ?? 'retiro-seguro-dev',
  version: '0.1.0',
  orientation: 'portrait',
  userInterfaceStyle: 'light',
  runtimeVersion: '0.1.0',
  updates: { enabled: false },
  plugins: ['./plugins/withPinnedGradle.cjs', 'expo-web-browser', 'expo-secure-store', 'expo-sharing',
    'expo-notifications',
    ['expo-camera', { cameraPermission: 'Escanea el QR de retiro para la verificación presencial.', recordAudioAndroid: false }],
    ['expo-image-picker', { photosPermission: 'Selecciona la foto del cuidador para autorizar su identificación.', cameraPermission: 'Escanea el QR de retiro para la verificación presencial.', microphonePermission: false }]],
  android: {
    package: process.env.ANDROID_PACKAGE_ID ?? 'org.example.retiro.development',
    versionCode: 1,
    blockedPermissions: ['android.permission.RECORD_AUDIO'],
    ...(process.env.ANDROID_GOOGLE_SERVICES_FILE ? { googleServicesFile: process.env.ANDROID_GOOGLE_SERVICES_FILE } : {}),
  },
  extra: { environment, gitSha: sha, pickupEnabled: false, pushConfigured: Boolean(process.env.ANDROID_GOOGLE_SERVICES_FILE), ...(projectId ? { eas: { projectId } } : {}) },
};
export default config;
