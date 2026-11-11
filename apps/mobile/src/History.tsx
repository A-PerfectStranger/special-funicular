import { useRef, useEffect, useState } from 'react';
import { Button, Text, View } from 'react-native';
import type { IdentityClient } from './identity';

type Record = { sequence: number; operation_id: string; student_name: string; local_date: string;
  state: string; incident_reason: string; report_result: string; report_protected: boolean;
  notification_states: { state: string; count: number }[];
  corrections: { event_id: string; outcome: string; protected: boolean }[] };
type Page = { records: Record[]; next_cursor: number | null };

export function History({ identity }: { identity: IdentityClient }) {
  const [page, setPage] = useState<Page>({ records: [], next_cursor: null });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('Consulta el historial en línea.');
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  async function load(before?: number) {
    setBusy(true); setPage({ records: [], next_cursor: null });
    try {
      const result = await identity.familyRequest<Page>(`/v1/me/pickups?limit=25${before ? `&before=${before}` : ''}`);
      if (!mounted.current) return;
      setPage(result); setMessage(result.records.length ? 'Historial consultado en línea.' : 'Sin registros.');
    } catch { if (mounted.current) setMessage('Historial no disponible. Comprueba conexión e ingreso.'); }
    finally { if (mounted.current) setBusy(false); }
  }
  return <View style={{ gap: 10 }}>
    <Text accessibilityRole="header">Historial de mis estudiantes</Text>
    <Text accessibilityLiveRegion="polite">{message}</Text>
    <Text>La decisión digital y el reporte físico son hechos distintos. Este historial no autoriza entregas.</Text>
    <Button title="Consultar historial reciente" disabled={busy} onPress={() => load()} />
    {page.records.map(record => <View key={record.operation_id} style={{ gap: 4 }}>
      <Text>{record.student_name} · {record.local_date}</Text>
      <Text>{record.report_result === 'DELIVERED' ? 'Entrega física reportada' : record.report_result === 'NOT_DELIVERED' ? 'No entrega reportada' : 'Sin reporte físico'}</Text>
      {record.report_result !== '' && <Text>{record.report_protected ? 'Reporte protegido por el archivo.' : 'Reporte pendiente de protección.'}</Text>}
      {(record.state === 'INCIDENCIA' || Boolean(record.incident_reason)) && <Text>Existe una incidencia. Consulta con la escuela.</Text>}
      {record.notification_states.map(notice => <Text key={notice.state}>Aviso: {notice.state === 'PROVIDER_RECEIPT' ? 'transferido al servicio de notificaciones del teléfono' : notice.state === 'PROVIDER_ACCEPTED' ? 'aceptado por el proveedor' : notice.state === 'SUPPRESSED' ? 'suspendido por cambio de vínculo o cuenta' : 'pendiente'}. No acredita recepción ni lectura.</Text>)}
      {record.corrections.map(correction => <Text key={correction.event_id}>Corrección técnica: {correction.outcome === 'DELIVERED' ? 'entrega reportada' : correction.outcome === 'NOT_DELIVERED' ? 'no entrega' : 'en revisión'} · {correction.protected ? 'protegida' : 'pendiente de protección'}</Text>)}
    </View>)}
    {page.next_cursor !== null && <Button title="Siguiente página del historial" disabled={busy} onPress={() => load(page.next_cursor!)} />}
  </View>;
}
