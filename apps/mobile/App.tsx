import { useEffect, useRef, useState } from 'react';
import { AppState, Button, SafeAreaView, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Family } from './src/Family';
import { Guard } from './src/Guard';
import { readCapabilities } from './src/capabilities';
import type { IdentityClient, MobileRole } from './src/identity';
import { createIdentityClient } from './src/identityRuntime';
import { SessionVisibility } from './src/sessionVisibility';
import { clearQrShares } from './src/qrShareRuntime';
import { History } from './src/History';
import { registerNotifications, unregisterNotifications } from './src/notificationRuntime';
import Constants from 'expo-constants';

export default function App() {
  const [status, setStatus] = useState('Sin comprobar conexión. Retiros deshabilitados.');
  const [familyEnabled, setFamilyEnabled] = useState(false);
  const [pickupEnabled, setPickupEnabled] = useState(false);
  const [operationsEnabled, setOperationsEnabled] = useState(false);
  const pushToken = useRef<string | null>(null);
  const [invitation, setInvitation] = useState('');
  const [pending, setPending] = useState(false);
  const [role, setRole] = useState<MobileRole | null>(null);
  const [sessionVisible, setSessionVisible] = useState(false);
  const [identity] = useState<IdentityClient | null>(() => {
    try { return createIdentityClient(); } catch { return null; }
  });
  const configured = Boolean(process.env.EXPO_PUBLIC_OIDC_REDIRECT_URI);
  const [visibility] = useState(() => new SessionVisibility(
    async () => {
      if (!identity) throw new Error('Identity unavailable');
      return identity.check();
    },
    (nextRole, visible, denied) => {
      if (nextRole !== undefined) setRole(nextRole);
      setSessionVisible(visible);
      if (denied) setStatus('Se requiere conexión e ingreso vigente. Retiros deshabilitados.');
    },
  ));

  useEffect(() => {
    if (!configured) return;
    let active = true;
    const endpoint = process.env.EXPO_PUBLIC_API_URL;
    if (endpoint) fetch(`${endpoint}/v1/operations/capabilities`, {
      cache: 'no-store', credentials: 'omit', redirect: 'error', signal: AbortSignal.timeout(5000),
    }).then(async response => response.ok ? response.json() : null).then(value => {
      if (active) setOperationsEnabled(value?.operations_enabled === true);
    }).catch(() => { if (active) setOperationsEnabled(false); });
    if (endpoint) fetch(`${endpoint}/v1/family/capabilities`, {
      cache: 'no-store', credentials: 'omit', redirect: 'error', signal: AbortSignal.timeout(5000),
    }).then(async response => response.ok ? response.json() : null).then(value => {
      if (active) setFamilyEnabled(value?.family_enabled === true && value?.pickup_enabled === false);
    }).catch(() => { if (active) setFamilyEnabled(false); });
    if (endpoint) fetch(`${endpoint}/v1/pickup/capabilities`, {
      cache: 'no-store', credentials: 'omit', redirect: 'error', signal: AbortSignal.timeout(5000),
    }).then(async response => response.ok ? response.json() : null).then(value => {
      if (!active) return;
      clearQrShares();
      setPickupEnabled(value?.pickup_enabled === true && value?.synthetic_only === true);
    }).catch(() => { if (active) setPickupEnabled(false); });
    visibility.start(AppState.currentState);
    const subscription = AppState.addEventListener('change', state => visibility.changed(state));
    return () => { active = false; subscription.remove(); visibility.dispose(); };
  }, [configured, visibility]);

  async function signIn(reauthenticate = false) {
    setPending(true);
    visibility.beginInteractive();
    try {
      if (!identity) throw new Error('Identity unavailable');
      visibility.finishInteractive(await identity.login(reauthenticate));
      setStatus(pickupEnabled ? 'Identidad validada. Ensayo de retiro solo con datos sintéticos.' : 'Identidad validada en línea. Retiros deshabilitados.');
    } catch { visibility.finishInteractive(null); setStatus('No fue posible validar la identidad. Vuelve a ingresar con MFA.'); }
    finally { setPending(false); }
  }

  async function activate() {
    const token = invitation;
    setInvitation(''); visibility.beginInteractive(); setPending(true);
    try {
      if (!identity) throw new Error('Identity unavailable');
      await identity.activate(token);
      setStatus('Cuenta activada. Ingresa con MFA para consultar tu familia.');
    } catch { setStatus('No se pudo activar. Verifica invitación, contacto verificado y vigencia.'); }
    finally { visibility.finishInteractive(null); setPending(false); }
  }

  async function signOut() {
    visibility.beginInteractive();
    setPending(true);
    try {
      if (identity && pushToken.current) {
        await unregisterNotifications(identity, pushToken.current).catch(() => undefined);
      }
      pushToken.current = null;
      const revoked = await identity?.logout();
      setStatus(revoked ? 'Sesión revocada y datos locales borrados.'
        : 'Datos locales borrados. Revocación en servidor sin confirmar.');
    } catch { setStatus('Acceso local bloqueado. No fue posible confirmar el cierre de sesión.'); }
    finally { visibility.finishInteractive(null); setPending(false); }
  }

  async function enableNotifications() {
    if (!identity) return;
    setPending(true);
    try {
      pushToken.current = await registerNotifications(identity);
      setStatus('Dispositivo registrado para avisos genéricos. Su recepción depende de la conexión y del proveedor.');
    } catch { setStatus('No se pudieron habilitar los avisos. Revisa permisos, conexión y configuración del servicio.'); }
    finally { setPending(false); }
  }

  async function checkConnection() {
    setPending(true);
    setStatus('Comprobando disponibilidad técnica. Retiros deshabilitados.');
    try {
      const endpoint = process.env.EXPO_PUBLIC_API_URL;
      if (!endpoint) throw new Error('No endpoint');
      const response = await fetch(`${endpoint}/v1/capabilities`, {
        cache: 'no-store', signal: AbortSignal.timeout(5000),
      });
      if (!response.ok || !readCapabilities(await response.json())) throw new Error('Unavailable');
      setStatus(pickupEnabled ? 'Conexión técnica disponible. Cada entrega sintética exige permiso en línea.' : 'Conexión técnica disponible. Retiros deshabilitados.');
    } catch {
      setStatus('Servicio no disponible. No se autoriza ningún retiro.');
    } finally {
      setPending(false);
    }
  }

  return (
    <SafeAreaView style={styles.container}><ScrollView>
      <View style={styles.card}>
        <Text style={styles.title}>Retiro seguro · Desarrollo</Text>
        <Text>{pickupEnabled ? 'Ensayo sintético de puerta. No usar con estudiantes reales.' : 'Ensayo con datos sintéticos. Retiros deshabilitados.'}</Text>
        <Text accessibilityLiveRegion="polite">{status}</Text>
        <Button title="Comprobar conexión" disabled={pending} onPress={checkConnection} />
        {configured && familyEnabled && !role && <>
          <TextInput accessibilityLabel="Invitación de activación" placeholder="Invitación recibida" secureTextEntry
            autoCapitalize="none" autoCorrect={false} value={invitation} onChangeText={setInvitation} maxLength={43} />
          <Button title="Activar con invitación y MFA" disabled={pending || invitation.length !== 43} onPress={activate} />
        </>}
        {configured && <Button title="Ingresar con MFA" disabled={pending} onPress={() => signIn()} />}
        <View style={{ display: sessionVisible ? 'flex' : 'none', gap: 12 }}
          accessibilityElementsHidden={!sessionVisible}
          importantForAccessibility={sessionVisible ? 'auto' : 'no-hide-descendants'}
          pointerEvents={sessionVisible ? 'auto' : 'none'}>
        {role && <>
          <Text>{role === 'PADRE' ? 'Cuenta de padre' : 'Cuenta de guardia'}</Text>
          <Button title="Reautenticar con MFA" disabled={pending} onPress={() => signIn(true)} />
          <Button title="Cerrar sesión" disabled={pending} onPress={signOut} />
        </>}
        {familyEnabled && role === 'PADRE' && identity && <Family identity={identity} pickupEnabled={pickupEnabled}
          photoActivity={select => visibility.photoActivity(select)} />}
        {familyEnabled && Constants.expoConfig?.extra?.pushConfigured === true && role === 'PADRE' && identity &&
          <Button title="Habilitar avisos en este Android" disabled={pending} onPress={enableNotifications} />
        }
        {operationsEnabled && role === 'PADRE' && identity && <>
          <History identity={identity} />
        </>}
        {pickupEnabled && role === 'GUARDIA' && identity && <Guard identity={identity} />}
        </View>
      </View>
    </ScrollView></SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 24, backgroundColor: '#eef2f6' },
  card: { gap: 20, padding: 24, backgroundColor: '#fff', borderRadius: 12 },
  title: { fontSize: 24, fontWeight: '600' },
});
