# AGENTS.md — Instrucciones de desarrollo

Aplica a todo el monorepo de retiro seguro de estudiantes.

## Fuentes y forma de trabajo

Los [requisitos](Requerimientos_retiro_seguro_estudiantes.md) definen el contrato
funcional, arquitectura, seguridad y aceptación. [PLAN.md](PLAN.md) concentra el
estado y el orden de las entregas. [README.md](README.md) documenta instalación y
comandos; los runbooks describen operaciones ejecutables. Consultar esas fuentes
sin copiar sus reglas o estados a documentos nuevos. Las instrucciones explícitas
más recientes del usuario prevalecen.

Avanzar con incrementos pequeños, completos y desplegables. No reabrir decisiones
de arquitectura fijadas. Resolver detalles dentro del contrato; preguntar solo
por datos o decisiones que falten y no puedan obtenerse del repositorio o la
configuración. Continuar las tareas independientes mientras se concretan.

Cada issue/PR enlaza RF/RFS y CA o AB afectados. Actualizar la fuente documental
correspondiente junto al cambio, sin añadir bitácoras, checkpoints de sesión ni
copias de reportes históricos. Los resultados por commit se conservan en Actions;
las evidencias privadas y anclas confiables se custodian fuera del repositorio.
No marcar tareas, pruebas o despliegues como terminados sin evidencia real. Usar
datos sintéticos en desarrollo, pruebas, capturas y demos.

## Implementación y validación

- Mantener backend/web/workers en Django modular, móvil en Expo SDK 56 y contratos
  en `tests/contracts/`. No introducir un frontend web separado ni microservicios
  que repartan la transacción de retiro.
- Fijar versiones compatibles y lockfiles; no cambiar de SDK mayor incidentalmente.
  Documentar comandos reales en README y usar los mismos en CI.
- Aplicar los controles del contrato en el servidor, incluidas transacciones,
  RLS forzada, permisos SQL separados y funciones privilegiadas estrechas. El
  runtime no recibe propiedad de tablas, SUPERUSER, BYPASSRLS, DDL ni migraciones.
- No crear limpiezas genéricas de eventos ni borrar o reescribir evidencia para
  corregir errores o reiniciar ensayos. Las correcciones añaden eventos vinculados.
- Mantener secretos fuera de código/bundle y de `EXPO_PUBLIC_*`; redactar QR,
  credenciales y documentos completos de logs y reportes de fallo.
- Ejecutar pruebas pertinentes y checks requeridos. Usar PostgreSQL real con roles
  runtime para transacciones, RLS y restricciones; las unitarias pueden simular
  adaptadores, pero staging valida IdP/KMS/WORM de ensayo reales.
- Cubrir casos positivos y negativos de permisos, concurrencia, revocación,
  replay, respuesta perdida, archivo fallido/tardío e integridad externa según el
  cambio. No sustituir aceptación del entorno por mocks ni inventar retenciones.

Un incremento terminado incluye contrato/API actualizado, migración compatible
si aplica, implementación, pruebas, observabilidad mínima y resultado verificable
en staging cuando el destino esté configurado. Al entregar, indicar cambios,
pruebas ejecutadas y fallos o bloqueos concretos.

## Integración y despliegue

Ramas cortas y PR con checks requeridos antes de integrar a `main`. Permisos mínimos
de Actions y credenciales efímeras OIDC; no ejecutar código de forks con secretos.
Aplicar el pipeline de PLAN: artefactos por commit/digest, staging y checks antes
de producción automática, sin aprobación manual rutinaria de promoción.

Serializar migraciones y despliegues por entorno, rechazar candidatos obsoletos y
no cancelar migraciones por un commit nuevo. Mantener API compatible con APK
instalados y migraciones expand/contract. Revertir solo código compatible, nunca
evidencia o la BD como rollback de una versión. Un destino sin configurar se
informa como bloqueado, nunca como despliegue exitoso.

Proteger claves de firma y restringir artefactos internos. Publicar un APK no lo
instala en teléfonos. Desplegar software no implica importar estudiantes, enviar
invitaciones/avisos ni activar una escuela: esas operaciones usan lote, destinatarios
y políticas verificados mediante comandos privados auditados.
