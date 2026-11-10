# Continuidad E3

PLAN concentra criterios y backlog; Actions conserva resultados por SHA. Anclas,
snapshots y recibos privados quedan fuera del repositorio. No copiar secretos,
QR, fotos ni reportes privados a Git. E0/E1/E2 están aceptadas según PLAN.
**E3 NO está aceptada todavía.**

## Base y resultados verificados

Base integrada por PR #23–#26 y #28–#30:
`bd8eca2b74356964e23fb41824830a80df72c2f5`.
[CI 42776069649](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42776069649)
aprobó 333 Python con PostgreSQL/roles reales, 24 móvil + 2 vendor JavaScript,
diez navegador/recuperación/diagnóstico, tipos/lint/migraciones/Expo, seguridad,
imagen y APK con cámara, sin micrófono y firma de desarrollo v2.

[CD 42777229650](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42777229650)
aprobó publicación/preparación/migración/staging, SHA/digest/TLS/callback/nueve
sondas, E1 browser/cloud/archive-drill/recuperación, APK staging con origen/bundle,
paquete/callback/permisos/firma y E2 completo con su ancla final (mínimo 1081).
Digest runtime: `sha256:e1b59a3a8eb18b38cf3c134c284cf508ad7ce2eaab8cb198aa1b8313c72bc840`.
APK SHA-256: `2b02d4d79c65abfabf9807e49390193457a283aea2ee3db7489c4e948c036df6`.
El lector independiente E1 verificó 1030 eventos sin SQL; archive-drill verificó
hasta 1039, incluido el intento tardío 1034 que siguió denegado.

E3 aprobó before_start_no_data_or_photo y same_site_guard_only_authenticated_minimal_photo:
la corrección LF de PostgreSQL quedó comprobada realmente en foto/roles/sede.
Falló después en lost_response_success, HTTP 503, mínimo 1112. WORM final fue
omitido; passed=false/e3_accepted=false. No acreditar E3 ni atribuir estos
resultados a un candidato posterior. Cohorte consumida:
`f86ddf69-cef1-54d9-928b-7e3dae1caaa7`; también está consumida la anterior
`6d17c1e8-29e2-545a-954c-8b30b6e3fa0e`. No reutilizar ninguna.

## Defecto actual reproducido y corrección

El adaptador HTTP de report-handover llamaba e3_report con seis placeholders y
cinco parámetros, aunque la función SQL recibe cinco. PostgreSQL/HTTP real
reprodujo 503 tanto para entrega como para no entrega. Las pruebas SQL existentes
pasaban pero faltaba el recorrido completo por HTTP; no cambiar ni editar las
migraciones aplicadas para corregir este enlace del transporte.

Rama fix/e3-handover-http-binding corrige a cinco placeholders. Dos regresiones
pasaron después del cambio: confirmar, descartar cuerpo, recuperar por UUID
original, habilitar con recibo SIMULATED, reportar ambos resultados, replay exacto,
conflicto por cambio de cuerpo/actor, padre denegado, no-store, único hecho nuevo
y protección posterior. SIMULATED no acredita AWS. Se conservan transacciones,
idempotencia, RLS/roles, evidencia, plazos y formatos API. El driver distingue
inyección de respuesta perdida, recuperación, reporte físico y token consumido.
Verificación local aprobada: 335 Python con PostgreSQL real, 26 JavaScript,
tipos/lint, migraciones/Django y dependencias Expo. Las dos regresiones fallaron
antes y pasaron después del cambio. PR/CI y aceptación AWS siguen pendientes.

## Próximos pasos obligatorios

1. Completar suite/PR/checks e integrar con CI aprobado y main actualizado. El CD
   anterior terminó; no queda migración ni archive-drill activo. Mantener límites
   MFA/sesión, SQL y archivo; no debilitar pruebas para presentar éxito.
2. Exigir main CI y CD del nuevo SHA/digest: E1/APK, E2, nueve controles E3 y
   lector independiente hasta máximo minimum_sequence. e2_accepted/e3_accepted=false
   delimitan el alcance parcial; exigir passed=true en protocolos, WORM y CI.
3. Del pool de cuatro cohortes nuevas confirmado por operador se consumieron dos;
   el selector debe verificar las restantes. No queda acción CloudShell pendiente.
   Agotarse bloquea y se repone según runbook E2, sin reset de identidades/canjes.
4. Solo tras todos los gates cerrar las seis filas E3 de PLAN. PR #27 sigue
   borrador; su rama local 48c7511 ya integró bd8eca2 y debe reconciliar esta
   corrección y reescribirse con SHA/digest/runs/trial/secuencias/APK aceptados.
   Exigir diff exclusivamente documental permitido, calidad y filtro docs-only
   para no redeplegar ni consumir una cohorte por el cierre documental.

## Operación y límites que conservar

- Gateway recuperado y callback existente sincronizado por operador. Ensayos/APK
  usan STAGING_RELEASE_ORIGIN verificado; base_url es pista. Ante retirada usar
  bootstrap stateless/sincronización estrecha del runbook, sin commission_e1.
- JWT GitHub se canjea una vez por sesión STS temporal para los hijos; se elimina
  JWT/identidades heredadas, sin cambiar trust/IAM. El ancla E2 ya aprobó en AWS.
- Nunca borrar/reiniciar cuentas, canjes, estudiantes, eventos, outbox, recibos ni
  WORM para repetir. No editar migraciones E2 0002–0005 ni ejecutar refresh SQL
  antiguos de work/. No pedir contraseñas/TOTP/semillas/códigos.
- La BD local original alcanzó el límite deliberado de snapshot sintético
  (5000 eventos/8 MB); se conserva sin ampliar cuotas ni borrar. Suites en BD
  aisladas retenidas: consultar work/e3-apk-isolated-db.txt y scripts work/.
  .env conserva la original. No publicar credenciales ni purgar datos de ensayo.
- pickup_enabled=false anterior se mantiene; el endpoint E3 separado anuncia
  synthetic_only=true. Capacidad/health nunca conceden entrega.
- E4: avisos/consultas/correcciones. E5: Android físico/cámara/retorno OIDC,
  recuperación integral/epoch/carga/RTO, retención institucional, firma,
  distribución y producción NOT_CONFIGURED. No hubo datos/mensajes reales.
  APK de desarrollo no acredita teléfono físico ni se publica aquí como binario.
- No crear commits en bucle para registrar cada SHA documental. Distinguir base
  funcional aceptada de revisión documental; consultar releases por SHA en Actions.
  Scratch saneado en work/, ignorado; estado/fuentes aquí, evidencia en su custodia.
