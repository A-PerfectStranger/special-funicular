import { useEffect, useRef, useState } from 'react';
import { Button, Text, TextInput, View } from 'react-native';
import * as Crypto from 'expo-crypto';
import * as ImagePicker from 'expo-image-picker';
import { File, Paths } from 'expo-file-system';
import { isTemporaryPhoto } from './pickerCache';
import type { IdentityClient } from './identity';

type Student = { id: string; name: string; timezone: string; principal: boolean; can_authorize: boolean;
  windows: { weekday: number; from: string; until: string; start_date: string; end_date: string }[] };
type Caregiver = { id: string; name: string; document: string; version: number };
type Authorization = { id: string; caregiver_id: string; revoked: boolean;
  schedule: { from: string; until: string }[] };
type Records = { caregivers: Caregiver[]; authorizations: Authorization[] };

export function Family({ identity, photoActivity }: {
  identity: IdentityClient; photoActivity: (select: () => Promise<void>) => Promise<void>;
}) {
  const [students, setStudents] = useState<Student[]>([]);
  const [selected, setSelected] = useState<Student | null>(null);
  const [records, setRecords] = useState<Records>({ caregivers: [], authorizations: [] });
  const [caregiver, setCaregiver] = useState<Caregiver | null>(null);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState('');
  const [document, setDocument] = useState('');
  const [photo, setPhoto] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [weekdays, setWeekdays] = useState('1,2,3,4,5');
  const [from, setFrom] = useState('13:00');
  const [until, setUntil] = useState('13:15');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const mounted = useRef(true);
  const pending = useRef<{ signature: string; key: string } | null>(null);

  useEffect(() => {
    mounted.current = true;
    identity.familyRequest<{ students: Student[] }>('/v1/students').then(result => {
      if (mounted.current) setStudents(result.students);
    }).catch(() => { if (mounted.current) setMessage('Consulta familiar no disponible. Verifica conexión e ingreso.'); });
    return () => { mounted.current = false; };
  }, [identity]);

  async function select(student: Student) {
    setSelected(null); setRecords({ caregivers: [], authorizations: [] }); setCaregiver(null);
    setName(''); setDocument(''); setPhoto(''); setEditing(false); setBusy(true);
    try {
      const result = await identity.familyRequest<Records>(`/v1/students/${student.id}/family`);
      if (!mounted.current) return;
      setRecords(result); setSelected(student); setMessage('Datos consultados en línea.');
    } catch { if (mounted.current) setMessage('No se pudo consultar. Vuelve a ingresar.'); }
    finally { if (mounted.current) setBusy(false); }
  }

  async function choosePhoto() {
    await photoActivity(async () => {
      let uri: string | undefined;
      try {
        const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'],
          base64: true, quality: 0.5, allowsEditing: true, aspect: [1, 1] });
        if (result.canceled) return;
        uri = result.assets[0].uri;
        const encoded = result.assets[0].base64;
        if (!encoded || encoded.length > 400000) throw new Error('Image too large');
        if (mounted.current) setPhoto(encoded);
      } catch { if (mounted.current) setMessage('Selecciona una foto JPEG o PNG más pequeña.'); }
      finally {
        if (uri && isTemporaryPhoto(uri, Paths.cache.uri)) {
          try { new File(uri).delete(); }
          catch { if (mounted.current) { setPhoto(''); setMessage('No se pudo eliminar la copia temporal. Selección descartada.'); } }
        }
      }
    });
  }

  async function mutate(path: string, payload: object) {
    setBusy(true); setMessage('Enviando.');
    // Preserve key/body after an ambiguous response; retry never creates a second logical command.
    const signature = JSON.stringify([path, payload]);
    if (pending.current?.signature !== signature) pending.current = { signature, key: Crypto.randomUUID() };
    try {
      await identity.familyRequest(path, payload, pending.current.key);
      if (!mounted.current) return;
      pending.current = null; setPhoto(''); setName(''); setDocument(''); setEditing(false);
      setMessage('Cambio confirmado en servidor.');
      if (selected) await select(selected);
    } catch {
      if (mounted.current) { setRecords({ caregivers: [], authorizations: [] });
        setMessage('Cambio sin confirmar. Reintenta los mismos datos o reautentica con MFA y consulta de nuevo.'); }
    } finally { if (mounted.current) setBusy(false); }
  }

  return <View style={{ gap: 12 }}>
    <Text accessibilityRole="header">Mi familia</Text>
    <Text accessibilityLiveRegion="polite">{message}</Text>
    {students.map(s => <Button key={s.id} title={`${s.name} · ${s.principal ? 'Principal' : 'Consulta'}`}
      disabled={busy} onPress={() => select(s)} />)}
    {selected && <>
      <Text>{selected.name} · Zona horaria: {selected.timezone}</Text>
      <Text>{selected.principal ? 'Puedes gestionar cuidadores y autorizaciones con MFA reciente.' : 'Vínculo secundario: consulta.'}</Text>
      <Text>Ventanas escolares:</Text>
      {selected.windows.map((w, i) => <Text key={i}>Día ISO {w.weekday}: {w.from}–{w.until}, {w.start_date} a {w.end_date}</Text>)}
      <Text>Cuidadores</Text>
      {records.caregivers.map(c => <Button key={c.id} title={c.name} disabled={busy}
        onPress={() => { setCaregiver(c); setEditing(false); setPhoto(''); setName(''); setDocument(''); }} />)}
      {selected.principal && <>
        {caregiver && <Button title="Editar cuidador seleccionado" disabled={busy} onPress={() => {
          setEditing(true); setName(caregiver.name); setDocument(caregiver.document); setPhoto('');
        }} />}
        <Text>{editing ? 'Actualizar cuidador: revoca sus autorizaciones anteriores.' : 'Nuevo cuidador'}</Text>
        <TextInput accessibilityLabel="Nombre del cuidador" placeholder="Nombre completo" value={name} onChangeText={setName} maxLength={160} />
        <TextInput accessibilityLabel="Documento del cuidador" placeholder="Número de documento (sin copia de cédula)" value={document} onChangeText={setDocument} maxLength={40} />
        <Button title={photo ? 'Foto seleccionada · cambiar' : 'Seleccionar foto del cuidador'} disabled={busy} onPress={choosePhoto} />
        <Button title={editing ? 'Guardar nueva versión' : 'Registrar cuidador'} disabled={busy || !name.trim() || !document.trim() || !photo}
          onPress={() => mutate(editing && caregiver ? `/v1/caregivers/${caregiver.id}/update` : '/v1/caregivers', {
            student_id: selected.id, name, document, photo, ...(editing && caregiver ? { version: caregiver.version } : {}),
          })} />
        {caregiver && <>
          <Text>Autorizar a {caregiver.name}. Fechas y horas en {selected.timezone}.</Text>
          <TextInput accessibilityLabel="Fecha inicial" placeholder="Inicio AAAA-MM-DD" value={start} onChangeText={setStart} />
          <TextInput accessibilityLabel="Fecha final" placeholder="Fin AAAA-MM-DD (igual para una sola fecha)" value={end} onChangeText={setEnd} />
          <TextInput accessibilityLabel="Días de semana" placeholder="Días ISO 1=lunes, 7=domingo, separados por coma" value={weekdays} onChangeText={setWeekdays} />
          <TextInput accessibilityLabel="Hora inicial" placeholder="Hora inicio HH:MM" value={from} onChangeText={setFrom} />
          <TextInput accessibilityLabel="Hora final" placeholder="Hora fin HH:MM" value={until} onChangeText={setUntil} />
          <Button title="Crear autorización" disabled={busy || !selected.can_authorize} onPress={() => mutate('/v1/authorizations', {
            student_id: selected.id, caregiver_id: caregiver.id,
            recurrence: { start_date: start, end_date: end, weekdays: weekdays.split(',').map(Number), from, until },
          })} />
        </>}
      </>}
      <Text>Autorizaciones</Text>
      {records.authorizations.map(a => <View key={a.id}>
        <Text>{records.caregivers.find(c => c.id === a.caregiver_id)?.name} · {a.revoked ? 'Revocada' : 'Registrada'} · {a.schedule.length} fecha(s)</Text>
        {a.schedule.map((s, i) => <Text key={i}>{new Date(s.from).toLocaleString('es-CO', { timeZone: selected.timezone })} — {new Date(s.until).toLocaleString('es-CO', { timeZone: selected.timezone })}</Text>)}
        {selected.principal && !a.revoked && <Button title="Revocar autorización" disabled={busy}
          onPress={() => mutate(`/v1/authorizations/${a.id}/revoke`, { student_id: selected.id })} />}
      </View>)}
    </>}
  </View>;
}
