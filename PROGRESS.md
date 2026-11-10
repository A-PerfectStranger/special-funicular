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
ensaya ahora 3592c40. **No atribuirle los resultados del candidato anterior.**
No avanzar main mientras migra o ejecuta archive-drill/aceptación. No queda una
acción CloudShell pendiente; pedir intervención solo ante un bloqueo real nuevo.
La sesión de desarrollo no tiene identidad AWS de operador.

## Próximos pasos obligatorios

1. Exigir en ese candidato publish/prepare/migrate/staging, SHA/digest runtime,
   TLS/callback, E1 browser/cloud/archive-drill y APK staging con bundle verificado.
2. Exigir E2 y los nueve controles E3; después, lector WORM independiente hasta
   el máximo minimum_sequence de ambos reportes. Un reporte de protocolo con
   e3_accepted=false delimita esa dependencia y no equivale a aceptación global.
3. Consultar disponibilidad mediante selector real, sin deducirla de intentos
   omitidos. El pool previo tenía cuatro cohortes y algunas están consumidas.
   Agotarse bloquea: operador repone según runbook E2, sin resetear historial.
4. Solo tras esos gates, verificar las seis filas E3 de PLAN y cerrar este estado
   con SHA/digest/runs/secuencias reales. PR #27 sigue borrador; su diff final
   será exclusivamente documentación permitida. Exigir calidad y filtro docs-only
   antes de integrar, para no redeplegar ni consumir otra cohorte por el cierre.

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
