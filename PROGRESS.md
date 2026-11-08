# Estado de ejecución — E1 en implementación

## Estado actual para continuar

**E1 sigue sin aceptación integral.** Main remoto verificado en
`5ac4f0296165361cf530f0f30ad350bbc542d6da` (PR #10). CI main 42452708111
aprobada; CD 42453335189 publish/prepare/migrate/staging aprobados y producción
bloqueada hasta E5. Evidence 0013 aplicada en RDS. Retiros y producción apagados.

- El operador confirmó las 13 identidades sintéticas/TOTP y el roster desde
  26d7d47. Contraseñas y semillas permanecen exclusivamente en Secrets Manager.
- Segundo ensayo real [42454301027](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42454301027):
  API/worker por digest verificado, acceso escolar protegido, Cognito/WORM/KMS y
  APK aprobados; PADRE volvió a fallar al capturar el retorno nativo, GUARDIA no
  se ejecutó y archive-drill quedó omitido. Reportes conservados sin alterar en
  docs/evidence/*-5ac4f02.json. High-water externo 37; no acredita recuperación SQL.
- Continuación `feat/e1-identity-checks`: revocación administrativa privada y
  restauración de dos cuentas fijas, prueba móvil con credenciales no vencidas,
  migración evidence 0014 con auditoría estrecha. La restauración no reactiva
  sesiones antiguas ni modifica identidad/rol/vínculos. Pendiente ensayo AWS.
- Exportador privado comprueba el roster original completo y los límites reales
  SQL/IAM/KMS antes de generar las copias. Opción de operador prepara recuperación
  MFA de una contraseña sintética y medición nativa Cognito exponencial. No
  ejecutados aún; no pedir ni publicar secretos.
- Capturador de prueba ampliado a navegación nativa solicitada por JavaScript:
  regresión reproducida fallida antes de corregir; cuatro pruebas Chromium reales
  aprobadas. Esto no prueba todavía la causa del fallo Cognito ni su solución real.
- Último make check: 154 Python/nueve JS aprobados; tipos, lint, migraciones y
  configuración Expo aprobados. La aceptación real y CI del nuevo candidato se
  registrarán por separado, sin heredar resultados de otro SHA.
- Sondeo real backend 5/15 iniciado en workflow 42456781366 sobre 5ac4f02/digest
  ef7b320f; sin AWS/secretos y sin alterar relojes. Resultado aún pendiente.
  No desplegar otro candidato durante la medición de 905 segundos.
- Faltan móvil real completo, baja/restauración online, archivo ausente/tardío,
  copia SQL divergente y recuperación/lockout Cognito. E1 permanece sin marcar.
- Decisión autorizada RFS07: Cognito exponencial; backend 5/15. COMPLIANCE siete
  días solo sintéticos. No hay credenciales AWS de operador en esta sesión.

## Historial del checkpoint inicial (7 de noviembre de 2026, America/Bogota)

**E1 no está terminada ni aceptada en AWS.** Base remota
`bbe48f4`, sincronizada por fast-forward tras fetch; rama `feat/e1-identity-evidence`.
AGENTS, PLAN, PROGRESS y requisitos leídos antes del código; criterios previos
registrados en `docs/e1-acceptance.md`. El usuario eligió Cognito de ensayo y
siete días COMPLIANCE exclusivamente para evidencia sintética.

Implementación local: identidad OIDC Code/PKCE y sesiones, cuatro roles locales,
escuelas/sedes/estudiantes/padres/vínculos, restricciones y RLS, funciones de
escritura restringidas, eventos/outbox y archivador/recibos/manifiestos externos,
verificador sin BD, BFF/consulta mínima y cliente móvil con SecureStore.
Contrato OpenAPI, README y runbook E1 actualizados. E1 desactivada por defecto;
retiros, invitaciones, operaciones E2–E5 y producción sin habilitar.

### Evidencia local del checkpoint

- `make db check`: **115 pruebas Python y siete JS**, PostgreSQL real con roles
  separados, Ruff/formato, mypy/TypeScript/ESLint, cfn-lint, migraciones, Django
  y compatibilidad Expo aprobados. No atribuirlo al SHA de E0 ni a AWS.
- `make security`: pip-audit/npm audit sin vulnerabilidades; gitleaks en historial
  y árbol sin hallazgos. Excepción estrecha para la expresión SQL literal
  `stamp+interval`, detectada como falso secreto; no se omiten archivos fuente.
- Bundle Android/Hermes exportado con los módulos nuevos. APK e imagen nuevos
  y checks CI por commit: pendientes al escribir este checkpoint.
- Chromium/Playwright con datos/sesión sintéticos: formulario CSRF, consulta mínima,
  paginación/controles de fecha y logout con reentrada denegada aprobados. Se corrigió
  `Origin:null` causado por no-referrer en formularios: BFF usa same-origin;
  no se envían referencias al IdP. Esto no acredita login Cognito real ni TLS AWS.
- SQL: aislamiento entre familias/escuelas, principal único/obligatorio, revocación,
  rotación y carrera de diez refresh, idle/expiración, escritura/mutación/SET ROLE
  denegados, rollback de evento/outbox/sesión y head sin huecos, lease expirado y
  recibo único. La devolución PL/pgSQL del archivador requirió cast explícito
  varchar→text; corregido con migración hacia delante.
- Tres accesos/tres eventos y no reapertura con recibo tardío aprobados con recibos
  simulados. RSA real en pruebas; IdP, S3 y KMS simulados no aceptan servicios reales.

### Pendiente y orden de continuación

1. PR #8 abierto como borrador. CI de `2b1355e` aprobada (quality, imagen/smoke,
   APK y required): https://github.com/A-PerfectStranger/special-funicular/actions/runs/42439770486.
   La repetición de PR y los commits posteriores se verifican por separado.
   Histórico: la integración preparatoria fue autorizada expresamente y se realizó
   después, con E1 desactivada (ver sección siguiente).
2. Comisionar Cognito/WORM/KMS/roles SQL usando el runbook E1 y operador AWS acreditado.
   No hay credenciales de operador en esta sesión; CI/main no es ese login.
   No reutilizar el código OAuth antiguo ni pedir claves permanentes.
3. Completar integración E1 del destino en CD: config/roles API, credencial del
   lector, arranque/retirada acotada del archivador y aceptación real de E1.
   El CD existente verifica E0, no acepta E1 por pasar sus probes. Las migraciones
   ahora bloquean antes de DDL si faltan roles E1 seguros, con diagnóstico explícito.
4. Provisionar cuentas sintéticas individuales/enrolar MFA; probar flujos completos,
   revocación, recuperación sin nuevos vínculos, WORM/KMS/retención/denegaciones,
   versiones/manifiestos y portal sin recibo contra el candidato por SHA/digest.
5. Completar cada fila de la matriz de aceptación. No marcar E1 completa por mocks,
   por un build, por recursos ACTIVE ni por la comisión de roles.

`docs/runbooks/e1.md` describe comandos reales y límites. El entorno sufrió una
interrupción y se recuperó con árbol/logs intactos. El parche interrumpido de fechas
se reaplicó y verificó. Se guardó una nota mínima pública, autorizada por el usuario,
en `docs/e1-session-recovery`; es documentación histórica, no la implementación.

### Comisión: primer intento y corrección

El usuario ejecutó el candidato `2b1355e` en CloudShell. El primer intento se
detuvo antes de CloudFormation: `Exact operator IAM principal required`.
Diagnóstico de lectura posterior: `billing=PASS`; stack E1 no acreditado
(`ValidationError` al describirlo). No atribuir recursos creados a ese intento.
Se elimina la dependencia innecesaria del ARN humano para el verificador: usará
OIDC GitHub/main con sujeto inmutable y audiencia STS exactos, separado de Deploy.
La identidad de operador valida cuenta y excluye roles runtime/CI; conserva la
autoridad real de la sesión CloudShell sin crear un usuario IAM adicional.
Los errores de comisión ahora muestran etapa y barrera/código AWS saneado.
Preparadas y probadas las definiciones API/worker E1: mismo digest y credenciales
por proceso, worker acotado a tres horas; falta conectarlas al despliegue real.
Último `make check` con estas correcciones: 117 Python y siete JS aprobado.
El resultado posterior de la comisión corregida se registra a continuación.

### Comisión completada e integración preparatoria

El operador ejecutó `ede76aa` en CloudShell y devolvió: identity/billing/
CloudFormation/private database role bootstrap; RDS privada disponible;
`E1 resources and SQL roles commissioned. E1 ACCEPTANCE PENDING.`
Esto acredita la comisión informada por el operador, no las suites E1 reales.
El usuario autorizó expresamente integrar la base con E1 desactivada para poder
continuar con OIDC/main. PR #8 integrado en `6efb4edb28aacf6dd3f0e2e53087ec80c4169863`;
los checks previos de `ede76aa` aprobaron en push y PR. CI main 42441266774 y CD 42441787035 publish/prepare/migrate/staging aprobados;
producción bloqueada E5. Copia del reporte en docs/evidence/e1-base-staging-6efb4ed.json.
Los probes son E0, no aceptación funcional E1. La continuación está en `feat/e1-staging-acceptance`.
Pendiente: activación del destino, fixture sintético con MFA, worker real,
verificador externo contra copia de BD, pruebas integradas y aceptación E1.

## E0 completada

E0 está aceptada en staging AWS con datos sintéticos. E1–E5 siguen pendientes;
la autenticación funcional de usuarios, los datos de menores, los retiros,
los avisos y la producción permanecen sin habilitar.

## Evidencia de aceptación real

| Comprobación | Evidencia |
| --- | --- |
| Código desplegado | `33f3ac64b87c5c9d2108dd6153ac9f2423ba30d3`; PR #6 integrado tras required/quality/imagen/APK aprobados. |
| CI de main | [42432920498](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42432920498), todos los checks aprobados. |
| CD real | [42433511451](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42433511451): publish, prepare, migrate y staging aprobados. |
| Imagen en ejecución | `sha256:4b19333d4353ae93514f93ebe662351a93f4cedf27604fd96974a02400e2da10`; comparación de tareas reales con la definición nueva y el índice OCI/manifest Linux amd64 aprobado. |
| URL temporal | https://re-ebedcb6688b94b228cd28424e44448c6.ecs.us-east-1.on.aws |
| Red | VPC dedicada; PostgreSQL privado y cifrado; ingreso HTTP de tareas permitido solo desde las SG del ALB real. |
| SQL | Comisión privada CloudShell: TLS verify-full, runtime sin SUPERUSER/BYPASSRLS/DDL, RLS forzada con dos escuelas sintéticas y contexto transaccional sin fuga. Migración CI posterior aprobada con Migrate. |
| Plano público | Ocho probes aprobados desde GitHub sin proxy HTTPS: TLS 1.3/certificado/hostname, live/ready/capabilities 200, negocio/admin 404 y escrituras 403. Cabeceras seguras, sin cookies. |
| Facturación | [Preflight 42430538070](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42430538070): gasto bruto consultado bajo techo, crédito suficiente y vigente hasta 2027-05-06, cuenta correcta e IAM ajeno denegado. |
| Presupuesto | Stack retiro-seguro-budget aplicado; comisión contrastó presupuesto CUSTOM de 150 USD brutos. Alertas 25/50/75/90/100% configuradas, correo fuera del repo. No es un corte rígido. |
| Rama | main protegido y check obligatorio required verificados por API. |

Copia persistente del reporte: [staging](docs/evidence/e0-staging-33f3ac6.json)
y [preflight](docs/evidence/e0-preflight-42430538070.json). Artefactos originales
13598188946 y 13596459500. El reporte del CD contiene SHA, digest, tarea, red, probes y
caducidad; no contiene credenciales ni saldos. La prueba desde el entorno
interceptado por proxy también pasó, pero no se usa como atestación TLS del origen.
Producción permanece BLOCKED/NOT_CONFIGURED hasta E5; su fallo explícito no se
presenta como un despliegue. La aceptación E0 corresponde al job staging aprobado.

## Operación y coste

RDS PostgreSQL 17 privado db.t4g.micro/20 GB sustituye Aurora Express porque Free
Plan obliga a una pasarela pública en ese modo. No se amplió el plan. API Fargate
con ALB y URL administrada, sin comprar dominio ni NAT Gateway.

Retirada de API programada a tres horas por despliegue; guarda horaria detiene RDS
fuera de la ventana activa y tras sus reinicios automáticos semanales. La guarda
está configurada; no se atribuye una ejecución futura de parada ya realizada.
La retirada programada de este reporte es el 7 de noviembre de 2026 a las 23:18
(America/Bogota); el instante UTC exacto está en el JSON. Detener RDS no
elimina costes de storage, backups y secretos; reserva de hasta 27 USD dentro de
los 30 existentes. E0 reserva 3 USD, reasignados de E1 (22 USD), manteniendo total
150 USD. Tarifas y límites en infra/aws/cost-estimate.md.

OIDC de GitHub/main, sujeto inmutable y audiencia STS; Deploy/Migrate y credenciales
SQL runtime/migrador/bootstrap separados. El pipeline no recibe la credencial raíz
SQL. No usa claves AWS permanentes ni el código OAuth de una sesión anterior.
El login/wizard/catálogo del Agent Toolkit interactivo no está acreditado: no se
presenta la identidad CI como ese login humano.

## Validación y límites de E0

- make check: 64 pruebas Python, 3 JS, PostgreSQL real, lint, tipos, migraciones,
  checks Django y compatibilidad Expo; cfn-lint, actionlint y Bash aprobados.
- CI analiza dependencias y secretos; imagen/API/worker no privilegiados. Worker
  solo tiene diagnóstico y rechaza ejecución de handlers aún inexistentes.
- APK arm64 SDK 56 compilado y firma debug verificada por CI. Repo público:
  manifiesto/checksum público, binario interno sin distribución pública. Firma
  estable, destino privado de distribución y pruebas físicas quedan para E5.
- La liveness interna ALB usa Host=IP privada: GET/HEAD stateless se atiende antes
  de CommonMiddleware solo con TRUSTED_INGRESS=ecs-express. Otras rutas y métodos
  mantienen validación Host/CSRF/HTTPS. Se reprodujo el 400 anterior; imagen local
  readonly sin /tmp devuelve 200 al probe y 400 a Host desconocido en API.
- No se acredita IdP/MFA humano, políticas de dominio, WORM/outbox, AT01–AT08 ni
  restauración/RTO. Son entregas E1–E5, no sustituidas por las sondas técnicas E0.

PR de preparación: [#5](https://github.com/A-PerfectStranger/special-funicular/pull/5).
PR de corrección y conexión: [#6](https://github.com/A-PerfectStranger/special-funicular/pull/6).
Publicación inicial previa [42430973973](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42430973973)
y comisión CloudShell comprobaron SQL/red; sus ocho probes devolvieron 503 en la
imagen anterior 9f988a1. La corrección de Host del ALB y el CD 42433511451
constituyen la aceptación actual; no se atribuyen los artefactos de otro SHA.

## Continuación E1: estado verificable y siguiente paso

Rama `feat/e1-staging-acceptance`, base main `6efb4ed`. E1 continúa abierta.
El usuario autorizó mantener Cognito con bloqueo exponencial nativo y backend
5 fallos en 15 minutos/bloqueo de 15 minutos. RFS07 y aceptación actualizados.

Cambios de continuación, aún sin aceptación AWS:

- Managed Login v2/Essentials para soportar prompt=login; política comprobada
  por backend. No ampliar el plan de AWS automáticamente si el nivel se rechaza.
- Herramienta privada de 13 identidades sintéticas/TOTP, dos escuelas y familias;
  contraseñas/semillas solo en Secrets Manager, mensajes suprimidos, transacción
  importer auditada. No se ha ejecutado ni creado usuarios en este ensayo.
- Regresión real local corregida: logout con refresh anterior a una rotación
  revoca la familia actual. Historial de hashes protegido con RLS; replay revoca.
  Móvil evita refresh oculto durante navegador y bloquea acceso local si falla
  el borrado de SecureStore. No afirmar borrado del SO cuando falla.
- Verificador externo puede comparar bytes/hash contra una copia SQL exportada,
  detectando edición aunque se recalculen hashes locales; CLI sin Django/SQL.
- Migraciones identity 0003 y evidence 0011/0012 todavía no aplicadas en AWS.

Orden siguiente: terminar checks de esta rama; publicar candidato por PR;
actualizar stack E1 revisado con operador; integrar migraciones y despliegue
API/worker acotado por digest; ejecutar provisión sintética privada y aceptación
real web/móvil/SQL/WORM/KMS, incluida copia divergente y recibo tardío. No marcar
E1 terminada por comisión, formulario de Cognito, fixtures o tests simulados.
Esta sesión no posee credenciales AWS de operador. No reutilizar códigos OAuth
antiguos ni pedir contraseñas/semillas por chat. Los IDs públicos del proveedor
fueron facilitados por el usuario; los secretos no.

Checks de continuación antes del siguiente cambio de CD: `make check` aprobado,
129 Python y nueve JS (siete móvil y dos vendor), PostgreSQL real, lint, tipos,
CFN, migraciones y Expo. `make security` aprobado: pip-audit/npm sin vulnerabilidades,
gitleaks de historial/árbol sin secretos. No equivale a CI del próximo commit ni
al ensayo real AWS. Estos resultados incluyen la regresión de logout/refresh.

Conexión de ensayo preparada: workflow manual `E1 synthetic trial`, mismo grupo
serializado que CD, exige CI main actual aprobado, publica el OCI aprobado y
usa Deploy/Migrate separados. API y archivador usan el mismo digest, credenciales
por proceso y ventana de tres horas. Relevo verificado antes de detener worker
previo; nuevas pruebas cubren fallo y orden de relevo. `e1_enabled=false` conserva
CD habitual apagado. No se ha ejecutado el workflow ni aceptado E1 en AWS.
AWS SAR confirma que DescribeUserPoolDomain no admite ARN individual; lectura
regional separada, resto de permisos Cognito continúa acotado al pool.
`make check` del adaptador de despliegue: 131 Python/nueve JS aprobado; bundle
Android/Hermes exportado. La IaC posterior de permiso regional también pasó
cfn-lint y tipos. CI del primer checkpoint 4324519: quality aprobado; imagen/APK
seguían en ejecución al registrar esta línea.

El operador actualizó el stack desde `0dd67fb` y confirmó nuevamente todas las
etapas y `E1 resources and SQL roles commissioned. E1 ACCEPTANCE PENDING.`
Tras la actualización, Chromium obtuvo HTTP 200 del login real, con username y
password visibles; no se introdujeron credenciales ni se acredita MFA todavía.

La continuación prepara jobs de navegador/protocolo real y verificador externo
bajo E1Acceptance/E1Verifier distintos. Los secretos sintéticos entran solo por
stdin/memoria: sin screenshots, trazas o logs de códigos/tokens. El verificador
consulta configuración real y confronta firmas/versiones/retención, prueba Sign,
Put, delete de versión COMPLIANCE vigente y reducción de retención denegados.
No intenta deshabilitar claves. Falta ejecutar estas suites, recuperación con
copia SQL divergente, revocación administrativa y fallo/retardo real de archivo.
También se prepara build APK con endpoint/scheme/package de staging, firma de
desarrollo y solo manifiesto público; no acredita retorno nativo en un teléfono.
Validación local de estas herramientas: `make check` aprobado (136 Python/nueve
JS), actionlint 1.7.12 oficial con checksum verificado, sintaxis Bash y Node
aprobadas. Las suites browser/cloud aún NO se ejecutaron contra AWS. No atribuir
al próximo commit el APK ya compilado por CI de una revisión anterior.
Se reprodujo un bundle de staging sin endpoint/callback al reutilizar caché Metro.
La exportación con --clear produjo otro hash e incluyó ambos valores, contrastados
contra los bytes Hermes reales. El build APK ahora limpia esa caché, fuerza tareas
y verifica el bundle/manifest del APK real antes de emitir manifiesto; falta
compilar ese APK en CI. CI push/PR de 0dd67fb aprobadas, incluidos imagen y APK de
desarrollo; no se atribuyen a los cambios posteriores.
Revisión de la suite: el navegador fija el origen Cognito de ensayo antes de
introducir usuario, contraseña o TOTP; una redirección a otro origen falla sin
enviar el fixture. Validación de sintaxis Node y actionlint aprobadas. Las suites
reales siguen pendientes de las migraciones/main y provisión privada.

## Primer ensayo integrado real de E1 (26d7d47)

Workflow 42449912611: publish/prepare/migrate/trial y staging-apk aprobados.
API/archivador por digest verificado y E1 habilitada solo en la ventana sintética.
Browser: tres logins escolares protegidos, reauth/DTO/paginación/fechas/logout
aprobados; flujo móvil PADRE falló y GUARDIA no llegó a ejecutarse. No aceptación
integral. Cloud independiente aprobado: Cognito/MFA configurados, COMPLIANCE siete
días, versionado/cifrado, claves activas/separadas, Sign/Put/delete de versión y
reducción de retención denegados. 19 eventos verificados, high-water externo
19 / 1e1c4538921d06e7ad866c6826d55e5e4de3dc0410915fcb0af7c32c76ffae2e.

Fallo móvil diagnosticado: Chromium no publica response para el redirect a un
esquema nativo. Reproducido con servidor local sin credenciales. Harness corregido
con CDP Fetch; dos regresiones Chromium reales aprobadas (captura/rechazo de esquema
nativo ajeno). No se afirma todavía que el flujo móvil real haya pasado.

En feat/e1-live-verification se preparan drill de archivo ausente/tardío,
recuperación siempre intentada y copia SQL privada mediante importer/función
estrecha auditada. La copia reescrita conserva formato PostgreSQL y cadena/hash
local válidos, pero se contrasta con versiones/manifiestos externos. Se distingue
SnapshotDivergence de un fallo del archivo para evitar falsos aprobados.
Nueva evidence 0013 aplicada solo local; no ejecutada en AWS. No hay nuevos roles
AWS ni cambios de retención/clave. Falta CI/integración y ensayo real de estos
comandos. Último make check: 145 Python/nueve JS aprobado; además dos regresiones Chromium
reales aprobadas tras corregir el timeout demasiado corto de la prueba negativa
y liberar Fetch al cerrar. Seguridad sin vulnerabilidades ni secretos.
Las pruebas de recuperación siempre intentada y límites de grants/JSON IAM
aprobaron localmente. Todo este incremento sigue sin CI/aceptación AWS propia.

### Continuación después del PR #10

PR #10 integrado en 5ac4f0296165361cf530f0f30ad350bbc542d6da tras todos los checks
push/PR aprobados; CI main 42452708111 aprobada. CD y repetición real de los
nuevos ensayos se revisan por separado. Rama siguiente feat/e1-identity-checks.
Preparado sondeo anónimo real del backend 5/15 en job opcional sin OIDC/secretos:
cinco fallos, start válido denegado, otro punto disponible, controles durante la
ventana y recuperación a 905 s. Todavía no ejecutado. No es una prueba del bloqueo
nativo Cognito ni sustituye la recuperación/revocación de cuenta pendientes.

### Gate continuo preparado en la continuación de PR #11

Browser/cloud/APK/archive-drill extraídos a workflow compartido invocado por el
ensayo manual y CD cuando e1_enabled=true. La promoción exige éxito del gate si
E1 está habilitada; E1false permite conservar la base preparatoria. Actionlint y
revisión estática aprobados, ejecución real aún pendiente. No hay nuevo rol IAM,
retención ni aprobación manual rutinaria. El grupo serializado se mantiene solo
en los callers para evitar bloqueo por anidamiento. Producción continúa E5.

La recuperación privada se probó también tras interrupción entre cambio en
Cognito y checkpoint en Secrets Manager: si la contraseña pendiente ya autentica
con MFA, solo finaliza el checkpoint y no intenta volver a asignarla. Regresión
fallida antes de corregir y aprobada después; evita chocar con una política de
historial de contraseñas al reanudar. Etapas privadas emiten etiquetas constantes
para diagnosticar un BLOCKED sin divulgar errores del proveedor o credenciales.
Último make check de esta continuación: 154 Python/nueve JS aprobado; escaneo del
árbol sin secretos. El ensayo real continúa pendiente.
