# Requerimientos del producto — Retiro seguro de estudiantes

Base de implementación · 6 de noviembre de 2026 · Proyecto: Aplicación Segura de Rastreo.

Este archivo define comportamiento, permisos, contratos y aceptación del producto. `AGENTS.md` rige la implementación y `PLAN.md` ordena el trabajo y el despliegue continuo. Las decisiones de arquitectura aquí indicadas están fijadas; los valores de conexión de cada entorno se configuran al aprovisionarlo.

## 1. Producto y arquitectura fijada

El MVP permite autorizar el retiro escolar, presentar un QR, verificar presencialmente a estudiante y retirador, registrar el resultado y notificar a la familia. El cuidador presenta QR y cédula física; no tiene cuenta ni aplicación. No incluye GPS, seguimiento de trayectos ni reconocimiento facial.

| Componente | Implementación |
| --- | --- |
| Repositorio | Monorepo en GitHub. |
| Aplicación padre/guardia | React Native con Expo SDK 56; dependencias compatibles fijadas en lockfile. Primera distribución: APK Android interno. |
| Web de administradores | Django templates, sesión del lado servidor, cookies protegidas y CSRF. |
| Backend | Python/Django modular, API `/v1`, BFF de identidad web y servicios de dominio compartidos con las vistas web. |
| Persistencia | PostgreSQL administrado, transacciones, restricciones, RLS y copias con recuperación a un instante. |
| Identidad | IdP administrado OIDC y MFA para los cuatro roles. |
| Evidencia | Eventos append-only, archivo WORM independiente, manifiestos verificables y claves KMS. |
| Procesamiento | Workers de archivo y notificaciones; outbox transaccional y reintentos idempotentes. |
| Despliegue | GitHub Actions: CI → staging → pruebas → producción automática. AWS seleccionado el 7 de noviembre de 2026; región us-east-1 y techo total de créditos 150 USD. Staging sintético E0/E1 verificado; producción pendiente E5. |

La escuela verifica vínculos, contactos, restricciones y horarios antes de entregarlos. El equipo técnico del proyecto ejecuta bulk, altas/bajas de personal, cambios de principal, configuración e incidencias urgentes mediante procesos privados auditados. Estas tareas no añaden permisos al administrador de escuela ni al administrador de sistema.

## 2. Roles y permisos

Usar exclusivamente `PADRE`, `GUARDIA`, `ADMIN_ESCUELA`, `ADMIN_SISTEMA`. Denegar por defecto; validar en servidor rol, escuela/sede, vínculo, principal, objeto, vigencia y estado en cada operación. El principal se define por estudiante: exactamente un vínculo activo con capacidad de autorizar. Los secundarios consultan y reciben avisos habilitados.

| Acción | Padre móvil | Guardia móvil | Admin. escuela web | Admin. sistema web | Cuidador sin app |
| --- | --- | --- | --- | --- | --- |
| Activar cuenta por invitación | Sí, propia | Alta técnica controlada | Alta técnica controlada | Alta técnica controlada | No |
| Ver estudiante asignado | Sí, vínculo activo | Solo datos mínimos al resolver QR válido | Solo datos mínimos del registro de salida | No | No |
| Registrar cuidador / autorizar / emitir / revocar QR | Solo padre principal del estudiante | No | No | No | No |
| Escanear/resolver QR | No como guardia | Sí, sede asignada y QR válido | No | No | Solo lo presenta; no consulta |
| Verificar cédula y ambas identidades / confirmar retiro | No | Sí, en presencia física | No | No | Presenta QR y cédula |
| Ver historial de sus estudiantes | Sí, vista familiar mínima | Solo resultado del evento que opera | Sí, salidas de su escuela | No | No |
| Ver accesos de administradores escolares | No | No | No | Sí, todas las escuelas, sin datos de menores | No |
| Crear/editar/borrar registros de salida o acceso | No | No; solo comando de retiro | No | No | No |
| Cargar estudiantes, cambiar vínculos, roles u horarios desde la app | No | No | No | No | No |

Las cuentas de personal son individuales y separadas por rol; no se acumulan permisos de padre, guardia y administrador en una misma sesión. Una persona con más de una función utiliza identidades de personal separadas para el MVP. La cuenta PADRE puede tener varios estudiantes, con capacidad principal distinta por vínculo.

## 3. Requerimientos funcionales

Cada criterio debe tener una prueba vinculada a su ID. Los registros históricos los escribe el sistema: los humanos pueden leer únicamente las proyecciones permitidas y ejecutar comandos de negocio, nunca crear, editar o eliminar evidencia arbitraria.

| ID | Comportamiento | Criterio de aceptación |
| --- | --- | --- |
| RF01 | Importar estudiantes y padres en bulk validado por escuela. | CA-F01: lote correcto se promueve completo; duplicado idéntico es idempotente; error referencial no activa ninguna fila del lote. |
| RF02 | Asignar vínculos precargados al padre que active invitación y contacto verificado. | CA-F02: invitación correcta asigna solo los hijos previstos; invitación ajena, usada o vencida no asigna ninguno ni revela existencia de otros. |
| RF03 | Padre consulta estudiantes vinculados y su historial mínimo. | CA-F03: dos familias no leen datos entre sí; un padre secundario puede consultar, pero no autorizar. |
| RF04 | Padre principal registra/actualiza cuidador con nombre, documento y foto, sin cuenta para cuidador. | CA-F04: faltan datos → no autorización; cambio sensible revoca tokens asociados; no se exige instalar app al cuidador. |
| RF05 | Padre principal autoriza por fecha o recurrencia y revoca antes del retiro. | CA-F05: secundario y administradores no pueden autorizar; recurrencia no crea un QR permanente; revocación bloquea tokens programados y vigentes. |
| RF06 | Aplicar horarios y restricciones escolares cargados por proceso técnico aprobado. | CA-F06: selección fuera de ventana o con bloqueo se rechaza; ninguna app permite ampliar el horario escolar. |
| RF07 | Emitir y compartir QR antes de su hora de inicio, sin datos personales. | CA-F07: emisión 08:00/inicio 13:00/fin 13:15: rechazo 12:59:59, aceptación 13:00 y 13:14:59, rechazo 13:15; igual con móvil en otra zona horaria. |
| RF08 | Renovar/reprogramar o revocar sin reactivar tokens previos. | CA-F08: nuevo token invalida anterior atómicamente; regenerar a las 13:10 no cambia vencimiento 13:15; reprogramar fuera de ventana falla. |
| RF09 | Guardia obtiene datos mínimos al escanear QR válido de su sede. | CA-F09: antes del inicio, tras vencimiento o desde otra sede no hay datos; administrador de sistema no puede usar este endpoint. |
| RF10 | Guardia verifica estudiante, cuidador y cédula física; confirma/rechaza. | CA-F10: tres comprobaciones requeridas; 50 solicitudes concurrentes crean una única confirmación; respuesta ambigua no autoriza físicamente; entregado/no entregado se reporta mediante evento nuevo idempotente. |
| RF11 | Notificar el reporte de entrega física a los padres vinculados habilitados, diferenciando confirmación digital e incidencia. | CA-F11: el sistema determina destinatarios; aviso externo no contiene datos del menor; escaneo, confirmación pendiente y no entrega no producen aviso de retiro; un reporte físico duplicado no duplica el aviso lógico. |
| RF12 | Mantener reintentos y estados honestos de notificación. | CA-F12: fallo y recuperación del proveedor no duplican el evento de salida; nunca se afirma leído por ausencia de error. |
| RF13 | Administrador de escuela consulta registros inmutables de salidas propias. | CA-F13: filtros por fecha/estudiante paginados dentro de su escuela; API de escritura de registros inexistente; acceso cruzado denegado. |
| RF14 | Provisionar personal, roles, principal y revocaciones mediante proceso técnico controlado. | CA-F14: ninguna de las cuatro apps cambia roles; baja técnica corta sesiones y operaciones activas; el administrador de sistema no se autopromueve. |
| RF15 | Suspender y escalar ante fallo de validación/conexión o identidad. | CA-F15: no hay validación offline, autorización por caché ni bypass manual dentro de la app. |
| RF16 | Registrar cada nueva sesión de administrador escolar automáticamente. | CA-F16: tres logins distintos generan tres eventos; refresh y doble callback del mismo login no duplican el evento; fallo de persistencia impide abrir la sesión. |
| RF17 | Administrador de sistema consulta solo registros de acceso escolar. | CA-F17: ve actor escolar, escuela, fecha y resultado, pero no foto, estudiante, cuidador ni salidas; filtros paginados y lectura auditada. |
| RF18 | Corregir inconsistencias históricas mediante eventos nuevos del sistema. | CA-F18: una corrección conserva bytes/ID del evento previo y referencia `supersedes_event_id` o `related_event_id`; no hay edición libre por ningún rol. |
| RF19 | Ofrecer resultado idempotente y reconciliar fallos de entrega/archivo. | CA-F19: tras respuesta perdida se consulta el mismo ID; sin decisión cierta no se entrega; la recuperación no reabre una salida ni reutiliza el QR. |

## 4. Requerimientos de seguridad

| ID | Control a implementar | Criterio de aceptación |
| --- | --- | --- |
| RFS01 | Autenticar todas las operaciones protegidas; MFA en los cuatro roles; enrolamiento y recuperación sin saltarse el vínculo. | CA-S01: no hay acceso anónimo a datos o QR; cambio de cuenta/recuperación no asigna hijos nuevos. |
| RFS02 | RBAC con atributos de escuela/sede/vínculo/principal/estado y defensa adicional RLS; denegar por defecto. | CA-S02: matriz de permisos completa en API e imágenes, dos escuelas/dos familias, cero accesos ajenos. |
| RFS03 | Atributos de rol/vínculo/horario solo por procesos técnicos aprobados; autorización solo por padre principal. | CA-S03: manipular claims/cuerpo no cambia rol ni principal; revocación efectiva en la siguiente operación. |
| RFS04 | QR opaco de 256 bits CSPRNG; guardar hash SHA-256, no token en logs, URLs ni telemetría. | CA-S04: decodificar no revela PII; revisar código del generador y 10 000 tokens inválidos, sin presentar esa muestra como prueba de entropía. |
| RFS05 | Consumo y confirmación atómicos; idempotencia y unicidad por salida incluso con tokens distintos. | CA-S05: 50 confirmaciones desde dos guardias generan una confirmación y un consumo efectivo; después de un único reporte físico, generan un aviso lógico por destinatario. |
| RFS06 | Validar `valid_from`/`expires_at` con reloj de servidor, autorización y vínculo actuales. | CA-S06: probar antes/inicio/fin, cambio de reloj, renovación y revocación concurrente con orden de commit definido. |
| RFS07 | En puntos de entrada del backend: 5 fallos por cuenta/origen en 15 minutos → bloqueo de ese punto 15 minutos. IdP Cognito: bloqueo exponencial nativo tras 5 fallos, inicialmente 1 s y hasta aproximadamente 15 min; diferencia autorizada el 7 de noviembre de 2026. Impedir enumeración y exigir MFA reciente para cambios sensibles. | CA-S07: probar umbral/recuperación del backend y el comportamiento nativo del IdP, sin presentar ambos como idénticos; sin bloqueo global ilimitado por IP atacante. |
| RFS08 | Access token máximo 5 minutos, sesión revocable; inactividad guardia 5 min, web 15 min, padre 15 min. Cierre invalida refresh. | CA-S08: tokens firmados aún no vencidos no evitan la baja de rol/cuenta validada online; no persistir tokens web en localStorage. |
| RFS09 | TLS 1.3 en acceso público; TLS autenticado en servicios; validar certificados, emisor/audiencia y callbacks. | CA-S09: canal inválido detiene acceso; no secretos ni PII en texto claro. |
| RFS10 | Cifrar almacenamiento y backups con claves KMS separadas por función; negar claves a roles de negocio; proteger claves por toda la retención. | CA-S10: copia sin claves no revela datos; rotación y restauración verificadas; destruir una clave no puede destruir evidencia aún retenida. |
| RFS11 | Crear auditoría por eventos del sistema: accesos, cambios, importaciones, QR, lecturas sensibles, salidas, correcciones, fallos, inicio/parada de auditoría. | CA-S11: actor real, hora, escuela, resultado y correlación; sin QR, credencial, foto o documento completo. |
| RFS12 | Registros append-only desde commit: sin UPDATE/DELETE/TRUNCATE/DDL en ejecución; archivo WORM y consultas según tipo/rol. | CA-S12: todos los roles humanos y credenciales de ejecución fallan al mutar; comprobar bytes/versiones protegidas y detección de huecos. |
| RFS13 | Fallar sin autorizar ante incertidumbre, DB/auditoría caída, reloj no confiable o evidencia no protegida. | CA-S13: inyectar fallos en cada paso de §6, sin éxito visual falso, pérdida silenciosa ni QR reactivado. |
| RFS14 | Minimizar datos en pantallas, caché, historial, notificaciones e imágenes; admin. sistema no ve menores. | CA-S14: inspeccionar respuestas y almacenamiento cliente; fotos solo autenticadas, `no-store`; no URLs públicas permanentes. |
| RFS15 | Validar entradas y archivos, consultas parametrizadas, límites y reencodificación de imagen; defensa CSRF en web con cookies. | CA-S15: inyección, XSS, archivos activos y rutas manipuladas no ejecutan código ni alteran permisos. |
| RFS16 | Limitar por actor/origen emisión, escaneo y cargas; no omitir seguridad al saturar. | CA-S16: 30 escaneos/min por guardia con ráfaga 10 como valor inicial; excesos se rechazan y miden, sin bloquear toda una escuela por una sola cuenta. |
| RFS17 | Retención explícita por categoría, sin borrado manual de eventos; ciclo automático al vencer únicamente según política aprobada. | CA-S17: datos sintéticos demuestran retención/borrado permitido, respaldo y ausencia de purga de evidencias vigentes. Activación de datos reales bloqueada sin plazos configurados; desarrollo y despliegue técnico con datos sintéticos pueden continuar. |
| RFS18 | Outbox transaccional, destinatario derivado del vínculo y callbacks autenticados; entrega de avisos al menos una vez con deduplicación. | CA-S18: callback falso/duplicado no crea salida; fallo push no reabre el retiro; un duplicado externo no se presenta como otra salida. |
| RFS19 | Invitación de un solo uso ligada al padre/contacto precargado y al IdP; TTL 24 h, revocable, sin autoasignación por cédula. | CA-S19: replay, contacto distinto y enlace filtrado sin control del contacto no vinculan estudiantes. |
| RFS20 | Importación aislada, autenticada, versionada e idempotente; mínimo privilegio y revisión previa. | CA-S20: lote adulterado, cruce de escuela, doble principal o reenvío incompatible se rechaza; rollback no deja vínculos activos parciales. |
| RFS21 | Registrar acceso escolar antes de abrir sesión de portal; admin. sistema sin acceso lateral a salidas. | CA-S21: fallar escritura impide sesión; renovar token no duplica ingreso; cuenta de admin. sistema no lee tablas ni endpoints de menores. |
| RFS22 | Separar identidad técnica de negocio, consultas administrativas, importador, escritor y archivador; no credenciales DBA en servicio. | CA-S22: inspección de grants/IAM demuestra ausencia de permisos de mutación sobre evidencia y ausencia de rol universal. |
| RFS23 | Cada corrección es evento nuevo, con autor causal y razón; verificar integridad y secuencia fuera de la BD operativa. | CA-S23: modificación o eliminación simulada en copia de BD se detecta contra archivo/manifiesto independiente; hash aislado sin anclaje externo no cuenta como evidencia suficiente. |
| RFS24 | Recuperación conserva bloqueos y evidencia; invalida tokens previos al punto de recuperación y reconcilia salidas antes de abrir puerta. | CA-S24: restaurar backup anterior a una salida no vuelve a autorizarla; detectar lag/huecos impide reabrir. |

## 5. Flujos y reglas de dominio

### 5.1 Bulk, activación y cambios de vínculo

1. Recibir por canal técnico privado un lote de una escuela, con aprobación escolar, `batch_id`, versión de esquema y hash del contenido.
2. Validar en staging del importador referencias, contactos, duplicados, restricciones y principal único. Un error impide promover todo el lote.
3. Promover mediante transacción. Repetir ID/hash devuelve el resultado original; el mismo ID con otro contenido se rechaza. Auditar ejecutor técnico y aprobación escolar.
4. Emitir invitación aleatoria de 256 bits al contacto precargado y verificado; guardar su hash, caducidad de 24 h y uso/revocación. Nunca enlazar hijos por la mera entrada de cédula, nombre o correo.
5. Canjear con sesión OIDC, MFA y control del contacto; asociar `issuer` + `sub` al padre precargado. El canje y la asignación son transaccionales e idempotentes.
6. Cambios de principal, baja o restricciones invalidan las autorizaciones/tokens pendientes afectados y sesiones pertinentes. El equipo técnico registra el motivo y la aprobación; el historial permanece intacto.

### 5.2 Autorización y QR diferido

El principal registra nombre, documento y foto del cuidador; no almacena una copia completa de su cédula. Autoriza por fecha o recurrencia dentro del horario de sede. Cada episodio de retiro tiene identidad estable y una única confirmación; una recurrencia no crea un QR permanente ni reinicia un episodio cerrado.

Generar 32 bytes CSPRNG codificados en base64url. Guardar SHA-256 como verificador. El token no contiene datos personales ni permisos autosuficientes, y se envía a resolución en el cuerpo de la petición. No incluirlo en URLs, logs, analítica ni crash reports. Compartirlo con el cuidador es la función prevista; el sistema sigue exigiendo verificación presencial.

```text
issued_at = instante de generación
valid_from = instante seleccionado y validado por el servidor
expires_at = min(valid_from + 15 minutos, authorization_end, school_window_end)
aceptable = valid_from <= server_now < expires_at
```

Anticipación máxima: 24 h. Rechazar intervalos vacíos y horarios fuera de ventana. Al renovar, sustituir el token atómicamente sin extender el vencimiento. Reprogramar es un comando explícito que vuelve a validar horario y versiones. Cambio sensible de cuidador, revocación o principal nuevo invalida tokens anteriores. Escanear no consume ni reserva el retiro.

### 5.3 Verificación y decisión de retiro

El guardia de la sede resuelve un QR vigente y ve únicamente los datos necesarios. Comprueba presencialmente estudiante, cuidador y cédula física. Exigir tres confirmaciones explícitas; una discrepancia produce rechazo/incidencia sin permiso de entrega.

Para confirmar, bloquear episodio y filas de vínculo/autorización/token en orden fijo; revalidar identidad, versiones, vigencia y restricciones dentro de la sección crítica. Consumir token, cerrar episodio, insertar `SALIDA_CONFIRMADA` y outbox en una sola transacción. Usar unicidad de confirmación por episodio y clave idempotente ligada a actor, operación y hash de petición.

Misma clave y cuerpo devuelve la operación original; cuerpo distinto produce conflicto. Renovación, cambio de principal y revocación usan el mismo orden de bloqueo. Si la revocación confirma primero, el retiro se deniega; si la decisión de retiro confirma primero, un bloqueo posterior genera incidencia, sin reescribir la historia. Errores de serialización requieren reintentar la transacción completa con límite, nunca conceder permiso por error.

### 5.4 Consultas web y accesos escolares

Django templates presenta las proyecciones de lectura de cada rol. `ADMIN_ESCUELA` consulta salidas de su escuela, incluyendo estados e incidencias; `ADMIN_SISTEMA` consulta accesos escolares sin datos de estudiantes/cuidadores/salidas. Aplicar paginación y límites, sin exportación masiva.

Cada nueva sesión del administrador escolar genera un evento de acceso persistido y protegido antes de abrir el portal. Correlacionar el login y deduplicar callbacks; refresh no es un nuevo ingreso. Registrar fallos sin atribuirlos a una identidad que no se haya verificado. Si no se puede persistir/proteger la evidencia, no se habilita la sesión.

## 6. Evidencia y entrega física

Separar la decisión digital del permiso visible y del reporte físico. El dato `SALIDA_CONFIRMADA` por sí solo no demuestra que el niño fue entregado.

1. Confirmar en PostgreSQL consumo, decisión, evento append-only y outbox.
2. Archivar inmediatamente el evento canónico en WORM, verificar hash, versión exacta y retención, y guardar recibo operativo. No mantener locks SQL mientras se espera a la red.
3. Esperar como máximo 5 s. Solo un recibo verificado dentro de ese plazo habilita la entrega; antes, la UI muestra pendiente y no autoriza entregar.
4. Al vencer el plazo o perder certeza, registrar `ENTREGA_NO_HABILITADA_POR_EVIDENCIA` y fijar incidencia. El token sigue consumido. El archivo tardío repara la evidencia, pero no habilita automáticamente una entrega ni reactiva el token.
5. Recuperar respuestas perdidas por el ID de operación original. La habilitación visible dura 30 s desde su emisión; una pantalla vencida no permite entregar. Al vencer sin actuación, escalar y registrar incidencia.
6. El guardia reporta entregado/no entregado por comando idempotente que añade un evento. El aviso definitivo nace de `ENTREGA_FISICA_REPORTADA`, con evidencia protegida. Si falla el archivo después del hecho físico, conservar el hecho y el trabajo pendiente, alertar y reintentar; nunca afirmar que la entrega física se deshizo.
7. Resolver incidencias mediante eventos nuevos del sistema con motivo y actor causal. Un reporte tardío puede describir un hecho ya ocurrido; no concede permiso para otra entrega.

| Estado operativo | Siguiente transición permitida |
| --- | --- |
| `PENDIENTE_DECISION` | `PENDIENTE_ARCHIVO` tras commit; rechazo/incidencia si no cumple controles. |
| `PENDIENTE_ARCHIVO` | `HABILITADA` con recibo oportuno; `INCIDENCIA` al vencer o fallar. |
| `HABILITADA` | `ENTREGA_REPORTADA` al registrar resultado; `INCIDENCIA` por bloqueo o vencimiento sin actuación. |
| `INCIDENCIA` | Añadir reconciliación o reporte tardío; nunca reactivar el token ni volver a habilitar la entrega. |
| `ENTREGA_REPORTADA` | Consultar y, si procede, añadir corrección vinculada; nunca editar el hecho. |

Las transiciones operativas son durables y serializadas: la carrera entre timeout, recibo, bloqueo y reporte no puede habilitar después de fijar incidencia. No existe transacción distribuida atómica PostgreSQL/WORM. La UI distingue los estados y no convierte errores, timeouts o falta de red en éxito.

Eventos: ID único, tipo, versión de esquema, actor causal, escuela, hora UTC, correlación y snapshot mínimo del hecho. No registrar tokens, fotos o documento completo. Correcciones usan `related_event_id` o `supersedes_event_id` y conservan los bytes originales.

La cuenta runtime no tiene INSERT directo a evidencias ni UPDATE/DELETE/TRUNCATE/DDL. Funciones estrechas del sistema construyen el evento desde contexto validado. Proteger objetos WORM con retención bloqueada y referencia de versión exacta; versionado simple no basta. Firmar/anclar manifiestos fuera de la BD y verificar huecos y divergencias. Separar claves e identidades; impedir que los servicios borren objetos, reduzcan retención o destruyan claves aún necesarias.

Tablas de tokens, sesiones, recibos, outbox, proyecciones y entregas de avisos son operativas y pueden cambiar según reglas. No mezclar su mutabilidad con los eventos. Sin cascadas de borrado hacia evidencia. Retención por categoría configurable antes de datos reales; purga automática únicamente al vencer la política aplicable, nunca edición/borrado manual de registros.

## 7. Implementación del backend y contratos

### 7.1 Módulos y datos

Mantener un backend modular y una BD transaccional para el retiro. Los workers se ejecutan en procesos separados y usan permisos propios.

| Módulo | Responsabilidad y persistencia principal |
| --- | --- |
| `identity` | OIDC, sesiones, MFA, roles, invitaciones y revocación. |
| `school_roster` | Escuelas, estudiantes, padres, vínculos, principal único activo e importaciones. |
| `authorization` | Cuidadores, versiones, autorizaciones, recurrencias, horarios y QR. |
| `pickup` | Episodios, locks, decisión única, idempotencia y reporte físico. |
| `evidence` | `pickup_events`, `school_access_events`, `security_events`, canonización y verificador. |
| `school_read` | Proyección de salidas por escuela; credencial de lectura limitada. |
| `system_read` | Proyección de accesos escolares; credencial sin acceso a menores. |
| `archive_worker` | Outbox de archivo, WORM, manifiestos y `archive_receipts`. |
| `notification_worker` | Outbox de avisos y `notification_delivery` por evento/destinatario. |

Restricciones de BD: referencias por escuela, índice parcial de principal activo único, hash único de token/invitación, episodio estable, confirmación única por episodio, lote ID/hash y deduplicación `(event_id, destination, purpose)` para efectos. Los workers toleran reinicio después de un efecto externo sin duplicar el efecto lógico.

PostgreSQL privado; habilitar y forzar RLS. Contexto de escuela derivado por servidor y aplicado únicamente dentro de la transacción, sin fuga entre conexiones reutilizadas. Cuentas runtime sin propiedad de tablas, `SUPERUSER`, `BYPASSRLS` o DDL. Queries parametrizadas. Si se usa `SECURITY DEFINER`: propietario no-login dedicado, `search_path` fijo, nombres cualificados y EXECUTE revocado a PUBLIC. Probar sus límites con credenciales reales de ejecución. Separar negocio, lectores, importador, escritor, archivador, notificador y migraciones; no credencial universal.

### 7.2 Identidad y clientes

Móvil: OIDC Authorization Code con PKCE S256 mediante navegador del sistema. Web: sesión BFF de Django con cookie HttpOnly/Secure/SameSite y protección CSRF. Validar firma, emisor, audiencia, tiempos, estado y nonce/correlación. Los claims externos no conceden roles ni vínculos por sí solos.

MFA para todos; reautenticación de antigüedad máxima 5 min para cambios sensibles de cuidador, autorizaciones/horarios y recuperación. Access token máximo 5 min; inactividad guardia 5 min y padre/web 15 min. Logout revoca refresh; baja, rol o principal se comprueban online. Tokens móviles persistentes solo en almacenamiento seguro del dispositivo; sin secretos de cliente embebidos ni tokens web en localStorage. Limpiar sesión y datos transitorios al cerrar sesión. Fotos autenticadas con `no-store`, sin URLs públicas permanentes ni caché de expedientes.

### 7.3 API mínima

| Contrato conceptual | Actor y control |
| --- | --- |
| `POST /v1/activation/redeem` | Padre autenticado en IdP; invitación y contacto verificado; no devuelve datos antes de canje válido. |
| `GET /v1/me/students` y `/v1/me/pickups` | PADRE, únicamente vínculos propios y vista mínima. |
| `POST /v1/caregivers`, `POST /v1/authorizations` | PADRE principal, objeto propio, reautenticación reciente. Actualizar/revocar mediante comandos específicos auditados. |
| `POST /v1/authorizations/{id}/issue-qr`, `/revoke`, `/reschedule` | PADRE principal; ventanas, versiones y lock de evento; fechas derivadas/validadas por servidor. |
| `POST /v1/guard/resolve-qr` | GUARDIA de sede; token en cuerpo, sin cache, límites; no consume. |
| `POST /v1/guard/confirm-pickup` | GUARDIA; tres comprobaciones, idempotencia, transacción y estado de evidencia. |
| `GET /v1/guard/operations/{id}` | Mismo guardia/sede autorizada; consulta de resultado, sin iniciar otro retiro. |
| `POST /v1/guard/operations/{id}/report-handover` | GUARDIA de la operación; resultado entregado/no entregado, evidencia nueva y aviso apropiado; no modifica el registro. |
| `GET /v1/school/pickup-records` | ADMIN_ESCUELA, filtro obligatorio de escuela derivado de sesión y paginación. |
| `GET /v1/system/school-access-records` | ADMIN_SISTEMA, proyección sin PII de menores. |
| Callback OIDC / callbacks de proveedores | Origen y mensaje validados, correlación/idempotencia y protección contra replay; sin confiar en payload libre. |

No exponer CRUD de evidencias, roles o estudiantes, autoasignación de hijos ni exportaciones masivas. Los comandos de negocio construyen los eventos en servidor. La web con Django templates usa estos mismos servicios de autorización y consulta; no implementa un segundo conjunto de reglas.

Publicar OpenAPI versionado y DTOs mínimos. Usar códigos HTTP coherentes: 401 sin sesión válida, 403 fuera de permisos y 409 por conflicto de idempotencia/estado; evitar revelar existencia de objetos ajenos. La respuesta de operación incluye `operation_id`, estado y expiración de habilitación del servidor. Los errores y estados pendientes nunca se representan como autorización. En móvil conservar solo el ID necesario para consultar una respuesta perdida, sin almacenar el QR ni el expediente como permiso offline.

### 7.4 Infraestructura y configuración

Contenedores sin privilegios; BD y almacenamiento privados; entrada pública TLS 1.3; canales internos autenticados; secretos administrados; KMS, copias/PITR y entornos aislados. Cifrado administrado de datos/backups. Si se cifra explícitamente un campo/objeto en aplicación, usar AES-256-GCM con nonces únicos y metadatos autenticados mediante biblioteca mantenida. Documentar el algoritmo/tamaño real del servicio KMS para firma de manifiestos, rotación y recuperación; nunca implementar criptografía propia.

UTC para instantes, zona IANA de sede para mostrar/seleccionar horarios. Reloj no confiable bloquea nuevas decisiones. Logs redactados y métricas sin PII. Servicios de producción no contienen credenciales de migración/importación. La región, endpoints, IDs de recursos y política de retención se suministran por entorno; falta de configuración crítica impide arrancar la función afectada de manera segura.

## 8. Casos de abuso convertidos en regresiones

Implementar estas pruebas en el mismo backlog de la función que protegen. Conservar IDs para asociarlas a issues y resultados; AB19 queda fuera del catálogo ejecutable porque el producto no usa GPS.

| Caso | Estímulo de prueba | Resultado/control verificable |
| --- | --- | --- |
| AB01 | Cuidador/tercero recibe QR y lo decodifica o consulta públicamente. | RFS02/04/14, CA-S04: solo token, cero datos sin guardia autorizado. |
| AB02 | Padre o admin. escuela cambia ID/escuela en petición. | RFS02/22, CA-S02: API/imagenes/RLS rechazan; ninguna escritura ajena. |
| AB03 | Tercero inventa o enumera tokens. | RFS04/16, CA-S04/16: impredecibilidad por diseño, límites, ningún dato/permiso. |
| AB04 | Cuidador repite un QR usado o lo asocia a otro niño. | RFS05, CA-S05: rechazo, evento y salida única. |
| AB05 | Dos guardias confirman a la vez, incluso con códigos viejo/nuevo. | RFS05/06, CA-S05: 50 concurrencias, una confirmación y token consumido una vez. |
| AB06 | Revocación o cambio de principal entre escaneo y confirmación. | RFS03/06, CA-S06: revocación que confirma primero impide retiro; resultado posterior es incidente, no reescritura. |
| AB07 | Atacante cambia reloj o presenta QR antes de `valid_from`. | RFS06, CA-F07/S06: servidor rechaza y no muestra fotos antes del inicio. |
| AB08 | Persona roba QR y se presenta como cuidador. | RF10, CA-F10: comprobar ambas personas y cédula; discrepancia bloquea. Residual: engaño/colusión humana. |
| AB09 | Atacante toma cuenta del padre o su recuperación. | RFS01/07/19, CA-S07/19: MFA y recuperación verificada sin cambiar vínculos; cambio sensible reautenticado. |
| AB10 | Admin. sistema intenta convertirse en superusuario o leer salidas. | RFS02/03/22, CA-S02/22: proyección/credencial exclusiva para accesos escolares, sin datos de menores. |
| AB11 | Tercero usa móvil de guardia o sesión de cuenta dada de baja. | RFS08/14: expiración/revocación en servidor, sin caché de expedientes ni modo offline. |
| AB12 | Atacante intercepta canal o falsifica callback IdP/push. | RFS09/18/21: emisor/certificado/correlación verificados; replay no abre sesión ni crea eventos falsos. |
| AB13 | Padre carga foto activa o texto con inyección. | RFS15: reencodificación, límites, consultas parametrizadas y salida escapada. |
| AB14 | Administrador o servicio intenta UPDATE/DELETE/TRUNCATE de registros. | RFS12/22/23: permisos denegados; objeto WORM/versión original verificable. |
| AB15 | Saturación o caída para forzar «autorizar igual». | RFS13/16: pendiente/escalamiento, nunca aprobación por defecto. |
| AB16 | Manipular destinatario o buscar foto pública/notificación detallada. | RFS14/18: destinatarios derivados, URLs protegidas, aviso genérico. |
| AB17 | Restaurar backup anterior o repetir petición tras timeout. | RFS05/24, CA-S24: reconciliación WORM, invalidación de tokens antiguos y bloqueo de reapertura. |
| AB18 | Persona usa cédula/email ajeno o invitación filtrada para vincular hijo. | RFS19/20: contacto verificado y precarga exacta; sin autoasignación por datos públicos. |
| AB20 | Operador introduce lote adulterado o cambia principal de otra escuela. | RFS20: staging, hash, aprobación, tenant, principal único, rollback de lote y evento. |
| AB21 | Admin. escuela intenta ingresar sin dejar rastro; duplica callback. | RFS21: sesión exige evento protegido; deduplicación por login real, no por IP. |
| AB22 | Privilegio de BD reescribe eventos/hashes o sustituye «última versión». | RFS12/23: comprobar manifiesto/versiones externas; incidente ante divergencia. El verificador externo detecta la alteración aunque se hayan cambiado los hashes locales. |
| AB23 | Worker falla después de consumir token, pero antes de archivo/notificación. | RFS13/18/24: outbox durable, pendiente sin entrega, archivo idempotente y reconciliación. |
| AB24 | Padre secundario o principal anterior intenta autorizar tras cambio. | RF05/RFS03: capacidad por vínculo y versión activa; cambio revoca todos los tokens pendientes. |
| AB25 | Privilegiado intenta destruir clave KMS o reducir retención para borrar evidencia. | RFS10/12/17: separación, política de protección de claves y retención; ensayo de denegación y recuperación en entorno sintético. |

## 9. Aceptación y operación

| Suite | Cobertura | Evidencia |
| --- | --- | --- |
| AT01 Bulk/activación | RF01–RF03/RF14, RFS19/20, AB18/20/24. | Lotes sintéticos, rollback, replay, activación y principal único. |
| AT02 Matriz de roles | RF03/09/13/17, RFS01–03/14/22, AB01/02/10/16. | Casos allow/deny de cada endpoint y proyección, escuelas/familias cruzadas. |
| AT03 QR diferido | RF05–RF08, RFS04–06, AB03–07. | Límites inicio/fin, 24 h anticipación, reprogramación y 50 confirmaciones simultáneas. |
| AT04 Identidad/sesión | RFS01/07/08/19, AB08/09/11/18. | MFA, recuperación, invitación, revocación y tres comprobaciones físicas. |
| AT05 Evidencia | RF16–RF19, RFS11–13/21–23, AB14/21–23/25. | Escritura restringida, permisos directos, WORM real sintético, correcciones y fallo de archivo. |
| AT06 Canal/entradas/claves | RFS09/10/15/17, AB12/13/25. | Configuración y pruebas de canal, uploads, KMS y retención. |
| AT07 Avisos y operación | RF10–RF12/RF15/RF19, RFS18, AB15/16/23. | Simulación de puerta, reporte físico, reintentos y ausencia de mensajes de entrega falsa. |
| AT08 Recuperación/carga | RFS13/16/24, AB15/17/22. | Restauración, conciliación de eventos y tokens, saturación y mediciones. |

Fixtures: dos escuelas, dos familias por escuela, principal y secundario, padre con varios hijos, dos guardias, cuentas revocadas y todos los estados del QR. Fotografías y documentos sintéticos. Usar PostgreSQL real con roles runtime para RLS/concurrencia. En staging probar adaptadores de IdP, KMS y WORM reales con datos sintéticos; los mocks cubren unitarias, no verifican permisos del proveedor.

| Objetivo | Medición / comportamiento exigido |
| --- | --- |
| Resolución QR | p95 ≤2 s con 20 guardias concurrentes y 5 resoluciones/s durante 15 min. |
| Archivo antes de habilitar | Recibo verificado ≤5 s; timeout pasa a incidencia según §6. |
| Habilitación visible | 30 s; pantalla vencida nunca habilita otro retiro. |
| Aviso al proveedor | p95 ≤30 s tras reporte físico, con servicios disponibles y evidencia protegida. No equivale a recibido/leído. |
| Reintentos de aviso | 30 s, 2 min, 5 min y 15 min; luego alerta y estado pendiente sin inventar recepción. |
| Recuperación | RTO objetivo 30 min, medido mediante simulacro y reconciliación. |

Recuperar desde backup anterior a una salida no puede reactivar su QR. Invalidar tokens anteriores al epoch de recuperación y reconciliar eventos contra WORM/manifiestos antes de reabrir retiros. Demostrar recuperación del evento y sus referencias; un backup periódico no acredita RPO cero.

Una función está terminada cuando cumple sus CA-F/CA-S, sus regresiones de abuso y el flujo integrado correspondiente. La habilitación del MVP con datos reales requiere todos los CA-F01–F19 y CA-S01–S24, pruebas físicas con personal, retención configurada y cero defectos que permitan retiro indebido, acceso cruzado, modificación de evidencia, portal sin log o replay de token. Cada resultado vincula commit, entorno, fecha, esperado y observado. Los controles automáticos de publicación se detallan en `PLAN.md`.
