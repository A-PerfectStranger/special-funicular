import { useState } from 'react';
import { Button, SafeAreaView, StyleSheet, Text, View } from 'react-native';
import { readCapabilities } from './src/capabilities';

export default function App() {
  const [status, setStatus] = useState('Sin comprobar conexión. Retiros deshabilitados.');
  const [pending, setPending] = useState(false);

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
        <Text>Base E0 con datos sintéticos. Autenticación y flujos por rol pendientes.</Text>
        <Text accessibilityLiveRegion="polite">{status}</Text>
        <Button title="Comprobar conexión" disabled={pending} onPress={checkConnection} />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: 24, backgroundColor: '#eef2f6' },
  card: { gap: 20, padding: 24, backgroundColor: '#fff', borderRadius: 12 },
  title: { fontSize: 24, fontWeight: '600' },
});
