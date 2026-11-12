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
productiva todavía sin valores observados; el intento de foundation quedó
bloqueado y el estado AWS requiere diagnóstico.
Regresión local: 491 Python, con PostgreSQL/TLS/roles reales; 27 JavaScript;
diez Chromium/recuperación/diagnóstico; tipos/lint/plantillas/checks Django,
compatibilidad Expo y auditorías de dependencias/secretos aprobados. CI del PR y
CD del futuro main se verifican por sus propios resultados antes de continuar.

## Candidato y operación pendiente

Main integrado: `3bb305635f8e13671408e47970fe236431bb5be3`, PR #36.
[CI 43158678756](https://github.com/A-PerfectStranger/special-funicular/actions/runs/43158678756)
aprobó; [CD 43159800799](https://github.com/A-PerfectStranger/special-funicular/actions/runs/43159800799)
está en curso, con publicación/preparación/migración aprobadas y staging pendiente.
Digest publicado: `sha256:9aa7cf6637f0706208016d0a8c4f7d0ccb931ebd6c78eba36b89edbed776c3a3`.
La aceptación de la base anterior no acredita este candidato automáticamente.

El operador confirmó cuenta y preflight completo de gasto/crédito/custodia con
reservas USD 40 nuevos + 50 retenidos + 30 contingencia, dentro del techo USD 150.
Inventario observado: diez secretos con prefijo, tres CMK, RDS staging 20 GiB y
cero snapshots manuales. Plan privado en el checkout CloudShell, bajo
`work/production-cost-plan.json`; su variable de ruta es `$production_checkout`.

**Foundation devolvió BLOCKED/PRODUCTION_OPERATION_FAILED sin etapa.** Se desconoce
si llegó a crear recursos: leer primero precondiciones, versiones PostgreSQL y
estados/eventos de los dos stacks productivos. No repetir comisión ni borrar
stacks, claves, secretos o BD para diagnosticar. Falta identificar la causa real.

`feat/production-diagnostics` corrige localmente la pérdida de contexto: etapas y
códigos fijos, errores AWS/HTTP saneados y reporte de fallo, sin excepciones/URLs/
credenciales remotas. Treinta pruebas pertinentes, tipos y lint aprobados.
Cambio aún sin publicar; completar la corrección con la causa observada antes de
iniciar CI al final, sin esperar ejecuciones largas ni alterar el candidato activo.

Después: resolver foundation conservando recursos; commission y configuración
observada mediante PR; aceptación E4 y E5 conjunta. Android 13 disponible, sin
APK instalado. Siguen pendientes aviso/recibo Expo real, allowlist, alarma/p95,
recuperación/epoch/carga, firma/retención productivas y ensayo presencial.

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
