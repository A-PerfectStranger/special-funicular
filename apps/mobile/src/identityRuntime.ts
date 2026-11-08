import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';
import * as WebBrowser from 'expo-web-browser';
import { IdentityClient } from './identity';

WebBrowser.maybeCompleteAuthSession();
const refreshKey = 'retiro.identity.refresh.v1';
const toUrlSafe = (value: string) => value.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

export function createIdentityClient(): IdentityClient {
  const apiUrl = process.env.EXPO_PUBLIC_API_URL;
  const redirectUri = process.env.EXPO_PUBLIC_OIDC_REDIRECT_URI;
  if (!apiUrl || !redirectUri) throw new Error('Identity is not configured');
  return new IdentityClient({
    apiUrl, redirectUri, request: fetch,
    readRefresh: () => SecureStore.getItemAsync(refreshKey),
    writeRefresh: value => SecureStore.setItemAsync(refreshKey, value, {
      keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
    }),
    clearRefresh: () => SecureStore.deleteItemAsync(refreshKey),
    pkce: async () => {
      const verifier = toUrlSafe(btoa(String.fromCharCode(...Crypto.getRandomBytes(32))));
      const challenge = toUrlSafe(await Crypto.digestStringAsync(
        Crypto.CryptoDigestAlgorithm.SHA256, verifier, { encoding: Crypto.CryptoEncoding.BASE64 },
      ));
      return { verifier, challenge };
    },
    browser: async (url, redirect) => {
      const result = await WebBrowser.openAuthSessionAsync(url, redirect, { preferEphemeralSession: true });
      return result.type === 'success' ? result.url : null;
    },
  });
}
