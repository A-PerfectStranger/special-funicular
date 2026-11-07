# Estado de ejecución — 7 de noviembre de 2026

## Resultado real

Base técnica E0 implementada y verificada. **Cierre operativo pendiente de AWS**:
no hay staging/producción ni toolkit autenticado. E1–E5 siguen pendientes; ningún
retiro real está habilitado. No se presenta el bloqueo como despliegue exitoso.

Base revisada: `c711ff9`, igual a `origin/main` al comenzar, tras fetch remoto.
Solo existían AGENTS, PLAN y requisitos; se leyeron completos. No había PROGRESS,
código ni pruebas. Rama `feat/e0-foundation`, PR:
https://github.com/A-PerfectStranger/special-funicular/pull/2

## Aceptación y evidencia

| Criterio definido antes de implementar | Estado acreditado |
| --- | --- |
| Checkout limpio y comandos reproducibles | Aprobado en runners GitHub: `make install db check`; locks uv/npm, imágenes por digest y plantilla SDK 56 fijada. |
| Django/templates/móvil/probes sin PII ni retiro parcial | Aprobado por pruebas y smoke de imagen; rutas de negocio/admin ausentes, retiro siempre deshabilitado. |
| CI lint/typecheck, unitarias, contratos, migraciones, PostgreSQL, secretos/dependencias | Aprobado: 15 tests Python, 3 tests JS; Ruff/mypy/ESLint/TypeScript, checks Django/Expo, pip-audit/npm audit/gitleaks sin hallazgos. |
| Imagen API/worker y APK con SHA/checksum/digest | Aprobado en CI y build local. Worker solo tiene diagnóstico; sin handlers E1/E4 falla explícitamente. APK arm64 standalone con clave de desarrollo. |
| Estructura CD y bloqueo honesto sin destino | Aprobado: validadores salen 2 con BLOCKED/NOT_CONFIGURED; workflow no inventa deploy. Adaptador live pendiente. |
| Staging real y kit AWS | BLOQUEADO: login y configuración de cuenta/recursos/dominio aún ausentes. |

Código/artefactos verificados: `586077c9e82e590a3ec586dacae277b217d1a345`.
Push CI aprobado: https://github.com/A-PerfectStranger/special-funicular/actions/runs/42349447096
PR CI aprobado: https://github.com/A-PerfectStranger/special-funicular/actions/runs/42349529509
Ambos aprobaron quality, backend-image, development-apk y required. Los checks de
revisiones posteriores aparecen en el PR; no atribuir estos artefactos a otro SHA.

### Pruebas y artefactos concretos

- PostgreSQL real: runtime sin SUPERUSER/BYPASSRLS/CREATEDB/CREATEROLE/DDL;
  sonda RLS forzada, escuelas separadas y contexto transaccional sin fuga.
  Esto no acredita las políticas futuras del dominio ni AT01–AT08.
- Imagen como 10001:10001, filesystem de solo lectura y /tmp efímero; probes
  aprobados y sin MIGRATION_DATABASE_URL en runtime.
- OCI manifest digest de CI para `586077c`:
  `sha256:9429903cef435dd0f1af5240a60c262f0493cdc35c25f0df19411ea6fb3ac827`.
  Artefacto OCI y manifiesto (retención 7 días):
  https://github.com/A-PerfectStranger/special-funicular/actions/runs/42349447096/artifacts/13564544466
- APK de CI compilado y firma verificada. SHA-256:
  `7b8eeb40a3457288b01e3a192672b1475273f6b5aad7b99941600544212afb18`.
  Solo se publica manifiesto porque el repo es público. Distribución privada del
  binario pendiente de destino autorizado; no se instaló en teléfonos.
- APK local del mismo código, build distinto (no igualdad binaria):
  `work/artifacts/mobile-development-586077c9e82e590a3ec586dacae277b217d1a345.apk`.
  SHA-256 `56ec9e3be09ebdb48062f0cc35d7ee2352593a9ef2c1f628ac1058d99c73c2ac`;
  apksigner aprobado: v2, RSA 2048, clave debug. Manifiesto .apk.json local.
  Archivo ignorado, no garantizado en un contenedor nuevo; reconstruir con make apk.
- cfn-lint y actionlint aprobados; presupuesto validado offline, no aplicado.
  Pruebas físicas en dispositivos pendientes de E5.

### Problemas corregidos y límites

- Docker no leía SQL montado: permisos de lectura corregidos.
- Plantilla nativa fuera del SDK: fijada a 56.0.38. Gradle 9 incompatible con
  Foojay/RN 0.85: plugin fija Gradle 8.14.3 y checksum oficial tras prebuild limpio.
- Dependencias transitivas vulnerables: overrides Zod/glob/minimatch y backport
  local deepmerge con licencia/regresiones porque no hay release upstream corregida.
  npm audit no analiza ese código local; sus pruebas permanecen obligatorias.
- Disco de unos 8 GB: varios intentos Android fallaron por espacio antes del build
  exitoso. Se retiraron cachés/herramientas opcionales locales; CI usó SDK completo.
  Después de verificar firma se eliminaron NDK/cachés Gradle temporales. Reinstalarlos
  según README antes de reconstruir. No se alteró fuente para ocultar fallos.
- gh falló al descargar redirects de artefactos; el conector GitHub recuperó logs y
  manifiesto. El OCI excede el límite de transferencia de 32 MiB del executor:
  conservar referencia GitHub, no afirmar una copia local verificada.
- Protección de rama/permisos de Actions: lectura HTTP 403. No se verificó que
  GitHub imponga E0 CI / required; los checks sí se ejecutaron y revisaron.

## AWS: estado exacto y siguiente acción

Usuario confirmó perfil aesir, experiencia avanzada (sin proyecto), us-east-1 y
máximo TOTAL 150 USD de créditos. Linux/curl/uv/red comprobados. CLI 2.39.6 instalada
con firma GPG verificada en work/bin/aws; perfil en work/aws/config. Rutas temporales
ignoradas, sin secretos en Git; una sesión nueva puede requerir reinstalación.

El navegador compartido falló con `the gaas-browser node_repl sandbox cannot be disabled`;
el usuario no tiene terminal del entorno. Se intentó aws login --remote y entregar
el código mediante secreto privado, sin leerlo/imprimirlo. Usuario confirmó que
secretos nuevos solo llegan a sesiones nuevas. Instancia actual: revisión 1,
secrets vacíos y variable ausente. Se canceló el intento: **login, STS, wizard,
MCP y catálogo NO verificados**. El código temporal guardado no sirve para iniciar
otro flujo: eliminarlo/renovarlo cuando exista canal interactivo, nunca pegarlo en chat.

Siguiente sesión: resolver navegador/terminal compartido o ejecutar el kit en el
equipo del usuario siguiendo infra/aws/README.md. Un login local no autentica este
contenedor. Tras login: STS, wizard humano, perfil env de aws-mcp, catálogo y reglas
oficiales añadidas a AGENTS sin sobrescribirlo. No pedir access keys/secret keys ni
declarar setup completo antes de verificar todos esos pasos.

No se crearon recursos AWS desde esta sesión. Saldo/gastos reales no consultados:
no afirmar gasto cero de la cuenta. Distribución de los 150 USD propuesta:
25 E1 + 35 E2/E3 + 20 E4 + 40 E5/despliegue + 30 reserva. Presupuesto CUSTOM y alertas
preparados, no aplicados; no son un corte rígido. Faltan correo/fechas reales,
saldo/vencimiento de créditos y cotización por horas. No destruir evidencia ni
claves retenidas para ahorrar.

## Continuación

1. Revisar integración y CI en el PR y sincronizar remoto antes de tocar código.
2. Completar autenticación/toolkit AWS; verificar saldo y presupuesto y configurar destinos.
3. Aprovisionar por IaC tras calcular coste y aportar dominio/configuración; implementar
   adaptador live y verificar staging. Mantener bloqueo hasta evidencia real.
4. Configurar custodia/firma estable y destino privado de APK; build no equivale a instalación.
5. Avanzar E1: IdP/MFA, modelos, RLS de dominio, evidencia y WORM/KMS reales sintéticos.
   Ningún requisito E1–E5 queda implementado por esta base E0.
