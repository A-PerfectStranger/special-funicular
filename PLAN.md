# PLAN — Estado y aceptación

Proyecto de retiro seguro de estudiantes. El [contrato](Requerimientos_retiro_seguro_estudiantes.md)
define comportamiento y seguridad; [AGENTS](AGENTS.md) fija las reglas de trabajo;
[README](README.md) contiene comandos y los runbooks contienen procedimientos.
Este documento concentra el estado y los criterios pendientes. Los resultados de
cada candidato se consultan por SHA en Actions; no se atribuye una aceptación
anterior a una imagen, APK o despliegue posterior.

## Estado vigente

| Entrega | Estado | Alcance |
| --- | --- | --- |
| E0 | Aceptada | Monorepo, CI, imagen/APK de desarrollo, AWS staging privado, OIDC de Actions, presupuesto y probes. |
| E1 | Aceptada con sintéticos | Cuatro roles, OIDC/MFA real, sesiones/revocación, RLS, eventos/outbox, WORM/KMS y verificador independiente. |
| E2 | Aceptada con sintéticos | Bulk privado, activación/contacto verificado, principal único, cuidadores/fotos, autorizaciones y revocación. Una familia pertenece a una sola escuela. |
| E3 | Aceptada con sintéticos | QR diferido, decisión única, archivo antes del permiso de 30 s, reporte físico, incidencias e idempotencia. |
| E4 | Candidato implementado y verificado localmente; aceptación AWS pendiente | Notificador Expo Push, historial familiar, consulta escolar y correcciones técnicas. La bandera de staging sigue apagada. |
| E5 | Pendiente | Comisión técnica productiva sin ejecutar. Android con instalación/MFA/consulta y bloqueo parcial comprobados; registro de avisos fallido. Recuperación/carga, resto de pruebas físicas, firma/distribución productivas y activación escolar pendientes. |

No hay producción comisionada ni uso real autorizado. `pickup_enabled=false` y
`synthetic_only=true` siguen en la configuración de ambos destinos. E3 se descubre
por su endpoint separado, exclusivamente sintético. Health nunca concede entrega.

### Evidencia que delimita E0–E3

| Entrega | Evidencia aceptada |
| --- | --- |
| E0 | [Preflight 42430538070](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42430538070) y [CD 42433511451](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42433511451). |
| E1 | [Ensayo 42501830048](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42501830048) y [recuperación E1 42507955250](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42507955250). AT02/04 y alcance E1 de AT05/06; base `0ca43742fd1a5ad77311a64ee522ef932682922d`. |
| E2 | Base `1a16b85fcc7f8ac25d268c308c1ccf9451c667b1`, [CI 42543919847](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42543919847) y [CD 42544785382](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42544785382). |
| E3 | Base `0a429bc17a6c608ac24dab1306699e5764ddbb58`, [CI 42786554831](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42786554831) y [CD 42788128412](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42788128412). |

Los CD citados no acreditan producción: ese destino terminó con
`BLOCKED/NOT_CONFIGURED`. E1/E2/E3 usan WORM COMPLIANCE de siete días y APK con
firma de desarrollo. E3 verificó 50 solicitudes concurrentes del mismo guardia en
AWS; dos guardias y vencimiento de sesión bajo locks se comprobaron con PostgreSQL
local. El APK inspeccionado acredita bundle, paquete, callback, permisos y firma,
pero no instalación, cámara ni retorno OIDC en un teléfono.

## Arquitectura y decisiones fijadas

- Monorepo Django modular para API, templates/BFF y workers; Expo SDK 56 para
  padre/guardia. No frontend web separado ni transacción distribuida de retiro.
- PostgreSQL real, RLS ENABLE/FORCE, cuentas distintas para negocio, lectores,
  importación, notificación, archivo y migración. Runtime sin propiedad, DDL,
  SUPERUSER, BYPASSRLS ni escritura libre de evidencias.
- Hechos canónicos append-only, outbox transaccional, archivo WORM con versión y
  hash exactos, manifiestos firmados y verificación fuera de SQL. Correcciones
  añaden hechos vinculados; no se borra historia para repetir un ensayo.
- Escuela aprueba datos y políticas; equipo técnico ejecuta operaciones privadas
  auditadas. Los administradores de aplicación no reciben CRUD ni autoasignación.
- AWS `us-east-1`, cuenta `028364485203`, techo total de USD 150 brutos. Antes de
  aprovisionar se comprueban gasto, saldo, vigencia y costes retenidos. Presupuesto
  y lifecycle: [AWS](infra/aws/README.md).
- Producción usará URL/certificado administrados de AWS; no hay dominio propio.
  Se prepara activación real después de completar todos los gates.
- Avisos por Expo Push; ensayos solo a dispositivos del equipo. Proyecto Expo
  `43s1r/retiro-seguro`, ID `8d55d0cb-2d9f-4a73-bac3-6ad7cab1f04f`;
  Firebase `retiro-seguro-2ab03`. Las claves se custodian en Expo/Secrets Manager.

## E4 — Criterios y cierre pendiente

RF03/11/12/13/17/18/19; CA-F03/11/12/13/17/18/19;
CA-S02/11/12/14/18/21/22/23; AT02/05/07; AB02/10/12/14/16/23.

| Criterio | Implementación y comprobación local | Falta para aceptación |
| --- | --- | --- |
| Aviso desde hecho físico | Trigger transaccional: solo `DELIVERED`; destinatarios derivados de vínculos/cuentas activos. No aviso por escaneo, decisión pendiente o no entrega. Envío espera recibo del reporte. | Hecho protegido y aviso real al equipo en staging, verificados por SHA. |
| Idempotencia y recuperación | Un aviso por evento/padre, leases concurrentes, reintentos 30 s/2 min/5 min/15 min, agotamiento pendiente de revisión, comando técnico auditado para reintentar el mismo aviso. | Fallo/recuperación del proveedor real, alarma y medición p95 de envío <=30 s. |
| Confirmación del proveedor | Tickets y recibos Expo correlacionados por HTTPS autenticado; callback público inexistente. Mensaje genérico; nunca se afirma recibido/leído. | Enhanced push security, credencial FCM v1, allowlist y recibo reales; prueba en Android. |
| Lecturas mínimas | API paginada de padre y lector SQL escolar separado; filtros por estudiante/fecha local; templates escapados; admin. sistema conserva exclusivamente accesos escolares. | Matriz completa en IdP/AWS y portal desplegado. |
| Correcciones | Comando importer privado, aprobación/motivo/operador, evento vinculado, replay/conflicto; conserva bytes, estado original y token consumido. | Corrección y ancla WORM independientes del candidato en staging. |
| Integración | Migraciones aditivas, contratos/tipos, worker aislado, definición de tarea y plantilla IAM/alarma. | Comisionar recursos, habilitar bandera revisada y completar gate integrado E4 antes de declararla aceptada. |

Regresión local vigente: 558 pruebas Python con PostgreSQL y roles reales,
42 JavaScript, tipos/lint, checks Django/Expo, migraciones y auditorías de
paquetes/secretos aprobados. Los recibos y respuestas de proveedor locales son **SIMULATED**; no
acreditan AWS, Expo/FCM ni dispositivo físico. CI, builds de imagen/APK y CD del
nuevo SHA requieren sus propios resultados.

`retiro-staging-operations` está comisionado: bucket interno, rol OIDC
MobilePublisher, clave KMS conservada y suscripción SNS confirmada.
Base integrada `55263bd8a31e4954ff1acba5354e7f306894b994`:
[CI 43165684917](https://github.com/A-PerfectStranger/special-funicular/actions/runs/43165684917)
aprobado y [CD 43167057252](https://github.com/A-PerfectStranger/special-funicular/actions/runs/43167057252)
con publicación, migración, staging, E1/browser/cloud/archive-drill, E2/E3 y APK
privado aprobados. Solo producción terminó BLOCKED por falta de configuración.
El lector independiente verificó 1.896 eventos en 61 s; conserva firmas KMS,
versiones/retención/hash, orden de cadena y deadline de 480 s con cuatro lectores.
Digest: `sha256:d0efa19f27cce5d6c047b055b491077a86aca8c5f0d03f3f907f03308729053d`.
APK staging: `18f8b34543b770b09c8f4444d328a6c54366d02277fe52e61c4d89ebd634249f`,
almacenado por SHA/checksum/origen, sin sobrescritura. La validez de la pasarela
se revalida al descargar; estos resultados no se trasladan a otro candidato.
Descarga privada del APK confirmada por el operador: versión, origen activo y
checksum coincidentes. En Redmi 10C/Android 13 el responsable confirmó instalación
tras corregir la extensión `.apk_` a `.apk`, conexión técnica, MFA y retorno nativo,
rol PADRE, estudiantes sintéticos A1/A2 como principal y zona America/Bogota.
Bloqueo/retorno descarta detalle y revalida; sin red oculta familia y exige conexión;
con red recupera sesión/familia. La denegación del permiso de avisos se comprobó.
Con permiso concedido, el registro falla con el mensaje genérico del APK actual:
causa sin identificar. El candidato añade diagnóstico seguro por etapa y exige
confirmación explícita del servidor; falta su build/CD y repetir el paso físico.
Estas observaciones no acreditan cámara, autorizaciones/retiro, recepción push,
actualización, firma productiva ni los demás escenarios Android E5. Siguen
pendientes alarma real, allowlist, comisión/gate del notificador y recibos Expo/FCM.

Orden: cerrar persistencia/permisos → transporte/worker/vistas → regresiones y
contrato → comisión y ensayo AWS/Expo → verificador externo. Procedimientos y
configuración pendiente: [E4](docs/runbooks/e4.md).

## E5 — Secuencia de aceptación conjunta

La primera activación exige AT01–AT08, CA-F01–F19 y CA-S01–S24, con cero defectos
críticos de permisos, retiro o evidencia. Cada resultado debe vincular SHA,
entorno, esperado y observado. No basta un build, una simulación ni un conjunto
de unitarias. Procedimiento: [E5](docs/runbooks/e5.md).

- [ ] Cerrar E4 en staging y ejecutar la regresión completa del candidato.
- [ ] Medir resolución QR p95 <=2 s: 20 guardias, 5 resoluciones/s, 15 minutos;
  archivo <=5 s, aviso p95 <=30 s y backlog/reintentos.
- [ ] Inyectar caídas DB/IdP/WORM/push/reloj y verificar cierre seguro, evidencia y
  recuperación sin duplicar salidas ni habilitar por caché.
- [ ] Restaurar backup anterior a una salida: epoch nuevo, invalidación de tokens
  anteriores, conciliación WORM/manifiestos/eventos/referencias y bloqueo ante
  lag/huecos. RTO objetivo <=30 min medido; la recuperación E1 no es esta prueba.
- [ ] Verificar IAM/SQL/KMS efectivos, retención, claves, backups/PITR, alertas,
  reconciliación y conservación de evidencia con sintéticos.
- [ ] Probar juntos APK en Android: instalación, firma, actualización, cámara,
  permisos, MFA/retorno OIDC, segundo plano/bloqueo, red intermitente y respuesta
  perdida con el ID original. Publicar APK no prueba instalación.
- [ ] Ejecutar ensayo presencial con personal y datos sintéticos, diferenciando
  decisión digital, permiso vigente, entrega/no entrega e incidencia.
- [ ] Comisionar producción aislada: configuración completa, presupuesto real,
  OIDC, BD, WORM/KMS, Expo, firma estable y distribución privada autenticada.
- [ ] Publicar el digest aprobado por el pipeline automático, con probes seguros.
- [ ] Validar lote, contactos, vínculos, principal, sede/zona IANA, ventanas,
  restricciones y canal urgente; activar la escuela mediante operación privada
  aprobada solo después de cumplir todos los criterios.

El responsable delegó la elección inicial de retención. La política seleccionada
vive en [retention.json](infra/environments/retention.json); **no está aplicada ni
acredita RFS17**. Faltan enforcement, ciclo automático permitido, denegaciones y
restauración reales, además de comprobar coste y vigencia de la custodia. El
responsable autorizó backup de un día para conservar el plan FREE y USD 150;
evidencias 90 días y custodia mínima 97 días se mantienen. No se
modifica la retención sintética de staging ni se cargan datos reales para ensayarla.

### Primera ventana técnica productiva

El responsable confirmó operador CloudShell y el techo total de USD 150.
Implementación integrada en main: infraestructura aislada,
preflight de gasto/crédito/custodia, roles SQL seguros, migración aislada,
promoción del mismo digest, probes y rollback de código compatible verificado.
Ventana de tres horas con retirada de API y guarda RDS; negocio deshabilitado.
Procedimiento: [producción](docs/runbooks/production.md). Foundation está en
`ROLLBACK_COMPLETE`: AWS rechazó backup de siete días bajo el plan gratuito.
Lifecycle no existe. La inspección de solo lectura del operador confirmó ausencia
de BD en RDS; CloudFormation registra `Database`, la clave y tres secretos como
`DELETE_SKIPPED`, y los demás recursos como `DELETE_COMPLETE`. La inspección
completa bloqueó porque el inspector no contemplaba ese estado de una BD ausente.
La corrección exige ausencia independiente e identificador/políticas exactos;
falta aprobarla por CI y repetir la inspección completa antes de recuperar.
El responsable descartó PAID y autorizó retención de backup de un día.
La recuperación preserva claves/secretos y exige FREE activo durante toda la
custodia, revisión financiera vigente y main aprobado. No cambia de plan.
El CD de `55263bd` aprobó E2/E3 con el pool repuesto. Las cohortes usadas se
conservan; una release posterior necesita sus propios gates y cohorte disponible.

| Criterio de esta etapa | Verificación requerida |
| --- | --- |
| Presupuesto | FREE activo durante toda la custodia, precios revisados, crédito suficiente, gasto bruto más reservas <= USD 150. Sin datos/plan válido, BLOCKED antes de aprovisionar. |
| Aislamiento | VPC/BD/KMS/secretos/roles productivos separados; TLS SQL obligatorio, RLS y runtime sin DDL/escritor. Plantillas y PostgreSQL local no acreditan IAM/AWS efectivos. |
| Publicación | Main aprobado, mismo SHA/digest que staging, migración serializada y verificación de imagen/red/TLS/salud; reversión de código verificada ante fallo. |
| Operación acotada | Retirada real de API/ALB y parada de RDS, sin borrar datos, claves, backups ni evidencia. |
| Alcance | Identidad/familia/retiros/avisos apagados. CI/CD, comisión/configuración AWS y pruebas conjuntas pendientes; la etapa no acredita E4/E5 ni activación escolar. |

## Integración, artefactos y promoción

1. Ramas cortas y PR a `main`. Checks requeridos: lint/tipos, unitarias, contratos,
   migraciones, PostgreSQL/RLS, negativas, secretos/dependencias e imagen/APK.
2. Main repite checks del SHA integrado. Imagen inmutable construida una vez y
   promovida por el mismo digest; API/templates/workers comparten revisión.
3. Staging: migración aislada, SHA/digest real, TLS/red/callback, E1, E2, E3 y gates
   adicionales de funciones habilitadas; verificación WORM hasta la última secuencia.
4. Producción automática solo tras todos los gates y comisión E5; no aprobación
   manual rutinaria de promoción. Destino incompleto informa BLOCKED, no éxito.
5. Serializar despliegues/migraciones por entorno y descartar candidatos obsoletos
   bajo exclusión mutua. No cancelar migraciones por un commit nuevo.
6. Expand/contract y API compatible con APK instalados. Rollback solo de código
   compatible; nunca borrar evidencia, restaurar BD o bajar esquema para revertir
   una release. Recuperación de desastre es una operación diferente.

Actions usa permisos mínimos, acciones por SHA y OIDC efímero con sujeto/audiencia
exactos; no código de forks con secretos. Los cambios exclusivamente documentales
pueden omitir builds/deploy solo con ancestro y diff permitidos verificados.

Por indicación del responsable, CI/CD se inicia al final del trabajo local y se
entregan enlaces/estado sin esperar ejecuciones largas. La siguiente sesión
verifica sus resultados antes de integrar/promover y continúa la aceptación
conjunta. No se omiten gates para evitar la espera.

## Operación y continuidad

- Fuentes por destino: `infra/environments/`. No inferir servicio activo a partir
  de la aceptación de una fase ni de una URL temporal.
- El gateway de staging es efímero. Usar origen observado del SHA/digest, con
  callback exacto; sincronizar únicamente el callback existente cuando proceda.
- Cohortes sintéticas de un solo uso. El selector comprueba disponibilidad; si se
  agotan se reponen por operador. Nunca resetear usuarios, canjes, eventos o WORM.
- Métricas y logs sin QR, credenciales, fotos, documentos completos ni payloads
  remotos. Alertas de divergencia, archivo fuera de plazo, reintentos agotados,
  reloj degradado y pendientes. Suspender el flujo afectado y añadir eventos.
- Alta/baja, importación, cambio de principal, revocación, correcciones, rollback
  y recuperación se operan mediante los runbooks; no mediante CRUD administrativo.
- Contexto mínimo de reanudación: [PROGRESS](PROGRESS.md). Evidencia privada y anclas
  confiables permanecen fuera del repositorio público.
