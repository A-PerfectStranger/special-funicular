# PLAN.md — Implementación y despliegue continuo

Proyecto: Aplicación Segura de Rastreo / retiro seguro de estudiantes.

Este documento concentra el estado vigente, la aceptación y el trabajo pendiente.
Las casillas completadas requieren evidencia real; una base local o un build no
acreditan despliegue AWS. Los procedimientos futuros describen objetivos, no
funciones ya disponibles. Contrato funcional:
[requisitos](Requerimientos_retiro_seguro_estudiantes.md); reglas de desarrollo:
[AGENTS.md](AGENTS.md); comandos: [README.md](README.md).

E0 y E1 están aceptadas con datos sintéticos. E2–E5 siguen pendientes: no hay
retiros, avisos ni uso con datos reales habilitados. La configuración de
[staging](infra/environments/staging.json) habilita E1/E2 y exige sus gates en CD;
[producción](infra/environments/production.json) permanece sin configurar.
El estado de un despliegue concreto se consulta por commit en
[Actions](https://github.com/A-PerfectStranger/special-funicular/actions), no se
deduce de la aceptación de una entrega ni de una URL temporal.

## 1. Configuración de trabajo fijada

| Área | Configuración |
| --- | --- |
| Código | Monorepo en GitHub; ramas cortas y PR a `main`. |
| Móvil | Expo SDK 56 / React Native; una base de código con flujos padre/guardia; Android APK interno inicial. |
| Web | Django templates, sesión/BFF de Django y CSRF. |
| Backend | Django modular, PostgreSQL, OIDC/MFA, workers/outbox, KMS y WORM. |
| Integración | GitHub Actions, checks obligatorios y artefactos vinculados al commit. |
| Promoción | Staging y pruebas automáticas antes de producción automática, sin aprobación manual rutinaria. |
| Infraestructura | AWS us-east-1; parámetros por entorno en infra/environments y operación/presupuesto en infra/aws/README.md. |
| Operaciones escolares | Escuela verifica los datos; equipo técnico ejecuta bulk, provisioning, bajas y cambios urgentes. |

El desarrollo y CI usan datos sintéticos. Los adaptadores locales deben
identificarse como simulaciones y nunca activarse en producción. La ausencia de
configuración productiva bloquea ese destino, no el desarrollo ni staging.

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

El arranque reproducible, las versiones y los comandos implementados se mantienen
en [README.md](README.md), los manifiestos y lockfiles. Conservar `.env.example`
sin secretos y fixtures sintéticos; mantener SDK 56 y dependencias compatibles.

## 3. Backlog en orden de dependencia

Cada entrega incluye implementación y pruebas de sus controles; la seguridad se desarrolla junto al flujo. Integrar a `main` incrementos pequeños, manteniendo rutas incompletas inaccesibles o deshabilitadas en servidor. No habilitar retiros reales con un flujo parcial.

### E0 — Base y pipeline inicial

- [x] Inicializar monorepo, estructura, dependencias fijadas, configuración sintética y README de arranque.
- [x] Crear aplicación Django, templates base, esqueleto móvil y health/readiness sin datos sensibles.
- [x] Implementar CI de lint/typecheck, unitarias, integración PostgreSQL, secretos y dependencias.
- [x] Construir imagen del backend/worker, guardar digest y generar APK de desarrollo interno (firma de desarrollo; sin distribución productiva).
- [x] Crear estructura de CD y validación obligatoria: destinos incompletos fallan con BLOCKED/NOT_CONFIGURED.
- [x] Conectar identidad OIDC de lectura para GitHub/main y verificar en AWS cuenta, créditos y denegación de acceso ajeno.
- [x] Aprovisionar y verificar staging AWS privado, presupuesto/alertas y CD real con OIDC, roles separados, SHA/digest y probes TLS.

**Aceptación acreditada:** [preflight 42430538070](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42430538070)
y [CD 42433511451](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42433511451).
Publicación OCI, preparación RDS, migración aislada y despliegue/probes reales
aprobados. Estos resultados acreditan la base técnica de E0, no funciones de negocio.

**Aceptación:** un checkout limpio ejecuta los comandos documentados y CI; artefactos llevan SHA. Sin destino, el estado de deploy es bloqueado/no configurado y no se publica un éxito ficticio.

### E1 — Identidad, aislamiento y base de evidencia

- [x] Implementar cuatro roles, OIDC/MFA móvil/web, sesiones, reautenticación y revocación online.
- [x] Crear escuelas, estudiantes, padres, vínculos y restricciones de principal único.
- [x] Configurar RLS y credenciales separadas; probar conexión reutilizada y límites por escuela/familia.
- [x] Implementar eventos canónicos, funciones de escritura restringidas, outbox y worker de archivo.
- [x] Conectar WORM/KMS de ensayo, recibos por versión, manifiestos y verificador externo.
- [x] Registrar login escolar protegido antes de abrir sesión; pantalla de accesos para admin. sistema sin datos de menores.

**Aceptación acreditada:** AT02, AT04 y la parte E1 de AT05/AT06, mediante
[ensayo integrado 42501830048](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42501830048)
y [recuperación independiente 42507955250](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42507955250).
Base funcional ensayada: `0ca43742fd1a5ad77311a64ee522ef932682922d`;
controlador de recuperación: `36954c0`. Estas referencias delimitan la aceptación,
sin afirmar que ese SHA sea el despliegue activo.

| Control | Alcance aceptado y referencia de contrato |
| --- | --- |
| Identidad | OIDC/MFA real de los cuatro roles, BFF web y protocolo móvil compartido, reauth, refresh/replay, logout y baja/restauración online. Recuperación conserva subject y comprueba crecimiento del bloqueo Cognito con cotas de RPC. AT04; RFS01/03/07/08/09/19; AB09/11/12. |
| Vínculos | Aislamiento por escuela/familia y principal único con PostgreSQL real; roster sintético original y vínculos conservados tras recuperación. Bulk e invitaciones siguen en E2. AT02; RF03/14; AB02/10/24. |
| Permisos | RLS ENABLE/FORCE, conexión reutilizada y rollback sin fuga, credenciales separadas, sin propiedad/DDL/BYPASSRLS/SET ROLE del escritor; lector sin menores. Inspección privada contrastada por verificador independiente. AT02/05; RFS02/12/22; AB02/10/14. |
| Archivo | Evento/outbox atómicos, escritura restringida, leases y recibo idempotente. Archivo ausente deniega el portal; archivo tardío no reabre el intento; un login nuevo protegido sí abre. AT05; RFS11/12/13/23; AB14/21/22/23. |
| Integridad externa | WORM COMPLIANCE/KMS sintético, versión/hash/retención y manifiestos firmados, denegaciones efectivas. Verificador sin SQL/Sign/Put acepta copia original y rechaza reescritura con cadena local válida. AT05/06; RFS10/12/17/23; AB22/25. |
| Acceso escolar | Login protegido antes de abrir sesión, deduplicación, cierre ante fallo y consulta mínima paginada del administrador de sistema con lectura auditada. RF16/17; CA-F16/17; RFS14/21/22; AB10/21. |

El límite backend de RFS07 fue medido por separado en
[42456781366](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42456781366),
sobre `5ac4f02`; no se atribuye esa medición a otro candidato. Los reportes
parciales conservan su alcance y `e1_accepted=false`; la aceptación requiere el
conjunto de controles. Las ejecuciones y artefactos por commit se consultan en
Actions; las copias privadas y anclas confiables permanecen fuera del repositorio.

**Límites:** COMPLIANCE siete días solo para evidencia sintética. La prueba del
protocolo móvil y el APK firmado con clave de desarrollo no acreditan instalación,
cámara ni retorno OIDC en Android físico. Retención institucional, distribución
privada, firma productiva y restauración integral del dominio siguen en E5.
Operación y repetición de ensayos: [runbook E1](docs/runbooks/e1.md).

### E2 — Bulk, activación y autorización familiar

Decisión del usuario: una familia pertenece a una sola escuela en este MVP.
El importador debe rechazar la reutilización entre escuelas también cuando
las promociones son concurrentes.

- [ ] Crear importador privado: staging, esquema, hash, aprobación escolar, promoción atómica e idempotencia.
- [ ] Crear provisioning/baja y cambios de principal auditados para el equipo técnico.
- [ ] Implementar invitación 256 bits/24 h, contacto verificado y asociación OIDC `issuer`/`sub`.
- [ ] Mostrar estudiantes propios y capacidades por vínculo en móvil.
- [ ] Crear cuidador, autorizaciones, recurrencias, restricciones de horario y revocación.

**Aceptación:** AT01 y casos relevantes AT02/AT04; ninguna asignación por datos declarados; lote incorrecto sin activación parcial; secundario sin capacidad de autorizar; cambios sensibles invalidan tokens.

**Criterios verificables y ejecución E2:**

1. Importador privado separado del runtime: esquema versionado, validación completa,
   hash de bytes, aprobación escolar vinculada al hash y promoción atómica. Replay
   idéntico conserva resultado; mismo ID con contenido distinto falla. Sin acceso
   desde apps administrativas ni activación parcial ante referencias inválidas.
2. Operaciones técnicas con ejecutor, motivo y aprobación: altas/bajas de personal,
   cambio de principal y restricciones. Invalidación online de sesiones pertinentes
   y versiones/autorizaciones afectadas, con evento/outbox en la misma transacción.
3. Invitación de 32 bytes CSPRNG, hash único y vida de 24 h, un solo uso y revocable.
   Canje con Code/PKCE, nonce, MFA y contacto verificado por IdP que coincide con
   la precarga; asociación exclusiva issuer/sub. Sin enumeración ni autoasignación.
4. API/móvil: estudiantes propios, capacidad por vínculo y aislamiento de familias,
   escuelas y roles. Principal registra/actualiza cuidador completo con foto
   reencodificada; autorizaciones por fecha o recurrencia semanal finita dentro de
   ventanas IANA precargadas. MFA <=5 min en cambios; revocación y actualización
   invalidan versiones anteriores. Sin QR permanente ni retiro habilitado.
5. PostgreSQL real con roles separados, RLS forzada, concurrencia, replay, límites
   temporales, rollback y pruebas negativas. Contrato, tipos, migraciones, seguridad,
   bundle/APK y ensayo integrado de staging por commit antes de acreditar E2.

**Implementación candidata:** modelo/migraciones E2 y comandos SQL con RLS forzada;
`family_ops` privado con esquema/hash/aprobación/promoción; invitaciones y canje
Code/PKCE con email verificado; principal/políticas/baja auditados; API familiar,
fotos reencodificadas y móvil SDK 56; OpenAPI y runbook operativo. El ensayo
`e2-trial.yml` comparte gate E2/WORM con CD y consume cohortes nuevas de un pool
acotado preparado por operador, sin permisos IAM nuevos para CI. El ensayo inicial
[42524078114](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42524078114)
aprobó sobre `3085e36`, incluida regresión E1/APK y evidencia externa. No acredita
las correcciones posteriores ni cierra por sí solo E2.

| Criterio | Verificación local | Verificación AWS |
| --- | --- | --- |
| Lote/hash/aprobación/idempotencia/rollback | PostgreSQL importer real, lote válido/incorrecto y conflicto posterior a staging | Ensayo inicial aprobado; carrera entre escuelas pendiente en AWS |
| Activación/contacto/issuer-sub/uso único | Firma RSA, PKCE y transporte; PostgreSQL, expiración y ocho canjes concurrentes | Ensayo inicial aprobado; scope email y MFA reales preparados; replay ampliado pendiente |
| Roles/familias/principal/sesiones | Dos escuelas, negativos, comandos concurrentes y cambio de principal ordenado | Ensayo inicial aprobado; concurrencia bulk/baja ampliadas pendientes |
| Cuidadores/fotos/autorizaciones/horarios | Reencodificación, recurrencia IANA/DST, revocación y límites de MFA | Protocolo móvil compartido inicial aprobado; recurrencia ampliada pendiente |
| Evidencia/compatibilidad/distribución | Evento/outbox atómicos; migraciones, tipos, contrato y bundle | Imagen/APK/WORM iniciales aprobados; candidato final pendiente |

**Límites actuales:** la rama candidata habilita E2 y su gate obligatorio en CD;
la integración sigue condicionada al ensayo AWS 42529491296. Falta verificar
el cierre de concurrencia y el gate compartido con pool real, después el CD
habitual, antes de cerrar la matriz. QR/permisos de
entrega pertenecen a E3 y no se declaran probados por invalidar autorizaciones.
No se ejecutaron importaciones/invitaciones ni mensajes reales. Procedimiento
CloudShell revisable, sin compartir códigos de verificación: docs/runbooks/e2.md.

Orden: importación/operaciones técnicas → activación → autorización familiar/API/
cliente móvil → regresiones y aceptación del candidato. Estado de ejecución y
continuidad solicitado por el usuario en PROGRESS.md. Las casillas permanecen
pendientes hasta verificar los criterios; E3–E5 permanecen deshabilitadas.

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
| Cuenta/destino productivo y presupuesto operativo | Equipo técnico con responsable del proyecto; staging ya tiene configuración versionada, producción requiere comisión E5. |
| URL productiva, DNS y certificados | Equipo técnico; URLs API/web y callbacks OIDC productivos. Staging usa URL administrada temporal. |
| IdP y clientes productivos, enrolamiento y recuperación MFA | Equipo técnico; Cognito de ensayo no acredita configuración productiva. |
| PostgreSQL, WORM, KMS productivos y retención por categoría | Equipo técnico configura; institución define plazos. Sin plazos no cargar datos reales ni fijar retención productiva irreversible por omisión. |
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
