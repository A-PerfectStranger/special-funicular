# Continuidad

[PLAN](PLAN.md) concentra criterios y aceptación; [README](README.md) y runbooks,
comandos. **E4/E5 y producción real siguen pendientes.** Sin datos/avisos reales,
activación escolar ni prueba física. Android 13 disponible sin APK instalado.

## Candidato y verificaciones

Main: `3bb305635f8e13671408e47970fe236431bb5be3`, PR #36, remoto actualizado.
[CI 43158678756](https://github.com/A-PerfectStranger/special-funicular/actions/runs/43158678756)
aprobado. [CD 43159800799](https://github.com/A-PerfectStranger/special-funicular/actions/runs/43159800799)
publicó imagen y APK privado, pasó migración/staging/E1; E2 terminó bloqueado
`E2_COHORT_POOL_EXHAUSTED`. E3 y producción omitidos: este candidato no tiene
aceptación E2/E3. Añadir cohortes sintéticas mediante operador sin reutilizar ni
resetear las usadas. Runbook E2 contiene el refill; no repetir CD antes de resolverlo.
Digest publicado: `sha256:9aa7cf6637f0706208016d0a8c4f7d0ccb931ebd6c78eba36b89edbed776c3a3`.

## Estado AWS que condiciona la continuación

Cuenta `028364485203`, `us-east-1`, operador CloudShell; techo total USD 150.
El operador confirmó preflight financiero con reservas USD 40 nuevas + 50
retenidas + 30 contingencia. Ese resultado no acreditó compatibilidad del plan
de cuenta ni la nueva comprobación independiente de caducidad del crédito.
Inventario observado previo: diez secretos con prefijo, tres CMK, RDS staging
20 GiB/backup un día y cero snapshots manuales. No usarlo como inventario posterior
al fallo. Plan privado en `$production_checkout/work/production-cost-plan.json`.

Source check pasó. `retiro-production-base` está `ROLLBACK_COMPLETE`: RDS rechazó
backup de siete días por límite del plan gratuito. `retiro-production-lifecycle`
no existe. **Ausencia de BD y recursos retenidos aún no inspeccionados.**
No repetir foundation ni eliminar recursos manualmente. Mantener siete días.
Cambiar a PAID requiere decisión explícita del titular: permite cargos fuera del
crédito; Budgets no impone un corte USD 150. Esa decisión sigue pendiente.

## Corrección preparada

`feat/production-diagnostics` añade etapas/errores saneados, guardia PAID, revisión
separada de vencimiento de créditos y recuperación restringida. El inspector
solo lee metadatos; exige BD ausente y retención/identidad KMS-secretos correctas.
La recuperación compara un plan privado con el estado actual, retira únicamente
el registro CFN fallido y reutiliza los mismos recursos Retain. Estado desconocido
o deriva bloquean. [Producción](docs/runbooks/production.md) contiene los comandos
y la reanudación tras interrupción; no ejecutarlos desde una rama sin aprobar.

Validación local pertinente: 56 pruebas Python, mypy de 166 archivos, lint/formato
y plantilla CloudFormation aprobados. No equivalen a aceptación AWS de esta
recuperación. Rama publicada para PR; CI queda pendiente de resultado y se
consulta por SHA en Actions. Integrar solo tras checks verdes.
No esperar ejecuciones largas. Después: decisión PAID, crédito real actualizado,
inspección, reparación conservadora, refill E2, candidato aprobado, comisión,
configuración observada por PR y aceptación E4/E5 conjunta.

## Controles que se conservan

Producción técnica: todas las funciones de negocio apagadas. Staging mantiene
`e4_enabled=false`; ambos destinos `pickup_enabled=false`, `synthetic_only=true`.
IdP/WORM/KMS/firma/retención productivos, Expo real, recuperación/epoch/carga,
retirada efectiva del gateway/BD y pruebas presenciales siguen pendientes.
No borrar eventos/recibos/WORM/claves/backups ni recomisionar recursos de staging
para reintentar. Docker local conserva BD y contenedores de ensayo detenidos;
`work/` contiene scratch privado, nunca evidencia de aceptación AWS.
