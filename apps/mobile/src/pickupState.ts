// Permission is online-only and measured with a monotonic clock. Device wall time
// never extends a server permission. Persist only the operation UUID for recovery.
export type PickupOperation = {
  operation_id: string; state: 'PENDIENTE_ARCHIVO' | 'HABILITADA' | 'INCIDENCIA' | 'ENTREGA_REPORTADA';
  server_now: string; permission_expires_at: string | null; may_handover: boolean;
  incident_reason: string; report_result: string; report_protected: boolean;
};
export class OnlinePermission {
  private until = 0;
  private freshUntil = 0;
  invalidate() { this.until = 0; this.freshUntil = 0; }
  observe(value: PickupOperation, sent: number, received: number) {
    this.invalidate();
    if (value.state !== 'HABILITADA' || value.may_handover !== true || !value.permission_expires_at) return;
    const lifetime = Date.parse(value.permission_expires_at) - Date.parse(value.server_now);
    const roundTrip = received - sent;
    if (!Number.isFinite(lifetime) || lifetime <= 0 || lifetime > 30000 || roundTrip < 0 || roundTrip >= 1000) return;
    this.until = received + Math.max(0, lifetime - roundTrip);
    this.freshUntil = received + 1000;
  }
  allowed(now: number) { return now < this.until && now < this.freshUntil; }
}
export const isOperationId = (value: unknown): value is string =>
  typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value);
