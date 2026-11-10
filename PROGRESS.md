# Continuidad E2 / E3

**E2 aceptada en staging sintético.** Estado conservado por instrucción explícita
del usuario; PLAN contiene criterios y fases. Evidencia por SHA en Actions y
anclas/recibos privados fuera del repositorio. No copiar reportes ni secretos.

## Base funcional acreditada

- SHA `1a16b85fcc7f8ac25d268c308c1ccf9451c667b1` (PR #16–#21 integradas).
- CI [42543919847](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42543919847)
  aprobado: 245 Python, 20 JavaScript móvil/vendor, siete staging (4 Chromium y
  3 recuperación), tipos/contratos/migraciones, seguridad, imagen/APK/firma.
- CD [42544785382](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42544785382):
  publish/prepare/migrate/staging, E1 browser/cloud/archive-drill/APK y
  e2-acceptance/family aprobados. Solo producción falla por NOT_CONFIGURED E5;
  no afirmar que el pipeline productivo o el MVP real estén aceptados.
- Digest runtime API/archivador contrastado:
  `sha256:3aa74250b1bfe778e2ed8d601e845124087d30ef603bf712e9004d5fafde44eb`.
- Cohorte `52cb10c3-9494-5893-bd8a-ce52d8c11ba3`: mínimo familiar 614;
  WORM independiente verificó 615 eventos sin SQL. Se comprobó SHA y que difiere
  de la cohorte `85885f69-3c08-581f-adb0-a297198314e2` del ensayo 74297b3
  [42529491296](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42529491296),
  aprobado con mínimo 489 y WORM 490. El pool permite repetir en otro release
  sin resetear cuentas, invitaciones ni evidencia.

## Alcance terminado

Importación privada con esquema/bytes/hash/aprobación/promoción atómica e
idempotente; una familia por escuela, incluso entre promociones concurrentes.
Invitaciones 256 bits/24 h, contacto firmado/verificado, OIDC/PKCE/MFA y binding
issuer/sub exclusivo. Consulta familiar/capacidades, cuidador/foto normalizada,
recurrencia finita IANA, horarios/restricciones/revocación y operaciones técnicas
auditadas. SQL/RLS y roles separados; principal anterior/secundario denegados;
baja y cambios sensibles invalidan sesiones/versiones. Contrato, cliente SDK 56,
CLI y runbook integrados. Galería conserva formulario solo bajo máscara y exige
check online al volver; logout/rechazo/segundo plano ordinario lo descartan.

Los fallos previos del control guardia y migración se clasificaron por operador:
TaskFailedToStart sin inicio/exitCode (migración: CannotPullContainerError), sin
SQL ejecutado. `isolated_task.py` permite un único reintento de no arranque
probado, con mismos definición/red/inputs; no reintenta SQL, ejecución incierta,
error de creación ni código 42. Segundo fallo bloquea. Diagnóstico conserva la
primera fase y publica solo categorías saneadas. Límites MFA y access <240000ms
no se relajaron. El CD acreditado completó migración y todas las aserciones.

## Continuación y límites

1. El cierre documental no añade comportamiento funcional. Para comprobar su
   integración, consultar el CI/CD de su SHA en Actions y exigir E1/E2/WORM con
   otra cohorte. No avanzar main durante migración/archive-drill. Tras ese gate,
   E3 se desarrolla según el estado vigente al final de este archivo y PLAN.
2. No crear un bucle de commits solo para registrar el último resultado: la base
   funcional aceptada y sus runs están arriba; releases posteriores se consultan
   por SHA en Actions. No atribuirles automáticamente esta aceptación.
3. El operador preparó cuatro cohortes; las dos acreditadas arriba ya se usaron.
   El CD del cierre documental consume otra: consultar las ejecuciones posteriores
   antes de contar disponibilidad. No resetear las previas. Ante agotamiento
   preparar pool nuevo según runbook; CI no crea Cognito ni escribe el vault.
4. No repetir commission_e1 ni pedir códigos/contraseñas/semillas. No editar
   migraciones 0002–0005 ya aplicadas ni ejecutar refresh antiguos de work/.
5. E3–E5 siguen pendientes: QR/retiro, avisos, validación Android física,
   retención institucional/firma/distribución y producción. pickup_enabled=false;
   solo sintéticos. No hay importaciones/invitaciones/mensajes reales enviados.

Scratch y reportes saneados en work/, ignorados. Git conserva fuentes/estado,
Actions los checks y la custodia privada las anclas y versiones WORM.


## Continuación E3 vigente

**E3 NO está aceptada.** Este estado documental se conserva en un borrador;
no integrarlo ni avanzar main hasta concluir la aceptación del candidato funcional.
La base integrada por PR #23–#26 es `3a65293b3e59956cb7f48cd64802d17a64995b93`.
[CI 42750238114](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42750238114)
aprobó 318 Python, 24 móvil + 2 vendor JS, diez navegador/recuperación/diagnóstico,
tipos/lint/migraciones/Expo, seguridad, imagen y APK (cámara, sin micrófono,
firma de desarrollo v2). `make check` y las diez regresiones también pasaron
localmente en la misma fuente. No ejecutar refresh SQL antiguos de work/.

E3 incluye episodio estudiante/fecha local, QR/hash/versiones, decisión/outbox,
recibo/sweep, reloj S3, reporte físico vinculado y SDK 56. Producción/uso real
continúan bloqueados. El ensayo E2/E3 comparte una cohorte de un solo uso y añade
ocho estudiantes sintéticos. Los builds no acreditan cámara física ni AWS.

## Infraestructura comprobada y bloqueo actual

El operador confirmó que la retirada programada eliminó el gateway anterior:
DescribeExpressGatewayService devolvió ResourceNotFoundException. El stack E1
conservaba el callback del host retirado. La recuperación de PR #26 distingue
esta ausencia de una denegación, evita la dependencia circular y muestra motivos
fijos/códigos AWS saneados en lugar del error genérico.

[CD 42751425748](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42751425748)
aprobó publish/prepare/migrate y recreó realmente la puerta stateless. El reporte
staging-deployment del SHA funcional comprobó digest runtime, TLS y ocho sondas;
E1/E2/E3 están false, archive_task null, origin_sync_required true y passed false.
El job staging `129617817768` falló deliberadamente con GATEWAY_BOOTSTRAP_ONLY
antes de E1/E2/E3. No confundir este resultado técnico con aceptación funcional.

- Origen observado: `https://re-b70d4a26db5e4e5892df797d3fec4467.ecs.us-east-1.on.aws`.
- Digest del candidato: `sha256:776d30f68c4374d858db47fb2e3341fa323a8b30e525bb0b6404bfc83ccf3901`.
- La ventana de retirada sigue acotada. No borrar cuentas, base, eventos ni WORM.
- `base_url` es una pista; ensayos y APK reciben el origen verificado mediante
  STAGING_RELEASE_ORIGIN. No editar el hostname por cada recreación.

El operador recibió el comando del checkout limpio main aprobado para ejecutar
`python3 -m scripts.sync_staging_origin --sha 3a65293b3e59956cb7f48cd64802d17a64995b93`.
La salida de sincronización todavía está pendiente; no afirmar que AWS fue
actualizado. El helper obtiene el hostname del servicio revisado, comprueba task
SHA y tag ECR inmutable y solo ejecuta un change set de WebClient.CallbackURLs
sin reemplazo, conservando otros parámetros/outputs. No accede al vault ni
provisiona identidades, SQL, IAM, claves o retención. No repetir commission_e1 ni
pedir contraseñas/TOTP/códigos. Procedimiento completo en runbook deployment.
Esta sesión carece de identidad AWS de operador; el escritorio no inicializó y
la acción debe realizarse desde CloudShell del operador.

## Pasos necesarios para cerrar E3

1. Obtener salida verificable del helper. Si bloquea, usar su categoría saneada y
   consultas privadas mínimas; no reintentar a ciegas ni modificar evidencia.
2. Reejecutar solo staging `129617817768` del CD anterior, con main todavía en
   `3a65293`. No repetir publish/migrate aprobados ni introducir otro SHA.
3. Exigir staging digest/TLS/callback, E1 browser/cloud/archive-drill/APK y
   E2/E3/lector WORM independiente hasta la secuencia final. Esas pruebas de
   puerta AWS aún no se ejecutaron; no cerrar casillas por existencia de código.
4. Verificar cohorte disponible con el selector real. Los CD fallidos previos no
   consumieron E2; no deducir disponibilidad de esa afirmación. Si el pool se
   agotó, operador prepara otro según E2, sin resetear canjes ni identidades.
5. Solo tras todos los gates, revisar los seis criterios de PLAN y convertir este
   borrador en cierre documental con SHA/digest/runs/secuencias reales. Exigir
   calidad y filtro docs-only verificable para evitar otro despliegue/cohorte.

E4 mantiene avisos/correcciones; E5, Android físico, recuperación integral, carga,
retención institucional/firma/distribución y producción. Scratch saneado en work/,
ignorado; fuentes/estado en Git, reportes por SHA en Actions y anclas privadas
fuera del repositorio. No publicar QR, credenciales, fotos o copias privadas WORM.
