# Estado de ejecución

## E0 — En curso (7 de noviembre de 2026)

Base: `c711ff9`, igual a `origin/main` tras `git fetch --prune origin`.
Solo existían AGENTS.md, PLAN.md y los requisitos. Se leyeron los tres; no había
código, pruebas, pipeline ni PROGRESS.md previo.

### Criterios de aceptación

1. Checkout limpio: dependencias fijadas/lockfiles, configuración sintética y comandos reales de README.
2. Django modular, templates y Expo SDK 56: sin rutas de negocio ni autorizaciones parciales; probes sin PII.
3. CI: lint/typecheck, unitarias/contratos, migraciones, PostgreSQL real con rol runtime restringido y escaneo de secretos/dependencias.
4. Imagen compartida API/worker y APK Android de desarrollo: SHA, checksum/digest y trazabilidad; no confundir build con instalación.
5. CD: validación obligatoria, bloqueo explícito sin destino, concurrencia sin cancelar migraciones; staging real pendiente de acceso/configuración.
6. AWS: seguir guía oficial, preservar instrucciones, no pedir secretos en chat; presupuesto total de créditos 150 USD.

### Etapas

1. Base/backend/PostgreSQL y pruebas.
2. Móvil/contratos y APK de desarrollo.
3. CI/artefactos/CD y controles AWS/presupuesto.
4. Verificación desde instalación limpia y registro de evidencia, fallos y siguientes pasos.

### Configuración pendiente del usuario

Se solicitaron juntos perfil CLI, experiencia AWS y región conforme a
https://raw.githubusercontent.com/aws/agent-toolkit-for-aws/refs/heads/main/setup-instructions/setup.md.
Linux detectado; curl/uv disponibles y awscli.amazonaws.com accesible. CLI AWS ausente.
El login y el wizard requieren intervención humana. No hay credenciales AWS configuradas.
Región, dominio, IdP, retención, cuenta Expo y firma productiva no se inventarán.

### Evidencia provisional (antes del commit final)

- `make check`: 10 tests Python, 1 móvil y (añadidos después) 2 de deepmerge;
  lint/typecheck Django/Expo y migraciones sin deriva aprobados. E0 no tiene modelos
  de negocio ni migraciones de dominio; no se acredita aceptación E1.
- PostgreSQL real 17 (imagen Alpine por digest): runtime sin SUPERUSER/BYPASSRLS/DDL,
  RLS forzado en tabla de ensayo y contexto transaccional sin fuga.
- Imagen Docker construida y ejecutada como 10001:10001, filesystem de solo lectura;
  probes reales aprobados. Sin variable MIGRATION_DATABASE_URL en el contenedor.
  Diagnóstico worker muestra 0 handlers; ejecución normal bloqueada explícitamente.
- Bundle Hermes Android exportado; plantilla nativa fijada a SDK 56.
- `npm audit --audit-level=low`: cero avisos con overrides verificados y parche local
  deepmerge (ver vendor/deepmerge/README.md); pruebas contra contaminación de prototipos.
- pip-audit sin avisos en primera revisión; gitleaks sin filtraciones en working tree.
- `cfn-lint infra/aws/budget.yaml` y actionlint 1.7.11 aprobados.
- AWS CLI 2.39.6 instalada, firma GPG verificada, perfil aesir/us-east-1 configurado.
  Toolkit NO instalado: login remoto pendiente; navegador falló con
  `the gaas-browser node_repl sandbox cannot be disabled` y usuario sin terminal.
- Lectura de protección de rama y permisos de Actions: HTTP 403. No afirmar que
  checks obligatorios estén configurados. El repositorio es público: no publicar APK interno.
- Presupuesto: 25+35+20+40+30=150 USD total, límites propuestos, no cotización.
  Sin recursos AWS creados por esta sesión; gasto/saldo de la cuenta no consultados.

### En curso / pendientes reales

APK nativo, verificación desde checkout limpio, ejecución de CI remoto y trazabilidad
final de artefactos. Publicación/integración aún no realizadas. Staging y toolkit
bloqueados por autenticación/configuración; CD falla explícitamente.
E0 NO está terminado mientras estos criterios sigan pendientes.
