import { useEffect, useRef, useState } from 'react';
import { AppState, Button, SafeAreaView, StyleSheet, Text, View } from 'react-native';
import { readCapabilities } from './src/capabilities';
import type { IdentityClient, MobileRole } from './src/identity';
import { createIdentityClient } from './src/identityRuntime';

export default function App() {
  const [status, setStatus] = useState('Sin comprobar conexión. Retiros deshabilitados.');
  const [pending, setPending] = useState(false);
  const [role, setRole] = useState<MobileRole | null>(null);
  const identity = useRef<IdentityClient | null>(null);
  const configured = Boolean(process.env.EXPO_PUBLIC_OIDC_REDIRECT_URI);

  useEffect(() => {
    if (!configured) return;
    try { identity.current = createIdentityClient(); } catch { return; }
    const subscription = AppState.addEventListener('change', state => {
      setRole(null);
      if (state === 'active') {
        identity.current?.check().then(setRole).catch(() => {
          setStatus('Se requiere conexión e ingreso vigente. Retiros deshabilitados.');
        });
      }
    });
    return () => subscription.remove();
  }, [configured]);

  async function signIn(reauthenticate = false) {
    setPending(true);
    setRole(null);
    try {
      if (!identity.current) throw new Error('Identity unavailable');
      setRole(await identity.current.login(reauthenticate));
      setStatus('Identidad validada en línea. Retiros deshabilitados.');
    } catch { setStatus('No fue posible validar la identidad. Vuelve a ingresar con MFA.'); }
    finally { setPending(false); }
  }

  async function signOut() {
    setRole(null);
    setPending(true);
    try {
      const revoked = await identity.current?.logout();
      setStatus(revoked ? 'Sesión revocada y datos locales borrados.'
        : 'Datos locales borrados. Revocación en servidor sin confirmar.');
    } catch { setStatus('Datos locales borrados. Revocación en servidor sin confirmar.'); }
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
    <SafeAreaView style={styles.container}>
      <View style={styles.card}>
        <Text style={styles.title}>Retiro seguro · Desarrollo</Text>
        <Text>Ensayo con datos sintéticos. Retiros deshabilitados.</Text>
        {role && <Text>{role === 'PADRE' ? 'Cuenta de padre' : 'Cuenta de guardia'}</Text>}
        <Text accessibilityLiveRegion="polite">{status}</Text>
        <Button title="Comprobar conexión" disabled={pending} onPress={checkConnection} />
        {configured && <Button title="Ingresar con MFA" disabled={pending} onPress={() => signIn()} />}
        {role && <>
          <Button title="Reautenticar con MFA" disabled={pending} onPress={() => signIn(true)} />
          <Button title="Cerrar sesión" disabled={pending} onPress={signOut} />
        </>}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 24, backgroundColor: '#eef2f6' },
  card: { gap: 20, padding: 24, backgroundColor: '#fff', borderRadius: 12 },
  title: { fontSize: 24, fontWeight: '600' },
});
