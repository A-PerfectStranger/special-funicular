import { useEffect, useState } from 'react';
import { AppState, Button, SafeAreaView, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Family } from './src/Family';
import { readCapabilities } from './src/capabilities';
import type { IdentityClient, MobileRole } from './src/identity';
import { createIdentityClient } from './src/identityRuntime';

export default function App() {
  const [status, setStatus] = useState('Sin comprobar conexión. Retiros deshabilitados.');
  const [familyEnabled, setFamilyEnabled] = useState(false);
  const [invitation, setInvitation] = useState('');
  const [pending, setPending] = useState(false);
  const [role, setRole] = useState<MobileRole | null>(null);
  const [identity] = useState<IdentityClient | null>(() => {
    try { return createIdentityClient(); } catch { return null; }
  });
  const configured = Boolean(process.env.EXPO_PUBLIC_OIDC_REDIRECT_URI);

  useEffect(() => {
    if (!configured) return;
    let active = true;
    const endpoint = process.env.EXPO_PUBLIC_API_URL;
    if (endpoint) fetch(`${endpoint}/v1/family/capabilities`, {
      cache: 'no-store', credentials: 'omit', redirect: 'error', signal: AbortSignal.timeout(5000),
    }).then(async response => response.ok ? response.json() : null).then(value => {
      if (active) setFamilyEnabled(value?.family_enabled === true && value?.pickup_enabled === false);
    }).catch(() => { if (active) setFamilyEnabled(false); });
    const subscription = AppState.addEventListener('change', state => {
      setRole(null);
      if (state === 'active') {
        identity?.check().then(setRole).catch(() => {
          setStatus('Se requiere conexión e ingreso vigente. Retiros deshabilitados.');
        });
      }
    });
    return () => { active = false; subscription.remove(); };
  }, [configured, identity]);

  async function signIn(reauthenticate = false) {
    setPending(true);
    setRole(null);
    try {
      if (!identity) throw new Error('Identity unavailable');
      setRole(await identity.login(reauthenticate));
      setStatus('Identidad validada en línea. Retiros deshabilitados.');
    } catch { setStatus('No fue posible validar la identidad. Vuelve a ingresar con MFA.'); }
    finally { setPending(false); }
  }

  async function activate() {
    const token = invitation;
    setInvitation(''); setRole(null); setPending(true);
    try {
      if (!identity) throw new Error('Identity unavailable');
      await identity.activate(token);
      setStatus('Cuenta activada. Ingresa con MFA para consultar tu familia.');
    } catch { setStatus('No se pudo activar. Verifica invitación, contacto verificado y vigencia.'); }
    finally { setPending(false); }
  }

  async function signOut() {
    setRole(null);
    setPending(true);
    try {
      const revoked = await identity?.logout();
      setStatus(revoked ? 'Sesión revocada y datos locales borrados.'
        : 'Datos locales borrados. Revocación en servidor sin confirmar.');
    } catch { setStatus('Acceso local bloqueado. No fue posible confirmar el cierre de sesión.'); }
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
      setStatus('Conexión técnica disponible. Retiros deshabilitados.');
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
        <Text>Ensayo con datos sintéticos. Retiros deshabilitados.</Text>
        {role && <Text>{role === 'PADRE' ? 'Cuenta de padre' : 'Cuenta de guardia'}</Text>}
        <Text accessibilityLiveRegion="polite">{status}</Text>
        <Button title="Comprobar conexión" disabled={pending} onPress={checkConnection} />
        {configured && familyEnabled && !role && <>
          <TextInput accessibilityLabel="Invitación de activación" placeholder="Invitación recibida" secureTextEntry
            autoCapitalize="none" autoCorrect={false} value={invitation} onChangeText={setInvitation} maxLength={43} />
          <Button title="Activar con invitación y MFA" disabled={pending || invitation.length !== 43} onPress={activate} />
        </>}
        {configured && <Button title="Ingresar con MFA" disabled={pending} onPress={() => signIn()} />}
        {role && <>
          <Button title="Reautenticar con MFA" disabled={pending} onPress={() => signIn(true)} />
          <Button title="Cerrar sesión" disabled={pending} onPress={signOut} />
        </>}
        {familyEnabled && role === 'PADRE' && identity && <Family identity={identity} />}
      </View>
    </ScrollView></SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 24, backgroundColor: '#eef2f6' },
  card: { gap: 20, padding: 24, backgroundColor: '#fff', borderRadius: 12 },
  title: { fontSize: 24, fontWeight: '600' },
});
