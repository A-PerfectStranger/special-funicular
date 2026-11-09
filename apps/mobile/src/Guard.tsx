import { useEffect, useRef, useState } from 'react';
import { Button, Image, Switch, Text, TextInput, View } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';
import type { IdentityClient } from './identity';
import { isOperationId, OnlinePermission, type PickupOperation } from './pickupState';

type Resolved = { student_name: string; caregiver: { name: string; document: string }; expires_at: string; server_now: string };
const RECOVERY = 'pickup_operation';
export function Guard({ identity }: { identity: IdentityClient }) {
  const [cameraPermission, requestCamera] = useCameraPermissions();
  const [scanning, setScanning] = useState(false);
  const [resolved, setResolved] = useState<Resolved | null>(null);
  const [photo, setPhoto] = useState('');
  const [checks, setChecks] = useState({ student: false, caregiver: false, document: false });
  const [oid, setOid] = useState('');
  const [state, setState] = useState<PickupOperation | null>(null);
  const [allowed, setAllowed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [reportPending, setReportPending] = useState(false);
  const [message, setMessage] = useState('Sin permiso de entrega. Escanea y verifica presencialmente.');
  const [reason, setReason] = useState('');
  const [witnessed, setWitnessed] = useState('');
  const raw = useRef('');
  const working = useRef(false);
  const detailUntil = useRef(0);
  const lastActivity = useRef(0);
  const timedOut = useRef(false);
  const [idle, setIdle] = useState(false);
  const live = useRef(true);
  const permission = useRef(new OnlinePermission());
  const report = useRef<{ key: string; payload: object } | null>(null);
  useEffect(() => {
    live.current = true;
    lastActivity.current = performance.now();
    const permit = permission.current;
    SecureStore.getItemAsync(RECOVERY).then(id => { if (live.current && isOperationId(id)) setOid(id); }).catch(() => {});
    return () => { live.current = false; permit.invalidate(); raw.current = ''; };
  }, []);
  useEffect(() => {
    if (!oid || idle) return;
    let active = true, polling = false;
    const permit = permission.current;
    async function poll() {
      if (polling || !active || timedOut.current) return;
      if (performance.now() - lastActivity.current >= 300000) {
        timedOut.current = true; permit.invalidate(); setAllowed(false); setIdle(true);
        setResolved(null); setPhoto(''); raw.current = '';
        setMessage('Inactividad de cinco minutos. Reautentica con MFA para continuar.'); return;
      }
      polling = true;
      const sent = performance.now();
      try {
        const result = await identity.pickupRequest<PickupOperation>(`/v1/guard/operations/${oid}`);
        if (!active) return;
        permission.current.observe(result, sent, performance.now());
        setState(result); setAllowed(permission.current.allowed(performance.now()));
      } catch { if (active) { permission.current.invalidate(); setAllowed(false); setMessage('Sin certeza en línea. No entregar. Recupera la misma operación.'); } }
      finally { polling = false; }
    }
    void poll();
    const poller = setInterval(poll, 500);
    const expiry = setInterval(() => { if (active) setAllowed(permission.current.allowed(performance.now())); }, 100);
    return () => { active = false; clearInterval(poller); clearInterval(expiry); permit.invalidate(); };
  }, [identity, oid, idle]);
  useEffect(() => {
    if (!resolved || idle) return;
    let active = true, checking = false;
    function hide() {
      raw.current = ''; setResolved(null); setPhoto('');
      setMessage('Validación vencida o sin certeza en línea. No entregar.');
    }
    const expiry = setInterval(() => {
      if (performance.now() >= detailUntil.current && active) hide();
    }, 100);
    const refresh = setInterval(async () => {
      if (checking || !active) return;
      if (performance.now() - lastActivity.current >= 300000) {
        timedOut.current = true; setIdle(true); hide(); return;
      }
      checking = true;
      try {
        const sent = performance.now();
        const value = await identity.pickupRequest<Resolved>('/v1/guard/resolve-qr', { token: raw.current });
        if (active) detailUntil.current = sent + Math.max(0, Date.parse(value.expires_at) - Date.parse(value.server_now));
      } catch { if (active) hide(); }
      finally { checking = false; }
    }, 5000);
    return () => { active = false; clearInterval(expiry); clearInterval(refresh); };
  }, [identity, resolved, idle]);

  async function scan(token: string) {
    if (working.current || !/^[A-Za-z0-9_-]{43}$/.test(token)) return;
    working.current = true; setScanning(false); setBusy(true); setResolved(null); setPhoto(''); raw.current = '';
    setChecks({ student: false, caregiver: false, document: false });
    try {
      const sent = performance.now();
      const result = await identity.pickupRequest<Resolved>('/v1/guard/resolve-qr', { token });
      const image = await identity.pickupPhoto(token);
      detailUntil.current = sent + Math.max(0, Date.parse(result.expires_at) - Date.parse(result.server_now));
      if (performance.now() >= detailUntil.current) throw new Error('Expired');
      if (live.current) { raw.current = token; setResolved(result); setPhoto(image); setMessage('Comprueba las tres coincidencias. Una discrepancia rechaza.'); }
    } catch { if (live.current) setMessage('QR rechazado o servicio no disponible. No entregar.'); }
    finally { working.current = false; if (live.current) setBusy(false); }
  }
  async function confirm() {
    if (!raw.current || working.current) return;
    working.current = true; setBusy(true);
    const token = raw.current; raw.current = ''; setResolved(null); setPhoto('');
    const id = Crypto.randomUUID();
    try {
      await SecureStore.setItemAsync(RECOVERY, id); // Before the decision can be sent.
      if (!live.current) return;
      setOid(id);
      await identity.pickupRequest('/v1/guard/confirm-pickup', { token, checks }, id);
      if (live.current) setMessage('Decisión registrada. Solo la habilitación vigente permite entregar.');
    } catch { if (live.current) setMessage('Resultado sin confirmar. Consulta esta misma operación; no entregues ni inicies otra.'); }
    finally { working.current = false; if (live.current) setBusy(false); }
  }
  async function handover(delivered: boolean) {
    setBusy(true); setReportPending(true); permission.current.invalidate(); setAllowed(false);
    if (!report.current) report.current = { key: Crypto.randomUUID(), payload: { delivered, witnessed_at: witnessed || new Date().toISOString(), reason } };
    try {
      await identity.pickupRequest(`/v1/guard/operations/${oid}/report-handover`, report.current.payload, report.current.key);
      if (live.current) { report.current = null; setReportPending(false); setMessage('Hecho reportado. La protección del reporte se consulta aparte; el hecho físico se conserva.'); }
    } catch { if (live.current) setMessage('Reporte sin confirmar. Reintenta exactamente el mismo hecho; no se concede otro permiso.'); }
    finally { if (live.current) setBusy(false); }
  }
  return <View style={{ gap: 12 }} onTouchStart={() => { if (!timedOut.current) lastActivity.current = performance.now(); }}>
    <Text accessibilityRole="header">Verificación en puerta · Ensayo sintético</Text>
    <Text accessibilityLiveRegion="assertive" style={{ color: allowed && !busy && !reportPending ? '#065f46' : '#991b1b', fontWeight: 'bold' }}>{allowed && !busy && !reportPending ? 'HABILITACIÓN VIGENTE · Entregar solo a las personas verificadas' : 'NO ENTREGAR · Sin habilitación vigente'}</Text>
    <Text>{message}</Text>
    {!oid && !idle && <Button title="Escanear QR" disabled={busy} onPress={async () => {
      permission.current.invalidate(); setAllowed(false);
      if (cameraPermission?.granted || (await requestCamera()).granted) setScanning(true);
      else setMessage('Se requiere cámara. No existe validación offline.');
    }} />}
    {scanning && <><CameraView style={{ height: 260 }} barcodeScannerSettings={{ barcodeTypes: ['qr'] }} onBarcodeScanned={value => scan(value.data)} />
      <Button title="Cancelar cámara" onPress={() => setScanning(false)} /></>}
    {resolved && <>
      <Text>Estudiante: {resolved.student_name}</Text>
      <Text>Cuidador: {resolved.caregiver.name} · Documento: {resolved.caregiver.document}</Text>
      {photo && <Image source={{ uri: photo }} style={{ width: 180, height: 180 }} />}
      {(['student', 'caregiver', 'document'] as const).map((key, i) => <View key={key}>
        <Text>{['Estudiante coincide', 'Cuidador coincide con foto', 'Cédula física coincide'][i]}</Text>
        <Switch value={checks[key]} onValueChange={value => setChecks({ ...checks, [key]: value })} />
      </View>)}
      <Button title="Confirmar las tres comprobaciones" disabled={busy || !Object.values(checks).every(Boolean)} onPress={() => confirm()} />
      <Button title="Rechazar por discrepancia" disabled={busy || Object.values(checks).every(Boolean)} onPress={() => confirm()} />
    </>}
    {oid && <>
      <Text>Operación: {oid}</Text><Text>Estado: {state?.state ?? 'SIN CERTEZA'} · {state?.incident_reason}</Text>
      {state?.report_result ? <Text>Reporte: {state.report_result} · {state.report_protected ? 'Protegido' : 'Archivo pendiente; escalar al equipo técnico'}</Text> : <>
        <TextInput accessibilityLabel="Motivo del reporte" placeholder="Hecho observado / motivo, sin documentos personales" value={reason} onChangeText={setReason} maxLength={500} />
        <TextInput accessibilityLabel="Hora del hecho tardío" placeholder="Reporte tardío: instante ISO con zona (opcional)" value={witnessed} onChangeText={setWitnessed} />
        <Button title="Reportar entrega física ya realizada" disabled={busy || idle || !reason.trim()} onPress={() => handover(true)} />
        <Button title="Reportar no entrega" disabled={busy || idle || !reason.trim()} onPress={() => handover(false)} />
        <Text>Reportar un hecho tardío registra una incidencia y no autoriza otra entrega.</Text>
      </>}
      <Button title="Cerrar consulta sin conceder permiso" disabled={busy} onPress={async () => {
        await SecureStore.deleteItemAsync(RECOVERY); permission.current.invalidate(); report.current = null;
        setAllowed(false); setReportPending(false); setState(null); setOid(''); setReason(''); setWitnessed('');
      }} />
    </>}
  </View>;
}
