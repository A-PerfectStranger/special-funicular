# Continuidad E3

PLAN contiene la aceptación y el backlog; este archivo conserva el estado real
para continuar. Las evidencias por commit están en Actions; anclas, recibos y
snapshots privados permanecen fuera del repositorio. No copiar secretos/reportes.

## Estado vigente

E0/E1/E2 están aceptadas con datos sintéticos según las referencias de PLAN.
**E3 todavía no está aceptada.** Implementación integrada por PR #23–#26 y #28;
base funcional actual `3592c40f830cb27b7ccd94b99b77ca6acdd653fb`.
[CI 42757851196](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42757851196)
aprobó 322 Python con PostgreSQL/roles reales, 24 móvil + 2 vendor JavaScript,
diez navegador/recuperación/diagnóstico, tipos/lint/migraciones/Expo, auditorías,
secretos, imagen y APK (cámara, sin micrófono, firma de desarrollo v2).

E3 incluye episodio estudiante/fecha local, QR/hash/versiones, decisión y outbox
atómicos, recibo/sweep, reloj S3, reporte físico vinculado y móvil SDK 56.
El ensayo E2/E3 comparte una cohorte de un solo uso y añade ocho estudiantes
sintéticos independientes. Producción y uso real continúan bloqueados.

## Infraestructura y aceptación en curso

La retirada programada eliminó el gateway anterior y dejó su callback registrado.
La recuperación integrada distingue ausencia específica de errores de permisos,
crea una puerta stateless, exige task SHA/digest y permite al operador cambiar
solo WebClient.CallbackURLs mediante change set sin reemplazo. El operador
confirmó la sincronización y el CD verificó posteriormente el login real.
`base_url` es una pista: ensayos y APK reciben STAGING_RELEASE_ORIGIN verificado.
No editar el hostname por cada recreación ni repetir commission_e1.

[CD 42751425748](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42751425748)
del candidato anterior 3a65293 aprobó staging/digest/TLS/callback, E1 browser,
cloud y archive-drill. El APK compiló y pasó permisos, pero su verificador usaba
la pista retirada. E2/E3 quedaron omitidas y no consumieron cohorte en ese run.
PR #28 corrigió el verificador para exigir el origen de release tanto en entorno
como en el bundle real, conservando paquete/callback; cuatro regresiones cubren
origen obsoleto y ejecución por módulo. E3 renueva sesiones interactivas después
de esperar valid_from sin ampliar MFA/idle ni límites del servidor.

[CD 42758935625](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42758935625)
verificó 3592c40: migración, staging/digest/TLS/callback/nueve sondas, E1 browser,
cloud, archive-drill/recuperación y APK staging con origen/paquete/callback,
cámara/sin micrófono/firma v2 aprobados. Digest runtime:
`sha256:48246ca90b8e043328e658ff3946568b1ec3d59247cc8a52f11ac525169e32cb`.
APK staging SHA-256:
`169376f5a7691b794ef0bd28f3dcc168638158433f5349d87a3dd33305b43d24`.
El lector independiente inicial verificó 806 eventos sin SQL; archive-drill
verificó hasta 815, incluido el intento tardío 810 que siguió denegado.

**Bloqueo actual:** E2 falló en `audit_anchor`, tras aprobar sus seis grupos de
activación, capacidades, cuidadores/revocación, cambio de principal, restricción
y baja técnica. Reporte `passed=false`, `minimum_sequence=849`, `failure_kind=unknown`.
E3 y lector WORM final fueron omitidos. No considerar esos seis grupos una nueva
aceptación E2 ni acreditar E3. Cohorte consumida:
`9b874f2c-740f-59de-a22d-0d33c91a1bf7`; no reutilizarla.
El selector encontró tres cohortes con salida 42 y reservó la cuarta con salida 0;
el pool actual está consumido. Un TaskFailedToStart/CannotPull anterior se
reintentó una vez sin ejecución y luego devolvió 42; no explica por sí solo el
fallo posterior de audit_anchor.

El reporte no distingue entre el control privado original-principal, el login
posterior y la mutación final. Se solicitó al operador una consulta ECS de solo
lectura (tiempos/stopCode/exitCodes, sin variables ni credenciales) para identificar
la tarea fallida. Esta sesión no tiene identidad AWS de operador. No reintentar
la cohorte ni restablecer cuentas/evidencia para ocultar el fallo. El run terminó;
no queda migración ni archive-drill activo. Main permanece en 3592c40.

## Próximos pasos obligatorios

1. Obtener el diagnóstico ECS solicitado y distinguir tarea privada/login/mutación
   del ancla final. Si hace falta, consultar logs privados limitados; no publicar
   variables de tareas, secretos ni errores con códigos OAuth.
2. Corregir la causa demostrada y el diagnóstico insuficiente; probar localmente
   y exigir PR/CI antes de main. Mantener sin cambios límites MFA/archivo/SQL y
   no editar migraciones E2 aplicadas. Si el fallo es externo, documentar prueba.
3. El pool fue consumido: preparar otro mediante operador según runbook E2, con
   identidades nuevas, sin reset de canjes/eventos. Solicitar el comando concreto
   cuando exista candidato main aprobado para repetir los gates.
4. Exigir todos los gates del candidato: E1/APK, E2, nueve controles E3 y lector
   independiente hasta máximo minimum_sequence. Reportes de protocolo con
   e2_accepted/e3_accepted=false no equivalen por sí solos a aceptación global.
5. Solo tras esos gates, cerrar las seis filas E3 de PLAN con SHA/digest/runs y
   secuencias reales. PR #27 sigue borrador; su diff frente al main funcional
   será exclusivamente documentación permitida. Exigir calidad y filtro docs-only
   antes de integrar para no consumir otra cohorte por el cierre documental.

## Reglas de continuidad y límites

- Nunca borrar/reiniciar cuentas, invitaciones, estudiantes, eventos, outbox,
  recibos ni WORM para repetir. No editar migraciones E2 0002–0005 aplicadas.
  No ejecutar refresh SQL antiguos de work/ ni pedir contraseñas/TOTP/códigos.
- Las suites repetidas alcanzaron el límite deliberado del snapshot sintético
  local original (5000 eventos/8 MB). No se borró ni amplió: una BD local aislada
  retenida pasó las 322 pruebas. .env conserva la BD original; para otra suite,
  consultar work/e3-apk-isolated-db.txt y work/e3_verify_apk_isolated.py, sin
  publicar credenciales ni ejecutar limpiezas. CI usa PostgreSQL limpio y pasó.
- pickup_enabled=false del contrato anterior se mantiene. Solo el endpoint E3
  separado anuncia synthetic_only=true; ninguna capacidad/health concede entrega.
- E4 conserva avisos/consultas/correcciones. E5 conserva Android físico, cámara y
  retorno OIDC nativo, recuperación integral/epoch/carga/RTO, retención
  institucional, firma/distribución y producción NOT_CONFIGURED.
- No se enviaron importaciones, invitaciones ni mensajes reales. Un APK firmado
  en desarrollo y el protocolo compartido no prueban instalación/cámara física.
- No crear commits en bucle para registrar cada nuevo SHA documental. Distinguir
  base funcional aceptada de revisión documental; releases posteriores se
  consultan por SHA en Actions. Scratch saneado en work/, ignorado.
