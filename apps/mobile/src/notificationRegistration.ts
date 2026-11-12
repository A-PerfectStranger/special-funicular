// Registration diagnostics contain only fixed support codes, never SDK messages or tokens.
import { FamilyRequestError } from './identity.ts';

type Stage = 'configuration' | 'channel' | 'permission' | 'device' | 'provider' | 'account';
type Failure = 'FAILED' | 'DENIED' | 'INVALID_RESPONSE' | 'TIMEOUT' | 'NATIVE_REGISTRATION'
  | 'PROVIDER_NETWORK' | 'PROVIDER_REJECTED' | 'HTTP_400' | 'HTTP_401' | 'HTTP_403'
  | 'HTTP_404' | 'HTTP_409' | 'HTTP_429' | 'HTTP_500' | 'HTTP_502' | 'HTTP_503' | 'HTTP_504';
const codes: Record<Stage, string> = {
  configuration: 'N01', channel: 'N02', permission: 'N03', device: 'N04', provider: 'N05', account: 'N06',
};
const messages: Record<Stage, string> = {
  configuration: 'Los avisos no están disponibles en esta versión o dispositivo.',
  channel: 'No se pudo preparar el canal de avisos de Android.',
  permission: 'Permite las notificaciones en los ajustes de esta aplicación para habilitar los avisos.',
  device: 'El servicio de notificaciones del teléfono no pudo registrar este dispositivo.',
  provider: 'No se pudo registrar el dispositivo con el proveedor de avisos.',
  account: 'El registro del dispositivo en tu cuenta no está confirmado. Comprueba conexión e ingreso.',
};

export class NotificationRegistrationError extends Error {
  readonly code: string;
  readonly stage: Stage;
  constructor(stage: Stage, failure: Failure = 'FAILED') {
    super('Notification registration was not confirmed');
    this.stage = stage;
    this.code = `${codes[stage]}-${failure}`;
  }
}

export function notificationRegistrationMessage(error: unknown): string {
  if (!(error instanceof NotificationRegistrationError)) {
    return 'El registro de avisos no está confirmado. Código de soporte: N00.';
  }
  return `${messages[error.stage]} Código de soporte: ${error.code}.`;
}

type DeviceToken = { type: 'android'; data: string };
export type NotificationRegistrationDependencies = {
  available: boolean;
  createChannel: () => Promise<unknown>;
  permission: () => Promise<boolean>;
  deviceToken: () => Promise<{ type: string; data: unknown }>;
  expoToken: (device: DeviceToken) => Promise<{ data: unknown }>;
  register: (token: string) => Promise<unknown>;
};

function failure(stage: Stage, error: unknown): Failure {
  if (error instanceof FamilyRequestError && stage === 'account') {
    switch (error.status) {
      case 400: return 'HTTP_400';
      case 401: return 'HTTP_401';
      case 403: return 'HTTP_403';
      case 404: return 'HTTP_404';
      case 409: return 'HTTP_409';
      case 429: return 'HTTP_429';
      case 500: return 'HTTP_500';
      case 502: return 'HTTP_502';
      case 503: return 'HTTP_503';
      case 504: return 'HTTP_504';
    }
  }
  if (error && typeof error === 'object' && 'code' in error) {
    if (stage === 'device' && error.code === 'E_REGISTRATION_FAILED') return 'NATIVE_REGISTRATION';
    if (stage === 'provider' && error.code === 'ERR_NOTIFICATIONS_NETWORK_ERROR') return 'PROVIDER_NETWORK';
    if (stage === 'provider' && error.code === 'ERR_NOTIFICATIONS_SERVER_ERROR') return 'PROVIDER_REJECTED';
  }
  return 'FAILED';
}

async function run<T>(stage: Stage, action: () => Promise<T>, timeoutMs?: number): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const pending = action();
    if (timeoutMs === undefined) return await pending;
    return await Promise.race([pending, new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new NotificationRegistrationError(stage, 'TIMEOUT')), timeoutMs);
    })]);
  } catch (error) {
    if (error instanceof NotificationRegistrationError) throw error;
    throw new NotificationRegistrationError(stage, failure(stage, error));
  } finally { if (timer !== undefined) clearTimeout(timer); }
}

export async function registerDevice(
  dependencies: NotificationRegistrationDependencies, timeoutMs = 15000,
): Promise<string> {
  if (!dependencies.available) throw new NotificationRegistrationError('configuration');
  if (!Number.isFinite(timeoutMs) || timeoutMs < 1 || timeoutMs > 60000) throw new Error('Invalid registration timeout');
  await run('channel', dependencies.createChannel);
  // The native permission dialog waits for the person's choice, without a network deadline.
  if (!await run('permission', dependencies.permission)) {
    throw new NotificationRegistrationError('permission', 'DENIED');
  }
  const device = await run('device', dependencies.deviceToken, timeoutMs);
  if (!device || device.type !== 'android' || typeof device.data !== 'string' || !device.data) {
    throw new NotificationRegistrationError('device', 'INVALID_RESPONSE');
  }
  const nativeToken: DeviceToken = { type: 'android', data: device.data };
  const expo = await run('provider', () => dependencies.expoToken(nativeToken), timeoutMs);
  if (!expo || typeof expo.data !== 'string' || !/^(ExponentPushToken|ExpoPushToken)\[[A-Za-z0-9_-]{10,200}\]$/.test(expo.data)) {
    throw new NotificationRegistrationError('provider', 'INVALID_RESPONSE');
  }
  const token = expo.data;
  const result = await run('account', () => dependencies.register(token), timeoutMs);
  if (!result || typeof result !== 'object' || !('registered' in result) || result.registered !== true) {
    throw new NotificationRegistrationError('account', 'INVALID_RESPONSE');
  }
  return token;
}
