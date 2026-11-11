import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import type { IdentityClient } from './identity';

export async function registerNotifications(identity: IdentityClient): Promise<string> {
  const projectId = Constants.easConfig?.projectId ?? Constants.expoConfig?.extra?.eas?.projectId;
  if (!Device.isDevice || Platform.OS !== 'android' || !projectId || Constants.expoConfig?.extra?.pushConfigured !== true) throw new Error('Push unavailable');
  await Notifications.setNotificationChannelAsync('account-updates', {
    name: 'Actualizaciones de cuenta', importance: Notifications.AndroidImportance.DEFAULT,
    lockscreenVisibility: Notifications.AndroidNotificationVisibility.PRIVATE,
  });
  let permission = await Notifications.getPermissionsAsync();
  if (permission.status !== 'granted') permission = await Notifications.requestPermissionsAsync();
  if (permission.status !== 'granted') throw new Error('Push permission denied');
  const result = await Notifications.getExpoPushTokenAsync({ projectId });
  await identity.familyRequest('/v1/me/notification-device', { token: result.data, enabled: true });
  return result.data;
}

export async function unregisterNotifications(identity: IdentityClient, token: string): Promise<void> {
  await identity.familyRequest('/v1/me/notification-device', { token, enabled: false });
}
