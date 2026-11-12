import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import type { IdentityClient } from './identity';
import { registerDevice } from './notificationRegistration';

export async function registerNotifications(identity: IdentityClient): Promise<string> {
  const projectId = Constants.easConfig?.projectId ?? Constants.expoConfig?.extra?.eas?.projectId;
  return registerDevice({
    available: Device.isDevice && Platform.OS === 'android' && Boolean(projectId)
      && Constants.expoConfig?.extra?.pushConfigured === true,
    createChannel: () => Notifications.setNotificationChannelAsync('account-updates', {
      name: 'Actualizaciones de cuenta', importance: Notifications.AndroidImportance.DEFAULT,
      lockscreenVisibility: Notifications.AndroidNotificationVisibility.PRIVATE,
    }),
    permission: async () => {
      let permission = await Notifications.getPermissionsAsync();
      if (permission.status !== 'granted' && permission.canAskAgain) permission = await Notifications.requestPermissionsAsync();
      return permission.status === 'granted';
    },
    deviceToken: () => Notifications.getDevicePushTokenAsync(),
    expoToken: devicePushToken => Notifications.getExpoPushTokenAsync({ projectId, devicePushToken }),
    register: token => identity.familyRequest('/v1/me/notification-device', { token, enabled: true }),
  });
}

export async function unregisterNotifications(identity: IdentityClient, token: string): Promise<void> {
  await identity.familyRequest('/v1/me/notification-device', { token, enabled: false });
}
