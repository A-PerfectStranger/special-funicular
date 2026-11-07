# CD y continuidad operativa E0

Estado: estructura de CD implementada; adaptador AWS y recursos no configurados. No hay staging/producción ni una versión previa para rollback. Nunca rellenar `staging_evidence_verified` sin ensayos reales. No hay datos reales ni invitaciones enviadas.

1. Revisar `PROGRESS.md`, `PLAN.md`, AGENTS y requisitos; fetch remoto, preservar cambios locales.
2. Ejecutar README/checks. Revisar SHA de candidato y resultados CI; no confundir builds locales de árbol modificado con el commit base.
3. Resolver Toolkit/login y cuenta/región; revisar presupuesto real. Definir dominio/TLS, red privada, PostgreSQL administrado, identidades separadas, secretos y destinos por entorno. Declarar recursos en IaC revisable antes de aplicarla.
4. Integrar adaptador de despliegue real: OIDC de GitHub restringido a repo/ref/audiencia; no credenciales estáticas. Imágenes por digest; migración con identidad separada bajo exclusión mutua; runtime sin DDL. Validar digest/provenance contra SHA de CI.
5. Ejecución staging: recursos y permisos reales, TLS y readiness; conservar registros de commit/digest/migración/fecha/resultado. En E0 solo sondas/sintéticos; AT01–AT08 van con E1–E5. No permitir retiro por readiness técnico.
6. Promoción productiva automática solo al cumplir regresión del incremento; mismo digest, no rebuild. Concurrencia sin cancelación; comprobar ascendencia frente a SHA ya publicado bajo el bloqueo para no sobrescribir con un candidato obsoleto. Actualmente no existe esa promoción: CD falla antes del despliegue.
7. Al fallar migración, no publicar ni revertir esquema: reparar hacia delante. Al fallar salud después de publicar, revertir solo a digest anterior compatible. Nunca borrar evidencia ni restaurar DB como rollback de código. Runbook de recuperación completa con WORM/epoch se implementará y ensayará antes de E5.

Faltan configuración del hosting, permisos/OIDC, registro privado de imágenes/APK, TLS/domino, IdP/KMS/WORM/retención, ensayos y monitoreo. La validación sintáctica del JSON no acredita que un recurso exista ni que sus permisos estén verificados.
