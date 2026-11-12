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
aceptación E2/E3. El operador repuso cuatro cohortes nuevas desde main aprobado
usando el bloque persistente; confirmó `E2 synthetic MFA fixtures prepared.`
El bloque terminó tras el preflight financiero y FREE activo, con reservas
USD 120 y techo USD 150, sin mensajes reales ni reset de las cohortes usadas.
El trial_id se conserva para reanudación. **Reposición confirmada por operador;
aceptación E2/E3 del candidato aún pendiente.** No confundir preparar MFA con
aprobar los gates; reejecutar CD solo al final, sobre el candidato que corresponda.
Digest publicado: `sha256:9aa7cf6637f0706208016d0a8c4f7d0ccb931ebd6c78eba36b89edbed776c3a3`.

## Estado AWS que condiciona la continuación

Cuenta `028364485203`, `us-east-1`, operador CloudShell; techo total USD 150.
El operador confirmó preflight financiero con reservas USD 40 nuevas + 50
retenidas + 30 contingencia. Debe revalidarse antes de nuevas operaciones: gasto
bruto más reservas <= USD 150, crédito suficiente y FREE activo durante toda la
custodia. El resultado previo no acreditó compatibilidad del backup de siete días.
Inventario observado previo: diez secretos con prefijo, tres CMK, RDS staging
20 GiB/backup un día y cero snapshots manuales. No usarlo como inventario posterior
al fallo. El checkout temporal y su variable ya no aparecen en CloudShell.
El bloque entregado usa `$HOME/retiro-operador-3bb3056` de forma persistente,
reconstituye el plan privado con la revisión real conservada (sin fingir una
revisión nueva) y ejecuta preflight actual antes de mutar. Trial reanudable en
`work/e2-refill-trial-id`; plan en `work/production-cost-plan.json`.

Source check pasó. `retiro-production-base` está `ROLLBACK_COMPLETE`: RDS rechazó
backup de siete días por límite del plan gratuito. `retiro-production-lifecycle`
no existe. **Ausencia de BD y recursos retenidos aún no inspeccionados.**
No repetir foundation ni eliminar recursos manualmente. El responsable rechazó
PAID y autorizó backup de un día para conservar FREE y el techo USD 150.
Evidencia 90 días y custodia mínima de claves 97 días se mantienen. El código
no cambia el plan; si FREE o sus créditos no cubren la custodia, bloquea.

## Corrección preparada

`feat/production-diagnostics` añade etapas/errores saneados, guardia FREE activo
durante toda la custodia y recuperación restringida. La plantilla y la
verificación RDS exigen backup de un día, conforme a la política actualizada.
El inspector solo lee metadatos; exige BD ausente y retención/identidad KMS-secretos correctas.
La recuperación compara un plan privado con el estado actual, retira únicamente
el registro CFN fallido y reutiliza los mismos recursos Retain. Estado desconocido
o deriva bloquean. [Producción](docs/runbooks/production.md) contiene los comandos
y la reanudación tras interrupción; no ejecutarlos desde una rama sin aprobar.

Validación local de esta revisión: 73 pruebas pertinentes de producción/cohortes,
mypy de 166 archivos, lint/formato, todas las plantillas CloudFormation, once
bloques Bash y escaneo de secretos aprobados. No equivalen a aceptación AWS. [PR #37](https://github.com/A-PerfectStranger/special-funicular/pull/37) actualizado;
CI queda pendiente de resultado y se
consulta por SHA en Actions. Integrar solo tras checks verdes.
No esperar ejecuciones largas. Después: checks del PR, integración/main CI,
gates E2/E3 con el pool repuesto, finanzas/continuidad FREE actualizadas,
inspección y reparación conservadora,
candidato aprobado, comisión y configuración observada por PR y aceptación E4/E5 conjunta.

## Controles que se conservan

Producción técnica: todas las funciones de negocio apagadas. Staging mantiene
`e4_enabled=false`; ambos destinos `pickup_enabled=false`, `synthetic_only=true`.
IdP/WORM/KMS/firma/retención productivos, Expo real, recuperación/epoch/carga,
retirada efectiva del gateway/BD y pruebas presenciales siguen pendientes.
No borrar eventos/recibos/WORM/claves/backups ni recomisionar recursos de staging
para reintentar. Docker local conserva BD y contenedores de ensayo detenidos;
`work/` contiene scratch privado, nunca evidencia de aceptación AWS.
