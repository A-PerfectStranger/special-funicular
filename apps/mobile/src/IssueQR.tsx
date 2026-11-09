import { useEffect, useRef, useState } from 'react';
import { Button, Text, View } from 'react-native';
import * as Crypto from 'expo-crypto';
import * as Sharing from 'expo-sharing';
import { File, Paths } from 'expo-file-system';
import QRCode from 'react-native-qrcode-svg';
import type { IdentityClient } from './identity';
import { finishQrShare } from './qrShareRuntime';

type Issued = { qr: string | null; episode_id: string; valid_from: string; expires_at: string };
export function IssueQR({ identity, authorization, schedule, timezone }: {
  identity: IdentityClient; authorization: string; schedule: { from: string; until: string }[]; timezone: string;
}) {
  const [value, setValue] = useState<Issued | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('Emite con MFA reciente, hasta 24 horas antes.');
  const qr = useRef<{ toDataURL: (callback: (data: string) => void) => void } | null>(null);
  const live = useRef(true);
  useEffect(() => { live.current = true; return () => { live.current = false; }; }, []);
  async function issue(from: string, reschedule = false) {
    setBusy(true); setValue(null);
    try {
      const result = await identity.pickupRequest<Issued>(`/v1/authorizations/${authorization}/${reschedule ? 'reschedule' : 'issue-qr'}`,
        { valid_from: from, ...(reschedule && value ? { episode_id: value.episode_id } : {}) }, Crypto.randomUUID());
      if (live.current) { setValue(result); setMessage(result.qr ? 'QR emitido. La entrega exige validación presencial y permiso en línea.' : 'Respuesta recuperada sin QR. Emite una renovación para compartirlo.'); }
    } catch { if (live.current) setMessage('No se emitió un QR utilizable. Reautentica o revisa horario y conexión. Renovar invalidará el anterior.'); }
    finally { if (live.current) setBusy(false); }
  }
  async function share() {
    setBusy(true);
    const file = new File(Paths.cache, `pickup-share-${Crypto.randomUUID()}.png`);
    let handedOff = false;
    try {
      if (!await Sharing.isAvailableAsync()) throw new Error('Sharing unavailable');
      const data = await new Promise<string>((resolve, reject) => {
        if (!qr.current) { reject(new Error('QR unavailable')); return; }
        qr.current.toDataURL(resolve);
      });
      file.write(data, { encoding: 'base64' });
      await Sharing.shareAsync(file.uri, { mimeType: 'image/png', dialogTitle: 'Compartir QR con el cuidador' });
      handedOff = true;
    } catch { if (live.current) setMessage('No fue posible compartir el QR.'); }
    finally {
      try { finishQrShare(file, handedOff); }
      catch { if (live.current) { setValue(null); setMessage('No se pudo borrar el archivo temporal. QR oculto; renueva antes de compartir de nuevo.'); } }
      if (live.current) setBusy(false);
    }
  }
  return <View style={{ gap: 8 }}>
    <Text>{message}</Text>
    {schedule.map((s, i) => <Button key={i} disabled={busy} title={`Emitir / renovar · ${new Date(s.from).toLocaleString('es-CO', { timeZone: timezone })}`}
      onPress={() => issue(s.from)} />)}
    {value?.qr && <>
      <QRCode value={value.qr} size={220} getRef={(ref: { toDataURL: (callback: (data: string) => void) => void }) => { qr.current = ref; }} />
      <Text>Vence: {new Date(value.expires_at).toLocaleString('es-CO', { timeZone: timezone })}. Renovar conserva este vencimiento.</Text>
      <Button title="Compartir imagen QR" disabled={busy} onPress={share} />
      {schedule.map((s, i) => <Button key={i} title={`Reprogramar · ${new Date(s.from).toLocaleString('es-CO', { timeZone: timezone })}`}
        disabled={busy} onPress={() => issue(s.from, true)} />)}
      <Button title="Ocultar QR" disabled={busy} onPress={() => setValue(null)} />
    </>}
  </View>;
}
