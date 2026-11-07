# Estado de ejecución y continuidad

7 de noviembre de 2026. **E0 parcial; no declarar entrega completa.** Sin recursos AWS, staging, producción ni retiros reales. Unidad de integración: PR1: https://github.com/A-PerfectStranger/special-funicular/pull/1 . La base se integra mediante PR y CI; Toolkit/staging continúan bloqueados. Consultar el estado de PR1 para confirmar la integración.

## Código y arquitectura

- Base remota verificada: main `c711ff9ea266b8e797f4c207d813bfd18aae4762`; solo contenía AGENTS/PLAN/requisitos. PROGRESS se creó en esta sesión.
- Rama publicada `feat/e0-foundation`; último código probado `b0f2a76e13edee7b4cd8849f2f4c1bc4356d86c0` (ver git log para cambios documentales posteriores).
- Django5.2.19/Python3.12.14, PostgreSQL16.11, Expo56.0.24/React19.2.3/RN0.85.3, JDK17 para APK. Lockfiles versionados. AWS elegido por el usuario, USD150 de créditos **totales**.
- Backend único modular con templates; core solo contiene base/sondas. Móvil con vistas sintéticas padre/guardia sin sesión ni permisos. Sin Django Admin, QR, autorizaciones o datos de estudiantes. Worker solo `--check`; procesadores de outbox pendientes E1/E4. CA-F/CA-S y AT01–AT08 del producto no se acreditan con E0.

## Criterios E0 y evidencia real

| Criterio | Estado y evidencia |
| --- | --- |
| A0: checkout y comandos | Verificado en checkout limpio de GitHub Actions: instalación bloqueada, migración separada y comandos de README. |
| A1: Django/templates/health | Verificado: live sin DB, ready200 con PostgreSQL/migraciones, ready503 genérico ante fallo o migración pendiente; no-store; retiro siempre false; configuración externa falla sin secretos/hosts/TLS válidos. |
| A2: móvil SDK56 | Esqueleto, lint/tsc/test, export Android y prebuild verificados. Plantilla nativa56.0.38 fijada por URL/SHA256. APK nativo, firma y paquete verificados en CI (run42346213379, BUILD SUCCESSFUL); retención local/entrega privada en curso. |
| A3: CI y seguridad | Run42346213379 job checks verde:16 pruebas con PostgreSQL real/contratos/configuración/integridad OCI, Ruff/formato/mypy, ESLint/tsc/test móvil, export de requirements sincronizado, pip-audit/npm audit0, Gitleaks sin secretos. Runtime sin DDL, TEMP, superusuario, BYPASSRLS, CREATEDB ni CREATEROLE. Actionlint local pasa. RLS de negocio pendiente E1. |
| A4: imagen/APK por SHA | Imagen OCI construida una vez, cargada también a Docker y smoke con PostgreSQL real; config digest de la imagen probada coincide con OCI. APK de desarrollo generado y verificado en CI; retención privada/local en curso, sin publicación pública. |
| A5: CD | Estructura y validador implementados; CLI devuelve2 DEPLOY BLOQUEADO. Destinos configured=false; adaptador AWS real, recursos y ensayos de staging pendientes. Workflow bloquea explícitamente, sin permisos/secretos cloud ni éxito ficticio. |
| A6: documentación/coste | README, contratos, arquitectura, runbooks y presupuesto actualizados. Toolkit no configurado; datos/acceso pendientes. |

CI del código anterior y fallos corregidos: run42345649621 checks14 e imagen verdes, Android falló por paquete SDK obsoleto tools (sustituido por paquetes explícitos); run42345813117 detectó exportación Docker incompatible con attestations (retiradas; no se promete SBOM/provenance); run42346025225 checks16 verdes, smoke detectó ConnectionResetError durante arranque (retry de OSError limitado30 intentos, corregido). No presentar esos runs fallidos como CI completo aprobado.

## Artefacto backend verificado

Run: https://github.com/A-PerfectStranger/special-funicular/actions/runs/42346213379 . SHA de merge de PR probado: `c6630a2fdcb472cdef71499bb3e6b40be62e07f3`; corresponde al head b0f2a76 y main base. No confundir SHA del merge de ensayo con SHA de head.

- OCI digest: `sha256:28170f9ef542ff452e5ce2ba24315197923ddb437e2686f743835128f2d43f88`.
- Config digest verificado contra Docker: `sha256:d719b123b990ead53b70e1270193fd774da164767bc529e424382445980875fb`.
- Artefacto: https://github.com/A-PerfectStranger/special-funicular/actions/runs/42346213379/artifacts/13563408758 . Contiene OCI, image.json, lista de dependencias y checksum del tar. Expira14/nov/2026. Digest ZIP del artefacto (distinto al OCI): `sha256:8c4d7a2256edea1cdf99c0c1578fa07399665e1eb8ca578c3b9756c348a70d05`.
- UID10001; APP_ENV por defecto unconfigured bloquea arranque sin configuración explícita. Smoke verifica migración por app_migrator, servicio/worker-check por app_runtime, capacidades false y worker sin handlers rechazado.

## Pendientes y bloqueos

1. **AWS Toolkit**: CLI ausente. Tras reinicio del entorno a las06:16 UTC, status seguía revisión1/enforced y sin awscli.amazonaws.com; request nuevo devolvió403 del proxy. Usuario está modificando red. Datos ya solicitados, sin respuesta todavía: perfil CLI, región, experiencia social con proyecto o avanzada. No pedir claves. Login y asistente requieren intervención humana según guía oficial. Estado/runbook: docs/runbooks/aws-toolkit.md. No añadir reglas de experiencia AWS a AGENTS hasta conocer el tipo correcto.
2. **Staging/CD real**: falta cuenta/acceso/región, destino, dominios/TLS, identidades OIDC/separación de credenciales, infraestructura privada, permisos y ensayos. No cambiar booleanos del JSON para fingir validación. Antes de aprovisionar, plan concreto de recursos/precios/duración dentro de USD150. No hay saldo/facturación verificados, alertas ni recursos creados. Gasto AWS de esta sesión USD0.
3. **APK**: job android-apk de run42346213379 verde: assembleRelease BUILD SUCCESSFUL en5m31s y verificación apksigner/paquete exitosa. El repositorio es público: CI nunca sube el APK interno a artifacts/releases públicos. Build local se interrumpió al reiniciar durante descarga de NDK; se retiró solo la instalación incompleta y NDK27.1.12297006/CMake3.22.1 ya reinstalados. Se repite build local con SHA b0f2a76; ver work/apk-build-final.log. No confundir éxito CI con una copia retenida del binario. Cuenta/proyecto Expo, firma/ID productivos y destino privado de distribución pendientes; desarrollo usa org.retiroseguro.synthetic y firma debug.
4. **Integración**: La base verificada se entrega por PR1 y solo se integra con CI completo verde. Reglas de rama/checks obligatorios aún no configuradas/verificadas en ajustes de GitHub. E0 completa sigue bloqueada por Toolkit/staging; no declarar esos controles cumplidos al integrar código.

## Entorno local y continuación

Todo el código y documentos previos al último estado están publicados en la rama; preservar cualquier actualización documental sin commit. `work/` contiene solo herramientas/logs ignorados, no entregables ni credenciales AWS.

- No hay API/worker de aplicación corriendo actualmente. Imagen provisional local retirada para liberar disco. Docker vfs consumió disco durante ensayos; evitar acumular imágenes/cachés innecesarias.
- Volumen PostgreSQL local sintético de la primera prueba puede persistir con bootstrap anterior al cambio TEMP. Para pruebas actuales, reinicializar **solo ese volumen sintético** según README (down -v + up --wait); nunca aplicar bootstrap local ni este reinicio a AWS/datos reales. CI usa volumen nuevo y ya verifica el bootstrap actual.
- Herramientas nativas locales: JDK17.0.21.0.2 oficial extraído/verificado en work/jdk-latest; SDK en work/android-sdk; GRADLE_USER_HOME=work/gradle; ANDROID_USER_HOME=work/android-user. Proxy Java y CA de la sesión se configuraron allí con TLS verificado. No copiar configuración de proxy/sesión a artefactos.
- Retomar: fetch remoto y comprobar árbol; consultar run42346213379 y logs; completar APK/firma/paquete y entrega privada; cerrar revisión/CI del código; actualizar esta tabla y PR con resultados reales. Resolver datos/red de AWS, completar Toolkit y luego IaC/adaptador/staging con presupuesto antes de aceptar E0. E1–E5 siguen pendientes.
