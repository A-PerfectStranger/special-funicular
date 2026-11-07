# PLAN.md — Implementación y despliegue continuo

Proyecto: Aplicación Segura de Rastreo / retiro seguro de estudiantes. Base de ejecución: 6 de noviembre de 2026.

Este plan transforma los requisitos en incrementos implementables. Todas las tareas comienzan pendientes: este documento no acredita código, infraestructura ni despliegues existentes. Contrato funcional: `Requerimientos_retiro_seguro_estudiantes.md`. Reglas del repositorio: `AGENTS.md`.

## 1. Configuración de trabajo fijada

| Área | Configuración |
| --- | --- |
| Código | Monorepo en GitHub; ramas cortas y PR a `main`. |
| Móvil | Expo SDK 56 / React Native; una base de código con flujos padre/guardia; Android APK interno inicial. |
| Web | Django templates, sesión/BFF de Django y CSRF. |
| Backend | Django modular, PostgreSQL, OIDC/MFA, workers/outbox, KMS y WORM. |
| Integración | GitHub Actions, checks obligatorios y artefactos vinculados al commit. |
| Promoción | Staging y pruebas automáticas antes de producción automática, sin aprobación manual rutinaria. |
| Infraestructura | AWS seleccionado por el usuario; us-east-1, perfil aesir. Destinos aún sin aprovisionar; crédito total máximo 150 USD. |
| Operaciones escolares | Escuela verifica los datos; equipo técnico ejecuta bulk, provisioning, bajas y cambios urgentes. |

Se puede empezar repositorio, dominio, API, móvil y CI con datos sintéticos. La falta de proveedor impide conectar el destino real de despliegue y validar sus controles; no impide avanzar en esas tareas. Los adaptadores locales deben identificarse como simulaciones y nunca activarse en producción.

## 2. Estructura y arranque del repositorio

| Ruta | Entregable |
| --- | --- |
| `apps/backend/` | Django, módulos de dominio, API, templates, migraciones y comandos privados. |
| `apps/mobile/` | Expo SDK 56, TypeScript, navegación por rol y configuración Android. |
| `tests/contracts/` | OpenAPI, compatibilidad de clientes y pruebas compartidas del contrato. |
| `infra/` | Infraestructura versionada, variables por entorno y políticas de IAM/red/retención. |
| `.github/workflows/` | CI, CD backend, build APK y ensayos programados. |
| `docs/runbooks/` | Despliegue, rollback, importación, incidentes y recuperación. |
| Raíz | Requisitos, AGENTS, PLAN y README con comandos reales y configuración de desarrollo. |

Crear `.env.example` sin secretos, lockfiles, fixtures sintéticos y arranque reproducible con PostgreSQL. Seleccionar y fijar versiones soportadas de Python/Django compatibles con dependencias; mantener SDK 56 y sus versiones compatibles de React Native. Crear comandos reales para instalar, arrancar, migrar, lint, typecheck y ejecutar suites. Documentarlos al implementarlos; no dar por existentes comandos que todavía no se han creado.

## 3. Backlog en orden de dependencia

Cada entrega incluye implementación y pruebas de sus controles; la seguridad se desarrolla junto al flujo. Integrar a `main` incrementos pequeños, manteniendo rutas incompletas inaccesibles o deshabilitadas en servidor. No habilitar retiros reales con un flujo parcial.

### E0 — Base y pipeline inicial

- [ ] Inicializar monorepo, estructura, dependencias fijadas, configuración sintética y README de arranque.
- [ ] Crear aplicación Django, templates base, esqueleto móvil y health/readiness sin datos sensibles.
- [ ] Implementar CI de lint/typecheck, unitarias, integración PostgreSQL, secretos y dependencias.
- [ ] Construir imagen del backend/worker, guardar digest y generar APK de desarrollo interno.
- [ ] Crear estructura de CD y validación obligatoria de configuración; conectar staging cuando exista proveedor.

**Aceptación:** un checkout limpio ejecuta los comandos documentados y CI; artefactos llevan SHA. Sin destino, el estado de deploy es bloqueado/no configurado y no se publica un éxito ficticio.

### E1 — Identidad, aislamiento y base de evidencia

- [ ] Implementar cuatro roles, OIDC/MFA móvil/web, sesiones, reautenticación y revocación online.
- [ ] Crear escuelas, estudiantes, padres, vínculos y restricciones de principal único.
- [ ] Configurar RLS y credenciales separadas; probar conexión reutilizada y límites por escuela/familia.
- [ ] Implementar eventos canónicos, funciones de escritura restringidas, outbox y worker de archivo.
- [ ] Conectar WORM/KMS de ensayo, recibos por versión, manifiestos y verificador externo.
- [ ] Registrar login escolar protegido antes de abrir sesión; pantalla de accesos para admin. sistema sin datos de menores.

**Aceptación:** AT02, AT04 y parte correspondiente de AT05/AT06; acceso cruzado y mutación denegados; portal bloqueado ante evidencia no protegida. La falta del proveedor deja pendientes los ensayos reales de adaptadores, no se reemplazan por un aprobado con mocks.

### E2 — Bulk, activación y autorización familiar

- [ ] Crear importador privado: staging, esquema, hash, aprobación escolar, promoción atómica e idempotencia.
- [ ] Crear provisioning/baja y cambios de principal auditados para el equipo técnico.
- [ ] Implementar invitación 256 bits/24 h, contacto verificado y asociación OIDC `issuer`/`sub`.
- [ ] Mostrar estudiantes propios y capacidades por vínculo en móvil.
- [ ] Crear cuidador, autorizaciones, recurrencias, restricciones de horario y revocación.

**Aceptación:** AT01 y casos relevantes AT02/AT04; ninguna asignación por datos declarados; lote incorrecto sin activación parcial; secundario sin capacidad de autorizar; cambios sensibles invalidan tokens.

### E3 — QR y retiro completo

- [ ] Implementar emisión/renovación/reprogramación y fórmula temporal del QR.
- [ ] Implementar escáner y resolución mínima del guardia; tres verificaciones explícitas.
- [ ] Implementar locks, confirmación única, idempotencia, consumo/evento/outbox atómicos y consulta por ID.
- [ ] Conectar recibo WORM oportuno, timeout 5 s, habilitación 30 s y estados de incidencia durables.
- [ ] Reportar entrega/no entrega por evento nuevo y reconciliar respuesta perdida/reporte tardío.

**Aceptación:** AT03, AT05 y AT07; 50 confirmaciones concurrentes producen una decisión; revocación ordenada; QR viejo o fuera de vigencia rechazado; archivo tardío no habilita; sin modo offline ni éxito visual falso.

### E4 — Avisos y consulta escolar

- [ ] Implementar worker de notificación, destinatarios derivados, deduplicación, reintentos y callbacks autenticados.
- [ ] Avisar desde reporte físico protegido; mensajes externos genéricos y estados de envío honestos.
- [ ] Crear consulta paginada de salidas/incidencias en Django templates por escuela.
- [ ] Implementar correcciones mediante comandos técnicos restringidos que añaden eventos vinculados.
- [ ] Completar vistas mínimas del padre y accesos escolares del admin. sistema.

**Aceptación:** AT02/AT05/AT07; no aviso por escaneo o decisión pendiente; ninguna duplicación lógica de salida/aviso; los administradores carecen de CRUD y acceso lateral.

### E5 — Operación real y primera distribución

- [ ] Completar ensayos AT01–AT08 y todos los CA-F/CA-S con resultados vinculados a commit.
- [ ] Medir carga, archivo, notificación y RTO; ensayar caída DB/IdP/WORM/push/reloj y recuperación desde backup antiguo.
- [ ] Verificar permisos reales, retención, claves, alertas, reconciliación y restauración con datos sintéticos.
- [ ] Probar APK en dispositivos Android del equipo, cámara, permisos, retorno de OIDC, bloqueo, actualización y red intermitente.
- [ ] Ejecutar ensayo presencial del flujo con personal y datos sintéticos, sin confundirlo con entrega real de un estudiante.
- [ ] Completar configuración productiva y publicar primera versión por el pipeline automático.
- [ ] Incorporar la escuela mediante lote verificado y activar el uso real al cumplir todos los criterios del MVP.

**Aceptación:** artefactos reproducibles, SHA/digest/APK identificables, cero defectos críticos de permisos/retiro/evidencia, runbooks ejecutables y datos operativos configurados. El despliegue de software puede preceder a la carga de datos reales; las rutas de retiro permanecen deshabilitadas mientras falten sus controles.

## 4. Pipeline de integración

| Disparador | Trabajo requerido | Resultado |
| --- | --- | --- |
| Pull request | Lint, typecheck, unitarias, contratos, migraciones, PostgreSQL/RLS, pruebas negativas y escaneo de secretos/dependencias. | Checks del PR y reportes por commit; sin acceso a secretos de producción. |
| Cambio en retiro/evidencia/permisos | Además: concurrencia, replay, revocación, idempotencia, archivo fallido/tardío y aislamiento. | Impide integrar una regresión de seguridad. |
| Integración en `main` | Repetir checks requeridos del commit integrado y construir artefactos inmutables. | Imagen por digest, lista de dependencias y manifiesto de release. |
| Candidato en staging | Migraciones, smoke tests y suites de integración con servicios de ensayo. | Evidencia necesaria para promoción. |
| Ejecución programada | Restauración/reconciliación, carga y revisión de dependencias/deriva de infraestructura. | Alerta y issue ante regresión; estas pruebas también se ejecutan antes de una release que afecte esa área. |

Los cambios solo documentales pueden omitir builds/deploys si el filtro de rutas es verificable. Fallos de seguridad, contrato, migración o integración bloquean promoción. No permitir excepciones silenciosas ni checks simulados. Para la primera activación real se exige la suite completa; después cada release ejecuta la regresión base y las pruebas adicionales de su impacto.

Seguridad de GitHub Actions: `GITHUB_TOKEN` con permisos mínimos por job, acciones fijadas por SHA y secretos por entorno. No ejecutar código de forks con secretos ni mediante un `pull_request_target` privilegiado. La identidad OIDC de despliegue se restringe a repositorio, rama/entorno y audiencia esperados; usar credenciales temporales del proveedor. La identidad de despliegue no se entrega a API/workers.

## 5. Despliegue continuo del backend y la web

API, Django templates y workers se publican desde la misma revisión. Construir una imagen una vez y promover su **mismo digest** entre staging y producción; la configuración se inyecta por entorno.

1. Validar configuración del destino y permisos; resolver artefacto por digest y verificar correspondencia con el commit aprobado por CI.
2. Obtener exclusión mutua del despliegue de staging. Ejecutar migraciones compatibles una sola vez con identidad separada; iniciar servicios y workers.
3. Ejecutar readiness, smoke tests de roles, sesión escolar auditada, retiro sintético completo, negativa de permisos e integridad de evidencia. Usar IdP/KMS/WORM de ensayo y notificaciones dirigidas solo al equipo.
4. Si todos los checks pasan, promover automáticamente a producción. No añadir revisores obligatorios de entorno para esta promoción rutinaria.
5. Bajo bloqueo de despliegue productivo, comprobar que el candidato no ha sido superado por una versión ya publicada. Ejecutar migración compatible, desplegar imagen y revisar salud.
6. Registrar commit, digest, esquema, fecha y resultado. Ejecutar sondas productivas no invasivas; cualquier prueba con eventos usa un tenant sintético separado, conserva su evidencia y jamás notifica a familias reales.
7. Si falla validación/migración/staging, detener promoción. Si falla salud después del despliegue, revertir al digest compatible anterior; si la reversión no es segura, bloquear la función afectada y ejecutar corrección hacia delante.

Serializar despliegues y migraciones por entorno; `cancel-in-progress: false` en producción. La exclusión de GitHub Actions no garantiza orden por antigüedad del commit: comprobar la ascendencia/revisión desplegada bajo el bloqueo y descartar candidatos obsoletos. Una release con dependencias entre backend y móvil publica primero la API compatible; no habilita una función móvil hasta disponer de backend seguro.

Crear `/health/live` para proceso y `/health/ready` para preparación del servicio sin exponer secretos. Separar disponibilidad técnica de la capacidad de autorizar retiros: si DB/reloj/evidencia no permiten operar con seguridad, la aplicación bloquea ese flujo aunque otras consultas sigan disponibles. Monitorizar esa capacidad explícitamente.

## 6. Migraciones, compatibilidad y rollback

- Usar expand/contract: añadir esquema compatible, desplegar código que soporte transición, ejecutar backfill idempotente y retirar estructuras solo cuando ninguna versión soportada dependa de ellas.
- Probar migraciones desde el esquema anterior y lectura por las versiones que puedan coexistir. Backfills no reescriben eventos históricos; nuevas interpretaciones viven en proyecciones/eventos nuevos.
- Una identidad temporal realiza migraciones; runtime no tiene DDL. No ejecutar migraciones al arrancar cada réplica.
- Un error de migración impide desplegar el resto; registrar estado y reparar mediante migración hacia delante. No cancelar a mitad para atender un nuevo commit.
- El rollback rutinario cambia el artefacto de aplicación compatible. Nunca borra evidencia, baja esquema automáticamente ni restaura un backup para revertir código.
- Mantener API `/v1` y contratos compatibles con los APK soportados. Para una retirada de compatibilidad, implementar respuesta explícita de actualización requerida y un despliegue coordinado; no asumir que todos actualizan al publicar el APK.

Runbook de recuperación: suspender nuevos retiros, restaurar entorno, invalidar tokens anteriores al epoch, reconciliar WORM/manifiestos/proyecciones y reabrir únicamente sin discrepancias. Objetivo RTO 30 min, validado con simulacro. Separar esta recuperación de desastres del rollback de una release.

## 7. Build y distribución móvil continua

Configurar Expo/EAS Build para **APK Android interno** firmado. Perfiles de staging y producción con endpoints/configuración distintos; package ID de staging separado para evitar confusión. Mantener identidad de firma estable de producción y proteger su keystore. Nunca incluir secretos de backend ni credenciales cloud en variables incorporadas al bundle.

Cada cambio móvil integrado ejecuta typecheck, pruebas y build; registrar commit, versiones, runtime, checksum y ubicación privada del APK. Antes de distribuir producción, probar el candidato con el backend de staging y verificar que la configuración del APK productivo apunta al entorno correcto. Los builds de staging/producción tienen configuración distinta y, por tanto, sus checksums se registran por separado; no afirmar que son el mismo binario.

Automatizar la publicación interna de APK aprobados por checks a usuarios autorizados. Restringir acceso a los enlaces de distribución: un enlace compartible no equivale a distribución privada por sí solo. Publicación no equivale a instalación; medir las versiones activas sin PII y mantener compatibilidad con clientes soportados.

El mecanismo inicial de actualización es nuevo APK interno. Si se habilita EAS Update posteriormente, agregar primero validación de `runtimeVersion`, canales separados y pruebas de compatibilidad; cambios nativos, SDK, permisos o módulos requieren un nuevo binario. No utilizar OTA para saltarse las pruebas o la compatibilidad de la release.

## 8. Observabilidad y respuesta operativa

Métricas: latencia/errores por operación, rechazos por permisos/ventana, replay y conflictos, tiempo de archivo, backlog/edad de outbox, entrega pendiente, estado de avisos, errores de login auditado y discrepancias del verificador. Identificadores de correlación internos sin QR, credenciales, fotos ni documentos completos.

Alertar inmediatamente ante evidencia divergente, autorización inesperada o acceso cruzado; suspender el flujo afectado y preservar hechos. Alertar por archivo fuera de plazo, agotamiento de reintentos, degradación de reloj y trabajos pendientes. El equipo técnico atiende, comunica a la escuela por su canal operativo y reconcilia con eventos nuevos.

Crear runbooks con comandos reales para alta/baja, importación, revocación urgente, incidencia de entrega, fallo WORM/IdP, rollback y recuperación. La escuela verifica y aprueba datos/cambios; el equipo técnico los ejecuta. Registrar ejecutor, motivo, alcance y resultado sin convertir esos procesos en CRUD de los administradores de aplicación.

## 9. Datos necesarios para conectar los entornos

Estos valores completan la configuración; no reabren la arquitectura. No inventarlos en código ni considerar que las casillas vacías están resueltas.

| Dato pendiente | Quién lo aporta / efecto |
| --- | --- |
| URL `organización/repositorio` y accesos GitHub | Equipo técnico; permite alojar código y activar Actions. |
| Proveedor, cuenta/proyecto, región y presupuesto operativo | Equipo técnico con responsable del proyecto; habilita IaC y destinos de staging/producción. AWS elegido; cuenta autenticada y recursos aún pendientes. |
| Dominio, DNS y certificados | Equipo técnico; URLs API/web y callbacks OIDC reales. |
| IdP, tenant, issuer, client IDs y métodos MFA | Equipo técnico; configuración de autenticación, enrolamiento y recuperación. |
| PostgreSQL, WORM, KMS y políticas de retención por categoría | Equipo técnico configura; institución define plazos. Sin plazos no cargar datos reales ni fijar retención productiva irreversible por omisión. |
| Cuenta/proyecto Expo, package ID y custodia de firma | Equipo técnico; build firmado y acceso a APK internos. |
| Proveedor/configuración push y destinatarios de ensayo | Equipo técnico; pruebas sin avisar a familias reales. |
| Contacto técnico de guardia y canal escolar urgente | Equipo técnico/escuela; ejecución concreta de escalamiento y reconciliación. |
| Primera sede, zona IANA, ventanas, restricciones y lote validado | Escuela entrega; equipo técnico carga cuando los controles del MVP estén operativos. |

Implementar validación de estas variables y de los permisos reales por entorno. Permitir CI/build sin proveedor; el job de deploy debe detenerse con diagnóstico claro si falta destino. La falta de datos de una escuela bloquea su activación, no las entregas de software con datos sintéticos.

## 10. Referencias de implementación

Consultar documentación oficial al escribir los workflows y configuración, manteniendo los contratos de este plan:

- [GitHub Actions: OIDC](https://docs.github.com/en/actions/concepts/security/openid-connect).
- [GitHub Actions: concurrencia de workflows y jobs](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).
- [Expo: distribución interna](https://docs.expo.dev/build/internal-distribution/).
- [Expo: runtime y compatibilidad de actualizaciones](https://docs.expo.dev/eas-update/runtime-versions/).
