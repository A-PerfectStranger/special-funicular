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


## Trabajo E3 vigente

PR #23–#25 integradas; main funcional `c31dbcc4b933bf633354ad492164f0f10c1fbdd1`.
[CI 42584549657](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42584549657)
aprobó 304 Python, 24 móvil + 2 vendor JS, diez navegador/recuperación/diagnóstico,
tipos/lint/migraciones/Expo, seguridad, imagen y APK con cámara, sin micrófono,
firma de desarrollo v2. Migración limpia y ocho expiraciones de sesión durante
locks verificadas. No ejecutar refresh SQL antiguos de work/.

E3 implementa episodio estudiante/fecha local, QR/hash/versiones, decisión/outbox,
recibo/sweep, reloj S3, reporte físico vinculado y SDK 56. Producción/uso real
continúan bloqueados. El ensayo E2/E3 comparte una cohorte de un solo uso y añade
ocho estudiantes sintéticos independientes. E3 NO está aceptada: no atribuir a
mocks, builds o salud un resultado de Cognito/KMS/WORM o Android físico.

[CD 42578747692](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42578747692)
del b423949 aprobó staging/digest/TLS, WORM cloud y APK. E1 browser usó un hostname
retirado y falló antes del proveedor; E2/E3 no corrieron. La sonda
[42581925936](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42581925936)
aisló DNS y [42582862978](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42582862978)
llegó al formulario IdP con el hostname activo, sin credenciales ni login.
[CD 42585734865](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42585734865)
del c31dbcc aprobó publish/prepare/migrate y bloqueó la discrepancia de callback.
Estos intentos no consumieron una cohorte E2. No contar su disponibilidad por
suposición; el selector real debe verificarla sin resetear historial.

El operador intentó sincronizar; el mensaje genérico ocultó el motivo. Sus dos
consultas de solo lectura confirmaron servicio `ResourceNotFoundException`
y stack E1 UPDATE_COMPLETE con el origen anterior `re-dc7939bf752047ff8947f600b81bc157`.
La retirada acotada eliminó la puerta; no hay sincronización de callback acreditada.
No reejecutar `commission_e1`, restaurar cuentas ni pedir contraseñas/TOTP/códigos.

Corrección en `feat/e3-origin-recovery`: reconocer ausencia específica, recuperar
una puerta stateless sin E1/E2/E3, dejar el gate bloqueado y conservar evidencia;
operador sincroniza solo WebClient.CallbackURLs del servicio/candidato observado,
con change set estrecho sin reemplazo y outputs persistentes iguales. Después
reintentar staging del mismo SHA. Los ensayos y APK reciben el origen verificado
por CD; `base_url` queda como pista de arranque. Diagnósticos con categorías fijas.
Pruebas pertinentes locales: 41 Python aprobadas y tipos completos; suite global,
PR/CI/main e infraestructura real de esta corrección aún en verificación.

Siguiente paso: completar checks/PR, integrar y observar bootstrap real; dar al
operador el SHA main aprobado para el comando acotado del runbook deployment.
Verificar su actualización real y reintentar staging sin avanzar main; exigir
E1 browser/cloud/archive-drill/APK, E2/E3 y WORM independiente. Solo después
cerrar los seis criterios de PLAN y el estado documental, mediante diff solo docs
verificado. No declarar E3 completa mientras esos gates falten. Scratch saneado
en work/, ignorado; fuentes/estado en Git, reportes por SHA en Actions y anclas
privadas fuera del repositorio. Esta sesión no tiene identidad AWS de operador;
el escritorio no pudo inicializarse y la actualización depende del operador.
