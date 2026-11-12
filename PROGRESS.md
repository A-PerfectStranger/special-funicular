# Continuidad

[PLAN](PLAN.md) concentra criterios y aceptación; los runbooks contienen comandos.
**Producción técnica comisionada; E4/E5 y uso escolar real siguen pendientes.**
Conservar FREE y techo bruto USD 150, sin reset de cohortes ni evidencias.

## Base acreditada

Main ad4d9645e8e382059599406c34d67735e7af9964, PR #38 integrada.
[CI 43181439878](https://github.com/A-PerfectStranger/special-funicular/actions/runs/43181439878)
aprobado. [CD 43182969257](https://github.com/A-PerfectStranger/special-funicular/actions/runs/43182969257)
aprobó staging, E1, E2/E3, APK privado y WORM: 2.109 eventos/148 s. Solo producción
bloqueó por configuración faltante. La comisión posterior es de operador y no
convierte ese CD en un resultado productivo aprobado.
Digest: sha256:412e2debae5a29f3991c83aa05d6ca6d9c8de35e4ab1f8c93dfbde0cc78b11a9.

## Producción técnica observada

Cuenta 028364485203/us-east-1. Foundation y lifecycle aprobados tras recuperación
restringida: BD originalmente ausente, reuso de una clave y tres secretos,
preflight FREE/gasto/crédito/custodia aprobado y plan privado almacenado en SSM.
**No repetir recover-foundation ni asumir ausencia de BD.**

Comisión de ad4d964 confirmada por el operador: bootstrap y migración aislados
exitCode 0; mismo digest, ingreso solo desde ALB, VPC dedicada y probes TLS
aprobados. El workspace comprobó readiness 200. Configuración pública observada
incorporada a infra/environments/production.json, con negocio deshabilitado.
Origen: https://re-c110c7b9a2de4036966d49e60c4fd66c.ecs.us-east-1.on.aws.
Ventana reportada hasta 2026-11-12 19:57:34 UTC (14:57:34 America/Bogota).
La programación no acredita retirada efectiva ni disponibilidad posterior.

Reportes y planes en el CloudShell del operador, checkout aprobado
$HOME/retiro-operador-55263bd sobre ad4d964: work/production-foundation.json,
production-commission.json, production-migration.json y production-configuration.json.
Solo la última propuesta pública se incorpora al repositorio. Sin identidad AWS
de operador vinculada al workspace, las operaciones privadas se ejecutan allí.
Plan financiero privado: work/production-cost-plan.json o
$HOME/retiro-operador-3bb3056/work/production-cost-plan.json. Cada mutación revalida
vigencia, FREE y coste bruto/reservas. Backup aprobado un día; evidencia 90 días,
custodia mínima 97 días; no reducir reservas ni inventar revisiones de precios.

## APK y aceptación conjunta

APK privado de ad4d964 SHA-256:
6d9521830b858c976f306eaa3921445987da882b1dc3beb3d494144f87436e7a.
Descarga bloqueada LIVE_GATEWAY_REQUIRED: staging fuera de su ventana de tres
horas, sin pasarela activa. La siguiente ejecución debe verificar/recrear origen,
sincronizar únicamente el callback existente si cambia y construir APK del origen
observado. No omitir controles ni usar el binario como vigente con origen retirado.

Ensayo físico confirmado por el responsable sobre el APK anterior de 55263bd:
Redmi 10C/Android 13, instalación al renombrar .apk_ a .apk, conexión, MFA/retorno
nativo, PADRE e1-a-p1, A1/A2 principal, America/Bogota, bloqueo/retorno, datos
ocultos sin red y recuperación online. Permiso denegado correcto; con permiso
concedido falla registro de avisos. Falta el nuevo APK y código N01–N06 para
resolver la causa; registro y recepción no acreditados. Credenciales/TOTP solo
en consola/vault privados. Cámara, puerta, actualización y demás E5 pendientes.

## Continuación

Rama feat/production-configuration desde main ad4d964: configuración observada,
prueba de destino incompleto explícito y documentos consolidados. La estructura
valida sin habilitar negocio; no atribuir aceptación al nuevo SHA automáticamente.
Validación local: make check aprobado (558 Python/PostgreSQL con roles reales,
42 JavaScript, lint/tipos/migraciones/Django/Expo/plantillas); make security sin
hallazgos. CI/imagen/APK y CD del nuevo candidato pendientes de su ejecución.

1. Revisar CI del PR; integrar solo con checks aprobados. Luego main CI/CD con
   staging/E1/E2/E3 antes de producción. Entregar enlaces sin esperar horas.
2. Si staging recreado informa origin_sync_required, ejecutar sync_staging_origin
   desde main limpio aprobado, sin otra operación activa, y repetir los gates.
   No sustituir base_url por cada hostname ni recomisionar identidad/evidencia.
3. Verificar producción prepare/migrate/deploy por su SHA/digest y OIDC. Si la
   ventana u origen vencieron, inspeccionar/recomisionar servicio según runbook;
   no recuperar foundation otra vez. Verificar retirada real API/ALB/RDS y
   rollback real por separado; siguen pendientes.
4. Descargar APK privado vigente, actualizar con la misma firma sin desinstalar,
   repetir registro de avisos y resolver su código antes de recepción real.
5. Cerrar E4: Expo/FCM/allowlist/alarma y gate integrado con WORM independiente.
   E5 conserva recuperación integral/epoch, carga/RTO, fallos, retención efectiva,
   firma/distribución productivas, ensayo presencial y activación escolar aprobada.

Staging e4_enabled=false. Ambos destinos pickup_enabled=false/synthetic_only=true;
producción E1–E4 apagados. Resultados por commit en Actions; planes/logs/evidencia
privados fuera de Git. El despliegue técnico no acredita uso con estudiantes reales.
