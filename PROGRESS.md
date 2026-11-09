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

Rama de implementación `feat/e3-pickup`, basada en `2e16bef` tras `git fetch` y
comparación con origin/main (sin divergencia). El CD de esa base
[42550789405](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42550789405)
aprobó staging/E1/E2; solo producción quedó NOT_CONFIGURED. Esa base consumió
otra cohorte; consultar disponibilidad real antes de una repetición.

Implementación nueva: módulo pickup, migraciones aditivas, funciones restringidas,
episodio por estudiante/fecha local, QR/hash/versiones, decisión/outbox, estados
serializados por recibo/sweep, reloj S3 con caducidad, reporte físico vinculado;
API/OpenAPI; emisión/compartir/cámara/tres comprobaciones/recuperación por UUID
en SDK 56. E3 permanece bloqueada en producción. Gate E2/E3 comparte cohorte de
un solo uso y añade estudiantes sintéticos, con control de atraso acotado.

Estado comprobado del candidato integrado `ab2d8fb` (PR #23):
[CI 42573282125](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42573282125)
aprobado, 289 Python, 24 móvil + 2 vendor JS, siete navegador/recuperación,
tipos/lint/migraciones/Expo, bundle Android, seguridad, imagen y APK con cámara
sin micrófono y firma de desarrollo v2. Migración desde base vacía y ocho casos
de sesión vencida durante locks aprobados. No usar refresh SQL antiguos de work/.

[CD 42574527123](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42574527123)
aprobó publish/prepare/migrate y contrastó digest runtime/red/TLS, pero staging
falló: la sonda E0 exigía 404 en la ruta E3 habilitada, que responde correctamente
405 a GET. E1/E2/E3 no se ejecutaron; no se consumió cohorte familiar en ese run.
E3 NO está aceptada. La corrección exige selección explícita de probes E3,
capacidad sintética exacta y negativas para 200/404/flag incoherente; después
requiere nuevo CI/PR y todos los gates AWS. No omitir ni ensayar a mano el gate.

Siguiente paso: integrar la corrección verificada y observar E1/E2/E3/WORM por
SHA. Si falta pool, usar preparación privada de E2, sin resetear cohortes ni
solicitar secretos en chat. Solo después registrar aceptación real y sus límites.
Scratch/resultados saneados en work/, ignorados; no publicar QR, credenciales,
fotos ni copias privadas de WORM.
