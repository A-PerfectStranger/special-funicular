# Continuidad E3

PLAN contiene criterios y backlog; Actions conserva los resultados por SHA.
Anclas, snapshots y recibos privados permanecen fuera del repositorio. No copiar
secretos, QR, fotos ni reportes privados a Git. E0/E1/E2 están aceptadas según PLAN.
**E3 NO está aceptada todavía.**

## Candidato y resultados verificados

Base funcional integrada por PR #23–#26 y #28–#30:
`bd8eca2b74356964e23fb41824830a80df72c2f5`.
[CI 42776069649](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42776069649)
aprobó 333 Python con PostgreSQL/roles reales, 24 móvil + 2 vendor JavaScript,
diez navegador/recuperación/diagnóstico, tipos/lint/migraciones/Expo, seguridad,
imagen y APK con cámara, sin micrófono y firma de desarrollo v2.

[CD 42768417415](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42768417415)
aprobó publish/prepare/migrate/staging, digest runtime/TLS/callback/nueve sondas,
E1 browser/cloud/archive-drill/recuperación y APK staging con bundle/origen,
paquete/callback/permisos/firma comprobados. Digest:
`sha256:6926fba996cd8825f07f12cbe4f9974171e81eb719076e31d5975993e666bfef`.
APK SHA-256: `9bd0605b8e096316729a0a29ef9d71a9ec947f7ee9d41d58aafd772253458d3f`.
El lector independiente E1 verificó 894 eventos sin SQL; archive-drill verificó
hasta 903, incluido el intento tardío 898 que siguió denegado.

E2 aprobó los seis grupos y el ancla final audit_anchor_mutation, mínimo 945.
E3 falló en scope_resolution tras aprobar solo before_start_no_data_or_photo,
mínimo 976; el reporte tiene passed=false y e3_accepted=false. WORM final fue
omitido. No acreditar E3 ni atribuir al nuevo candidato resultados de ese SHA.
Cohorte consumida: `6d17c1e8-29e2-545a-954c-8b30b6e3fa0e`; no reutilizarla.

## Defecto reproducido y corrección en verificación

La ruta HTTP de foto decodifica con validate=True la salida de PostgreSQL
encode(bytea,'base64'), que inserta LF cada 76 caracteres. La regresión nueva con
PostgreSQL real/roles/RLS, QR vigente y JPEG real reprodujo HTTP 400 en el guardia
correcto; los accesos anónimo, padre y guardia de otra sede eran rechazados.

La corrección integrada por PR #30 elimina solo LF de esa representación interna,
conserva validación estricta del resto y devuelve los mismos bytes JPEG. La
regresión pasó después del cambio y comprueba bytes exactos, tipo image/jpeg,
no-store, permisos y token sin consumir. No modifica SQL, migraciones, formatos
externos ni exposición de fotos. El driver E3 distingue ahora rechazo por otra
sede/padre, resolución válida y foto, sin publicar cuerpo ni excepción remota.
Verificación local aprobada: 333 Python con PostgreSQL real, 26 JavaScript,
tipos/lint, migraciones/Django y dependencias Expo. La regresión falló antes y
pasó después de la corrección. PR y main CI aprobaron.
[CD 42777229650](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42777229650)
verifica el candidato bd8eca2; todos sus gates AWS siguen siendo obligatorios.

## Próximos pasos obligatorios

1. Completar suite/PR/checks e integrar solo con CI aprobado y main actualizado.
   El CD anterior terminó; no queda migración ni archive-drill activo. No ampliar
   límites de MFA/sesión, archivo ni políticas para hacer pasar el ensayo.
2. Exigir main CI y CD completos del nuevo SHA/digest: E1/APK, E2, nueve controles
   E3 y lector WORM independiente hasta máximo minimum_sequence. Los campos
   e2_accepted/e3_accepted=false delimitan reportes parciales, no aceptación global.
3. El operador confirmó cuatro cohortes nuevas desde 3592c40; una se consumió en
   el CD anterior y el selector verificará las restantes. No queda acción de
   CloudShell pendiente. Agotarse bloquea y se repone según runbook E2, sin reset.
4. Solo tras esos gates cerrar las seis filas E3 de PLAN. PR #27 sigue borrador;
   su rama local ya integró 71ebf16 y debe reconciliar la corrección y reescribirse
   con SHA/digest/runs/trial/secuencias/APK realmente aceptados. Su diff final será
   solo documentación permitida; exigir calidad/docs-only antes de integrar para
   evitar otro despliegue o consumo de cohorte por el cierre.

## Operación y límites que conservar

- El gateway efímero fue recuperado y el operador sincronizó el callback existente.
  Ensayos y APK usan STAGING_RELEASE_ORIGIN verificado; base_url es solo una pista.
  Ante retirada seguir bootstrap stateless y sincronización estrecha del runbook;
  no repetir commission_e1 ni editar el hostname en cada recreación.
- El wrapper intercambia una vez JWT GitHub por sesión STS temporal reutilizada
  por los hijos; elimina JWT y credenciales heredadas, sin cambiar trust/IAM.
  PR #29 y el CD real completaron la restauración/ancla E2 antes bloqueada.
- Nunca borrar/reiniciar cuentas, canjes, estudiantes, eventos, outbox, recibos ni
  WORM para repetir. No editar migraciones E2 0002–0005 ni ejecutar refresh SQL
  antiguos de work/. No pedir contraseñas/TOTP/semillas/códigos.
- La BD local original alcanzó el límite deliberado de snapshot sintético
  (5000 eventos/8 MB). Se conserva sin ampliar cuotas ni borrar; usar BD aislada
  retenida para suites, según scratch work/e3-apk-isolated-db.txt y scripts de
  verificación work/. .env conserva la original; nunca publicar credenciales.
- pickup_enabled=false del contrato anterior se mantiene. El endpoint E3 separado
  anuncia synthetic_only=true; una capacidad/health nunca concede entrega.
- E4 conserva avisos/consultas/correcciones. E5 conserva Android físico, cámara y
  retorno OIDC nativo, recuperación integral/epoch/carga/RTO, retención
  institucional, firma/distribución y producción NOT_CONFIGURED. No hubo datos,
  importaciones, invitaciones ni mensajes reales. APK de desarrollo no acredita
  instalación/cámara física ni se publica como binario en el repositorio público.
- No crear commits en bucle para registrar cada SHA documental. Distinguir base
  funcional aceptada de revisión documental; consultar releases por SHA en Actions.
  Scratch saneado en work/, ignorado; fuentes/estado aquí y evidencia en su custodia.
