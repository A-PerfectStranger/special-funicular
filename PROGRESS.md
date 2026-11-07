# Estado de ejecución y continuidad

Actualizado: 7 de noviembre de 2026, sesión E0. **E0 EN CURSO, no aceptada de extremo a extremo.** No hay despliegue ni retiro real habilitado.

## Base y decisiones

- Remoto verificado con fetch/ls-remote: main `c711ff9ea266b8e797f4c207d813bfd18aae4762`. Solo AGENTS, PLAN y requisitos; no existía PROGRESS. Rama de trabajo `feat/e0-foundation`.
- Arquitectura original conservada. Python3.12.14/Django5.2.19 LTS, PostgreSQL16.11, Expo56.0.24/React19.2.3/RN0.85.3. Versiones y lockfiles reales de registros oficiales.
- AWS elegido por el usuario, créditos **USD150 totales**. No recursos creados, gasto AWS de esta sesión USD0; saldo real sin consultar. Presupuesto y condiciones en docs/aws-budget.md.
- Repositorio público confirmado vía GitHub. APK interno no se publicará en artifacts/releases públicos; build local firmado debug solo para ensayo. Registro privado/EAS/firma productiva pendientes.

## Implementado, sujeto a verificación final

Django/templates, live/ready, capabilities v1 con retiro deshabilitado; esqueleto móvil sin PII/QR/sesiones; configuración sintética; PostgreSQL con migrador/runtime separados; Docker no root; contratos JSON; pruebas de fallos/migraciones/permisos; scripts de checks/seguridad; workflows CI/imagen/APK y CD fail-closed; README y runbooks. Worker solo --check: sin procesamiento de outbox aún.

## Evidencia observada hasta ahora

- `scripts/check.sh`: exit0; Ruff/formato/mypy/Django/migraciones/pytest12 tests + ESLint/tsc/prueba móvil pasan. Se añadió luego test de workflows; verificar suite final antes de cerrar.
- PostgreSQL real con app_runtime: no superusuario, BYPASSRLS, CREATEDB, CREATEROLE ni CREATE en schema; DDL rechazado. No hay modelos de negocio/RLS hasta E1.
- `scripts/security.sh`: exit0, pip-audit sin avisos, npm audit0, Gitleaks archivos/historial sin secretos. Se corrigió pytest vulnerable y overrides transitivos npm documentados; no se bajó SDK.
- `npm run mobile:export`: bundle Android correcto tras overrides. Prebuild con plantilla fijada56.0.38 correcto. Prebuild sin fijar descargaba SDK57; corregido en script por URL+SHA256.
- Imagen provisional local construida (`a12a69...`, árbol todavía sin commit; NO es artefacto aceptado del SHA base). Ejecuta UID10001. Sondas contra contenedor: home/live/capabilities200 no-store; ready503 con DB inaccesible. DB disponible validada por pytest, aún falta smoke de contenedor positivo.
- Build APK nativo: primer intento falló UnknownHostException services.gradle.org (Java no usaba proxy heredado). Segundo intento en progreso con proxy Java configurado solo en work/gradle. No APK aceptado todavía.
- Disco se llenó por Docker vfs durante primeros intentos. Se retiró imagen/contenedor PostgreSQL de esta tarea tras tests; volumen sintético sigue presente. Docker API provisional en puerto8000 sigue activo. Para repetir suites levantar Compose (volverá a descargar imagen). No hay datos reales afectados.

## Bloqueos pendientes

1. Toolkit AWS: CLI ausente, awscli.amazonaws.com bloqueado403. Usuario respondió que está modificando red. Refrescar status y probar nuevo request tras confirmación. Preguntas pendientes: nombre de perfil, experiencia social/proyecto o avanzada, región. Guía exige estos datos y login/asistente humanos. No pedir secretos. Ver docs/runbooks/aws-toolkit.md.
2. AWS staging/producción no aprovisionados; infra/environments/*.json configured=false. Validación retorna2; CD falla explícitamente. Adaptador AWS real, IaC, OIDC, TLS, permisos, dominios y ensayos aún pendientes. No marcar quinto ítem E0 completo.
3. APK nativo, firma verificada y entrega privada, CI remoto/artefacto por SHA aún sin resultado. No confundir bundle con APK.
4. Integración por PR/checks en main todavía no realizada. No hay permisos de rama/checks obligatorios configurados/verificados.

## Próximos pasos inmediatos

1. Revisar log work/apk-build-retry.log y completar build sin desactivar TLS ni proxy; documentar bloqueo si persiste.
2. Revisión final, corregir problemas, suites13+ y smoke imagen con DB; check limpio independiente si recursos lo permiten.
3. Commit de código; reconstruir imagen/APK con SHA de código real y registrar digest/checksum (los builds anteriores con árbol modificado son provisionales).
4. Subir rama/PR y verificar CI si acceso disponible; no integrar con checks fallidos. Mantener E0 pendiente hasta criterios A0–A6 de docs/E0-acceptance.md verificados.
5. Completar Toolkit y staging solo tras inputs/configuración reales. No habilitar retiros ni cargar datos reales; E1–E5 completamente pendientes.
