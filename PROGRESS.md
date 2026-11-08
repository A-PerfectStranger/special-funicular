# Estado de ejecución — E1 en implementación

## Checkpoint E1 (7 de noviembre de 2026, America/Bogota)

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
