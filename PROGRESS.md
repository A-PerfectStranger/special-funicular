# Estado de ejecución y continuidad

Actualizado: 7 de noviembre de 2026, sesión E0. **E0 EN CURSO, no aceptada de extremo a extremo.** No hay despliegue ni retiro real habilitado.

## Base y decisiones

- Remoto verificado con fetch/ls-remote: main `c711ff9ea266b8e797f4c207d813bfd18aae4762`. Solo AGENTS, PLAN y requisitos; no existía PROGRESS. Rama `feat/e0-foundation`, publicada en https://github.com/A-PerfectStranger/special-funicular/pull/1 (borrador). Main no modificado. Código actual `8e3a228f5592191003ccfe016628e5f452788175`.
- Arquitectura original conservada. Python3.12.14/Django5.2.19 LTS, PostgreSQL16.11, Expo56.0.24/React19.2.3/RN0.85.3. Versiones y lockfiles reales de registros oficiales.
- AWS elegido por el usuario, créditos **USD150 totales**. No recursos creados, gasto AWS de esta sesión USD0; saldo real sin consultar. Presupuesto y condiciones en docs/aws-budget.md.
- Repositorio público confirmado vía GitHub. APK interno no se publicará en artifacts/releases públicos; build local firmado debug solo para ensayo. Registro privado/EAS/firma productiva pendientes.

## Implementado, sujeto a verificación final

Django/templates, live/ready, capabilities v1 con retiro deshabilitado; esqueleto móvil sin PII/QR/sesiones; configuración sintética; PostgreSQL con migrador/runtime separados; Docker no root; contratos JSON; pruebas de fallos/migraciones/permisos; scripts de checks/seguridad; workflows CI/imagen/APK y CD fail-closed; README y runbooks. Worker solo --check: sin procesamiento de outbox aún.

## Evidencia observada hasta ahora

- CI remoto desde checkout limpio: https://github.com/A-PerfectStranger/special-funicular/actions/runs/42345649621 y run42345813117, job checks verde. Logs confirman14 pruebas PostgreSQL/contratos/configuración/workflows + lint/tipos/seguridad sin avisos. Run42346025225 también verifica16 pruebas y todos los checks. Se reforzó además la denegación de tablas temporales en la base de test (TEMP revocado igual que base local); CI del cambio pendiente.
- PostgreSQL real con app_runtime: no superusuario, BYPASSRLS, CREATEDB, CREATEROLE ni CREATE en schema; DDL rechazado. No hay modelos de negocio/RLS hasta E1.
- `scripts/security.sh`: exit0, pip-audit sin avisos, npm audit0, Gitleaks archivos/historial sin secretos. Se corrigió pytest vulnerable y overrides transitivos npm documentados; no se bajó SDK.
- `npm run mobile:export`: bundle Android correcto tras overrides. Prebuild con plantilla fijada56.0.38 correcto. Prebuild sin fijar descargaba SDK57; corregido en script por URL+SHA256.
- Imagen local provisional validó UID10001, home/live/capabilities200 no-store y ready503 con DB inaccesible. Imagen OCI remota del primer CI creada con artefacto backend-9e6f4cc5a14f988f9827738337e9cc9088e832bd (SHA de merge de PR). Segundo CI falló por exportar simultáneamente lista de attestations al formato Docker. Corregido: una plataforma sin attestations, mismo build OCI+Docker y verificación del digest/configuración cargada; smoke con PostgreSQL real agregado. Run42346025225 construye OCI+Docker correctamente; smoke detectó un ConnectionResetError transitorio durante arranque de Gunicorn. Corregido retry de errores de red con límite30 intentos; nuevo CI pendiente.
- APK local: falló primero por Java sin proxy, luego por ausencia de JDK17. Se instaló JDK17.0.21.0.2 oficial en work con checksum, CA y proxy Java sin desactivar TLS. Compilación nativa en curso, log work/apk-build-jdk17.log. CI Android falló inicialmente porque setup-android solicitaba paquete obsoleto tools; corregido con paquetes explícitos. No APK aceptado todavía.
- Disco se llenó por Docker vfs durante primeros intentos. Se retiró imagen/contenedor PostgreSQL de esta tarea tras tests; volumen sintético sigue presente. Docker API provisional detenido e imagen retirada para liberar disco. Para repetir suites levantar Compose (volverá a descargar imagen). No hay datos reales afectados.

## Bloqueos pendientes

1. Toolkit AWS: CLI ausente, awscli.amazonaws.com bloqueado403. Usuario respondió que está modificando red. Refrescar status y probar nuevo request tras confirmación. Preguntas pendientes: nombre de perfil, experiencia social/proyecto o avanzada, región. Guía exige estos datos y login/asistente humanos. No pedir secretos. Ver docs/runbooks/aws-toolkit.md.
2. AWS staging/producción no aprovisionados; infra/environments/*.json configured=false. Validación retorna2; CD falla explícitamente. Adaptador AWS real, IaC, OIDC, TLS, permisos, dominios y ensayos aún pendientes. No marcar quinto ítem E0 completo.
3. APK nativo, firma/paquete y entrega privada pendientes. CI checks verificado, CI completo del código actual pendiente. No confundir bundle con APK.
4. PR1 borrador publicada; integración a main todavía no realizada. No hay permisos de rama/checks obligatorios configurados/verificados.

## Próximos pasos inmediatos

1. Revisar log work/apk-build-jdk17.log y completar build sin desactivar TLS ni proxy; documentar bloqueo si persiste.
2. Revisión final, corregir problemas, suites13+ y smoke imagen con DB; check limpio independiente si recursos lo permiten.
3. Código ya publicado; esperar CI de 8e3a228 y registrar digest/checksum de ese candidato. Builds locales iniciales sin commit son provisionales.
4. Actualizar PR1 y documentación con evidencia final; no integrar con checks fallidos. Mantener E0 pendiente hasta criterios A0–A6 de docs/E0-acceptance.md verificados.
5. Completar Toolkit y staging solo tras inputs/configuración reales. No habilitar retiros ni cargar datos reales; E1–E5 completamente pendientes.
