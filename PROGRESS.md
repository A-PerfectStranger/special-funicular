# Estado de ejecución — E1 en implementación

## Sesión E1 actual (7 de noviembre de 2026, America/Bogota)

Base remota comprobada con `git fetch --prune origin`: `bbe48f4`. Checkout
actualizado por fast-forward desde `33f3ac6`; rama `feat/e1-identity-evidence`.
Se leyeron AGENTS, PLAN, PROGRESS y requisitos; criterios y etapas previos al
código en `docs/e1-acceptance.md`. El usuario eligió Cognito para ensayo y
autorizó siete días de retención WORM exclusivamente para datos sintéticos.

**E1 no está terminada ni aceptada en AWS.** Cambios locales en curso:

- Modelos identity/school_roster/evidence; migraciones compatibles hacia delante,
  RLS forzada, credenciales SQL separadas, funciones de eventos/sesiones/archivo.
- OIDC Code/PKCE, firma/issuer/audiencia/nonce/tiempos/MFA, sesiones revocables,
  BFF Django con CSRF y credencial aislada de lectura del sistema.
- Archivador S3/KMS, versiones/recibos/manifiestos/checkpoints externos y verificador
  sin conexión SQL; transporte móvil con navegador del sistema y SecureStore.
- Nada de esto se ha desplegado. La bandera E1 está desactivada por defecto.

Evidencia local intermedia: baseline `make check` aprobada; 27 regresiones nuevas
de identidad/aislamiento aprobadas con PostgreSQL real y firmas RSA reales.
Ruff y mypy aprobaron esa revisión. Los mocks del IdP y recibos simulados de las
pruebas de SQL **no** acreditan Cognito, WORM ni KMS reales. Pruebas adicionales,
integración completa, CI/builds, configuración cloud y aceptación E1 pendientes.

El entorno sufrió una interrupción y se recuperó con el árbol/logs intactos.
Antes de la interrupción, `make db check` completo pasó con **103 pruebas Python
y siete JS**, lint, tipos, migraciones, Django y Expo. Hay ediciones posteriores
de archivo/IAM que necesitan revalidación. Se guardó una nota mínima de continuidad
con autorización del usuario en la rama documental `docs/e1-session-recovery`;
esa rama no contiene la implementación ni acepta E1.

Próximos pasos: completar/validar archivador y móvil; preparar IaC/commissioning
E1 sin ampliar permisos del CD E0 de forma implícita; actualizar contratos,
runbooks y controles de aceptación; ejecutar suites y registrar fallos/bloqueos.
Esta sesión no dispone aún de una identidad AWS de operador acreditada. OIDC
de CI/main existente no es esa identidad. No usar el código OAuth viejo.

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
