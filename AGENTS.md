# AGENTS.md — Instrucciones de desarrollo

Proyecto: Aplicación Segura de Rastreo / retiro seguro de estudiantes. Aplica a todo el monorepo. Base documental: 6 de noviembre de 2026.

## 1. Contrato y forma de trabajo

Implementar `Requerimientos_retiro_seguro_estudiantes.md` siguiendo el backlog de `PLAN.md`. Los requisitos definen el comportamiento; este archivo define cómo trabajar; el plan define orden, validación y entrega. Las instrucciones explícitas más recientes del usuario prevalecen.

Avanzar con incrementos pequeños, completos y desplegables. No reabrir las decisiones de arquitectura fijadas. Resolver detalles de implementación dentro del contrato y registrar los cambios que afecten comportamiento, API, permisos o persistencia. Preguntar únicamente por datos o decisiones que falten y no puedan obtenerse del repositorio/configuración. Continuar las tareas independientes mientras se concretan.

Cada issue/PR enlaza RF/RFS y CA o AB afectados. Actualizar documentación junto al código. No marcar una tarea, prueba o despliegue como terminado sin evidencia real. Usar datos sintéticos en desarrollo, pruebas, capturas y demos.

## 2. Stack y estructura

- Monorepo en GitHub; ramas cortas, PR y checks requeridos antes de integrar a `main`.
- `apps/backend/`: Python/Django modular, API `/v1`, OIDC/BFF, vistas web con Django templates y workers.
- `apps/mobile/`: React Native con **Expo SDK 56**, flujos separados por rol padre/guardia. Android APK interno como distribución inicial.
- `infra/`: infraestructura y configuración versionadas por entorno; AWS seleccionado (us-east-1); cuenta y recursos aún por configurar. Crédito total máximo: 150 USD.
- `tests/contracts/`: contratos API y compatibilidad entre backend y móvil. Pruebas de dominio junto a cada aplicación.
- `.github/workflows/`: CI, staging, promoción automática, build móvil y verificaciones programadas.
- En la raíz: estos tres documentos, README de arranque y lockfiles/manifiestos correspondientes a cada herramienta.

PostgreSQL administrado, IdP OIDC/MFA, KMS, WORM y outbox se mantienen. Un backend modular y una BD transaccional para el retiro; API/web/workers pueden ejecutar procesos distintos desde la misma imagen versionada. No introducir un frontend web separado ni microservicios para repartir la transacción.

Fijar versiones compatibles y lockfiles. Usar la versión de React Native y módulos compatibles con SDK 56; no cambiar de SDK mayor de manera incidental. Documentar comandos reales de instalación, arranque, migración, lint y pruebas en README al crearlos. CI usa esos mismos comandos.

## 3. Invariantes del producto

1. Roles humanos exactos: `PADRE`, `GUARDIA`, `ADMIN_ESCUELA`, `ADMIN_SISTEMA`. Sin superadministrador funcional ni Django Admin público. Cuidador sin cuenta/app.
2. Solo el padre principal por estudiante crea cuidadores y autoriza/gestiona QR; los secundarios consultan y reciben avisos. La escuela verifica vínculos; el equipo técnico ejecuta bulk, provisioning, cambios e incidencias mediante herramientas privadas auditadas.
3. La activación usa invitación aleatoria de un solo uso a contacto precargado verificado y la identidad OIDC. No asignar hijos por datos que el usuario escribe.
4. Backend autoriza cada operación por rol, escuela/sede, vínculo, principal, objeto, vigencia y estado. Claims del IdP o valores del cliente no conceden permisos por sí solos.
5. QR de 256 bits CSPRNG; guardar hash SHA-256. Sin PII, token en URL, logs o telemetría. `issued_at` difiere de `valid_from`; vigencia de 15 min limitada por horario/autorización y anticipación máxima 24 h. Renovar no extiende plazo.
6. Un token utilizable por episodio; una confirmación única transaccional. Escanear no consume ni autoriza definitivamente. Confirmar requiere tres comprobaciones presenciales.
7. Locks ordenados, revalidación dentro de la transacción, restricciones únicas e idempotencia ligada al actor/cuerpo. Revocación y cambio de principal participan en el mismo orden de concurrencia.
8. Sin conexión, certeza o evidencia protegida, no se habilita la entrega. No modo offline, caché de autorización ni bypass de supervisor.
9. Persistir consumo, decisión, evento y outbox juntos. Archivar fuera de locks SQL; recibo WORM verificado en máximo 5 s para habilitar, permiso visible 30 s. Timeout fija incidencia; archivo tardío no autoriza. Aplicar exactamente la máquina de estados de requisitos §6.
10. Reportar el resultado físico añade un evento. Notificar entrega solo desde el reporte físico con evidencia protegida. Fallos posteriores conservan el hecho, generan alerta/reintento y no reactivan el QR.
11. Evidencia append-only: ningún humano crea/edita/borra registros arbitrarios. Las correcciones son eventos nuevos vinculados. Sesiones, outbox y proyecciones mutables se almacenan por separado.
12. El administrador escolar solo lee salidas de su escuela; abrir su sesión exige evento de acceso protegido. El administrador de sistema solo lee accesos escolares y no accede a menores, cuidadores o salidas.

## 4. Seguridad de implementación

OIDC móvil con PKCE S256/navegador del sistema; web con sesión Django, cookies HttpOnly/Secure/SameSite y CSRF. MFA en todos los roles; tokens/sesiones, reautenticación y límites conforme a requisitos. Revocación online. Secretos fuera del código/bundle; almacenamiento seguro del dispositivo para credenciales móviles persistentes. No tokens web en localStorage ni caché persistente de expedientes/fotos.

PostgreSQL real con RLS habilitado/forzado; contexto de escuela derivado por servidor y acotado a la transacción. Runtime sin propiedad de tablas, SUPERUSER, BYPASSRLS o DDL. Credenciales separadas para negocio, consultas, importación, escritura de evidencia, archivo, avisos y migraciones. Funciones privilegiadas estrechas, `search_path` fijo, nombres cualificados y EXECUTE restringido. No INSERT libre a evidencia, cascadas de borrado ni limpiezas genéricas de eventos.

Verificar versión exacta WORM, retención y hash; anclar manifiestos independientes y proteger claves durante toda la retención. No considerar suficiente una cadena de hashes editable en la BD. No inventar plazos de conservación ni sustituir WORM real por un mock en la aceptación del entorno.

UTC y zona IANA de sede. Reloj no confiable bloquea nuevas decisiones. TLS público 1.3, certificados verificados, KMS y copias cifradas. Validar entradas y archivos, reencodificar fotos, parametrizar SQL y escapar salida web. Redactar secretos/QR/documentos completos de logs y reportes de fallos.

## 5. Pruebas y definición de terminado

Ejecutar pruebas pertinentes al cambio y checks requeridos; usar PostgreSQL con roles runtime para transacciones, RLS y restricciones. Unitarias pueden simular adaptadores; staging debe validar IdP/KMS/WORM de ensayo reales. Cubrir casos positivos y negativos de roles/escuelas/familias, límites temporales, replay, 50 confirmaciones concurrentes, revocación concurrente y respuesta perdida.

Para evidencia/sesiones, probar mutación denegada, pérdida/retardo de archivo, portal sin log, duplicación de callback, correcciones y manifiesto divergente. Para recuperación, demostrar que un backup anterior no reactiva una salida. Para avisos, comprobar destinatarios derivados y ausencia de avisos falsos.

Un incremento terminado incluye contrato/API actualizado, migración compatible si aplica, implementación, pruebas relevantes, observabilidad mínima y resultado verificable en staging cuando el destino esté configurado. Al entregar, indicar qué cambió, pruebas ejecutadas y fallos/bloqueos concretos. No afirmar que las casillas pendientes ya están implementadas.

## 6. Integración y despliegue continuo

Producción automática después de staging y checks: no añadir aprobación manual rutinaria de promoción. El pipeline aplica los controles de `PLAN.md`, publica artefactos por commit/digest y serializa migraciones/despliegues por entorno. No ejecutar código de forks con secretos ni credenciales de producción. Permisos mínimos de GitHub Actions y credenciales efímeras OIDC al proveedor.

Mantener API compatible con APK instalados y migraciones expand/contract. Revertir código compatible; no revertir evidencia ni restaurar BD como rollback de una versión. No cancelar migraciones en ejecución por la llegada de otro commit. Un destino sin configurar debe informarse como bloqueado, nunca como despliegue exitoso.

La distribución móvil genera APK firmado para usuarios internos; publicar un APK no lo instala en los teléfonos. La disponibilidad de una nueva versión no justifica romper la API para los binarios aún soportados. Proteger claves de firma y limitar acceso a artefactos.

Desplegar código no implica importar estudiantes ni enviar invitaciones o avisos reales. La activación de una escuela utiliza el lote y destinatarios verificados y las políticas de datos configuradas. Separar esos comandos operativos de la publicación rutinaria de software.
