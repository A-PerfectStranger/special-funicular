import React, { useState } from 'react';
import { Pressable, SafeAreaView, StyleSheet, Text, View } from 'react-native';
import { previewFor, type PreviewRole } from './src/preview';

export default function App() {
  const [role, setRole] = useState<PreviewRole | null>(null);
  return (
    <SafeAreaView style={styles.root}>
      <Text style={styles.title}>Retiro seguro</Text>
      <Text>Demostración sintética · E0</Text>
      <Text accessibilityRole="alert" style={styles.warning}>Retiro de estudiantes deshabilitado</Text>
      <Text>Identidad y acceso estarán disponibles en una fase posterior.</Text>
      <View style={styles.actions}>
        {(['PADRE', 'GUARDIA'] as const).map(item => (
          <Pressable key={item} accessibilityRole="button" style={styles.button} onPress={() => setRole(item)}>
            <Text style={styles.label}>Vista de ejemplo: {item === 'PADRE' ? 'padre' : 'guardia'}</Text>
          </Pressable>
        ))}
      </View>
      {role && <Text>{previewFor(role).message}</Text>}
      <Text>Sin datos de estudiantes, QR ni permisos de entrega. Esta vista no inicia una sesión.</Text>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, padding: 24, gap: 20, backgroundColor: '#f3f6fa', justifyContent: 'center' },
  title: { fontSize: 32, fontWeight: '700', color: '#18324f' },
  warning: { color: '#8b1d13', fontSize: 20, fontWeight: '600' },
  actions: { gap: 12 },
  button: { padding: 16, backgroundColor: '#18324f', borderRadius: 8 },
  label: { color: '#ffffff', fontSize: 16 },
});
