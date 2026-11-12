# Continuidad

[PLAN](PLAN.md) contiene criterios y aceptación; [README](README.md) y runbooks,
comandos. E0–E3 están aceptadas con sintéticos. **E4/E5 y producción real siguen
pendientes.** No hubo datos ni avisos reales, activación escolar ni pruebas físicas.

## Base verificada

Main de referencia: `ac21cef9cb6a8ea4f2b5477565111cffd799400f`.
[CI 43147560038](https://github.com/A-PerfectStranger/special-funicular/actions/runs/43147560038)
aprobado; [CD 43148696923](https://github.com/A-PerfectStranger/special-funicular/actions/runs/43148696923)
aprobó publicación, migración, staging, E1/E2/E3, APK privado y WORM independiente
hasta 1.637 eventos. Solo producción quedó BLOCKED/NOT_CONFIGURED.
Digest/checksum y alcance en PLAN; la pasarela se revalida contra ECS al descargar.
No atribuir estas aceptaciones a commits posteriores.

## Implementación que continúa

`feat/production-commissioning` prepara la primera ventana técnica productiva:
VPC/BD/KMS/secretos/roles separados, bootstrap SQL, preflight de gasto/custodia,
migración aislada y CD del mismo digest, con salud/TLS y rollback compatible
verificado. Todas las rutas de negocio permanecen apagadas. Configuración
productiva todavía sin valores observados; no se aprovisionó producción.
Regresión local: 491 Python, con PostgreSQL/TLS/roles reales; 27 JavaScript;
diez Chromium/recuperación/diagnóstico; tipos/lint/plantillas/checks Django,
compatibilidad Expo y auditorías de dependencias/secretos aprobados. CI del PR y
CD del futuro main se verifican por sus propios resultados antes de continuar.

## Siguiente operación

1. Recibir resultados CI del PR, corregir si falla e integrar solo con checks
   requeridos aprobados. El responsable pide iniciar CI/CD al final y cerrar el
   turno sin esperar ejecuciones largas; no omitir gates.
2. El responsable tiene operador CloudShell en `028364485203`, `us-east-1`, y
   confirmó mantener USD 150 totales. Preparar revisión privada de precios,
   gasto/crédito y custodia; ejecutar primero el preflight de
   [producción](docs/runbooks/production.md). No pedir secretos por chat.
3. Desde main aprobado: foundation → commission. Contrastar propuesta
   `work/production-configuration.json` con AWS e incorporarla mediante PR.
   CD automático verifica staging completo antes de producción. Los recursos
   y el origen productivos no se inventan para completar el JSON.
4. Continuar E4 y aceptación [E5](docs/runbooks/e5.md) paso a paso con el responsable.
   Android 13 disponible, **sin APK instalado**. Primer paso: descargar candidato
   vigente por canal privado y comprobar instalación; no darlo por probado.
5. E4: registro propio del Android, hashes auditados/allowlist, comisión del
   notificador, aviso/recibo Expo reales, fallo/recuperación, alarma y p95,
   consultas/corrección y verificador final. E5 conserva IdP/WORM/retención y firma
   productivos, recuperación integral/epoch, carga/RTO y ensayo presencial.

## Controles que se conservan

- `e4_enabled=false` en staging; producción técnica mantiene E1–E4 apagadas.
  `pickup_enabled=false`, `synthetic_only=true`. No habilitar negocio por desplegar.
- Cuenta/techo/custodia, retención seleccionada y recursos existentes en PLAN y
  runbooks. No recomisionar Cognito/SNS/KMS ni reutilizar/resetear cohortes para
  continuar. Datos/eventos/recibos/WORM/keys/backups se conservan.
- El gateway es efímero. Callback existente de staging solo se sincroniza contra
  origen/SHA/digest observados con el comando restringido documentado.
- Docker local conserva PostgreSQL de desarrollo y contenedores de ensayo
  productivo aislados, detenidos tras las pruebas. `work/` guarda scratch privado
  y certificados sintéticos; no es aceptación AWS ni se publica al repositorio.
