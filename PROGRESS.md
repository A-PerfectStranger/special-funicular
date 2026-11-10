# Continuidad después de E3

**E3 terminada y aceptada en staging sintético.** E0/E1/E2 conservan su aceptación
según PLAN. E4/E5, producción y uso con datos reales permanecen pendientes.
PLAN contiene los seis criterios E3 verificados y su matriz de alcance; los
runbooks contienen procedimientos. No copiar reportes, secretos, QR, fotos,
snapshots ni anclas privadas al repositorio.

## Base funcional acreditada

- SHA `0a429bc17a6c608ac24dab1306699e5764ddbb58`, PR #23–#26 y #28–#31 integradas.
- [CI 42786554831](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42786554831):
  335 Python con PostgreSQL/roles reales, 24 móvil + 2 vendor JavaScript, diez
  navegador/recuperación/diagnóstico, tipos/lint/migraciones/Expo, seguridad,
  imagen y APK aprobados.
- [CD 42788128412](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42788128412):
  publicación/preparación/migración/staging, digest/TLS/callback/nueve sondas,
  E1 browser/cloud/archive-drill/recuperación, APK staging, E2, nueve controles E3
  y WORM independiente final aprobados. Solo producción falla por NOT_CONFIGURED
  de E5; no afirmar pipeline productivo ni MVP real aceptados.
- Digest API/archivador verificado:
  `sha256:f10d670ee36c01d3f4413cf282e93864fc84f19059f5f28d903dab5b18eee4cb`.
- APK staging SHA-256:
  `ccc77c588e5d9428a638b00a93b8783991188a2746eb4061c60c8af2080c7079`.
  Origen/bundle/paquete/callback, cámara/sin micrófono y firma de desarrollo v2
  comprobados. No se publica el binario en el repositorio público.
- Cohorte consumida `ad86e8ec-928d-58e8-adf1-814badfd3e12`: E2 mínimo 1219,
  E3 mínimo 1335; lector independiente verificó 1338 eventos hasta 1338 sin SQL.
  Reportes saneados en Actions; anclas y recibos privados en su custodia externa.

## Alcance terminado y verificado

Episodio único estudiante/fecha local, QR de 256 bits/solo hash, ventanas UTC/IANA,
anticipación/renovación/reprogramación, foto mínima autenticada del guardia de
sede y tres comprobaciones. Decisión/consumo/evento/outbox atómicos con RLS y
roles restringidos; idempotencia actor/cuerpo, revocación ordenada y 50 solicitudes
concurrentes sin segunda salida. Dos guardias y sesión vencida durante locks se
ensayaron con PostgreSQL local; AWS ensayó 50 solicitudes del mismo guardia.

Reloj observado de S3, archivo oportuno <=5 s, permiso de 30 s y cierre ante
revocación/timeout/vencimiento. Demora WORM real acotada y recibo tardío nunca
rehabilitan. Hecho físico mediante evento nuevo, entrega/no entrega, replay,
respuesta perdida/UUID original y reporte tardío conservados y protegidos.
Un hecho pendiente de archivo no se borra ni se convierte en otro permiso.

La aceptación usa el conjunto CI/E1/APK/E2/E3/WORM. Los campos e2_accepted o
e3_accepted=false de reportes de protocolo son límites de ese reporte parcial;
sus passed=true y el lector externo aprobado se comprobaron conjuntamente.
Los recibos SIMULATED de pruebas locales no se presentan como evidencia AWS.

## Operación que debe conservar otra sesión

1. El cierre actual solo documenta aceptación: el código/imagen/APK acreditados
   siguen identificados por 0a429bc. No crear commits en bucle por cada SHA
   documental ni atribuir esta aceptación a releases posteriores automáticamente.
   El filtro docs-only comprueba ancestro/SHA/diff permitido antes de omitir
   builds/deploy; una revisión documental no consume otra cohorte.
2. Tres cohortes del pool nuevo se consumieron: dos intentos fallidos y la
   acreditada arriba. El selector verificará la disponibilidad restante. Nunca
   reutilizar/resetear canjes, cuentas, estudiantes, eventos, outbox, recibos ni
   WORM. Ante agotamiento reponer por operador según runbook E2, sin borrar.
3. El gateway es efímero y conserva retirada acotada. STAGING_RELEASE_ORIGIN
   acompaña ensayos/APK desde el despliegue verificado; base_url es pista. Ante
   retirada usar bootstrap stateless y sincronización exclusiva del callback
   existente del servicio/SHA/digest observado. No repetir commission_e1 ni
   editar hostnames por cada recreación. No hay acción CloudShell pendiente.
4. La federación usa un intercambio JWT GitHub por sesión STS temporal para los
   hijos, sin ampliar trust/IAM ni MFA del dominio. Las regresiones HTTP cubren
   base64 PostgreSQL con LF y el enlace de cinco parámetros de e3_report;
   conservar el recorrido completo por HTTP, además de las pruebas SQL.
5. No editar migraciones E2 0002–0005 ya aplicadas ni ejecutar refresh SQL antiguos
   de work/. Nunca pedir contraseñas, TOTP, semillas o códigos al chat.
6. La BD local original alcanzó el límite deliberado de snapshot sintético
   (5000 eventos/8 MB); se conserva sin ampliar cuota ni borrar. Suites recientes
   pasaron en BD aisladas retenidas. Consultar work/e3-apk-isolated-db.txt y los
   scripts de verificación work/ si existen; .env conserva la original. En otro
   workspace preparar entorno local según README, sin reset de staging.

## Siguiente entrega y límites

Continuar con E4 según PLAN: notificaciones desde hechos protegidos, destinatarios
derivados/reintentos/deduplicación, consultas escolares y correcciones por eventos
vinculados mediante comandos técnicos. No iniciar uso real ni avisos a familias.

E5 conserva Android físico/cámara/retorno OIDC nativo, recuperación integral con
epoch/reconciliación desde backup antiguo, carga/RTO, retención institucional,
firma/distribución privada y configuración productiva. Siete días COMPLIANCE son
solo sintéticos; APK de desarrollo y protocolo compartido no prueban dispositivo
físico ni distribución. pickup_enabled=false anterior permanece; el endpoint E3
separado anuncia synthetic_only=true. Health/capacidad nunca conceden entrega.
No hubo datos, importaciones, invitaciones ni mensajes reales.

Scratch saneado en work/, ignorado; estado/fuentes en Git, resultados por SHA en
Actions y evidencia/anclas privadas fuera del repositorio. No avanzar main durante
migraciones/archive-drill ni omitir gates en futuros cambios funcionales.
