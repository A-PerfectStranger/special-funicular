# Evidencia de AWS

Copias sin credenciales de los artefactos reales de GitHub Actions. Los ZIP
originales tienen retención limitada; estas copias conservan el resultado por SHA.

- e0-staging-33f3ac6.json: artefacto 13598188946 del CD 42433511451. Publicación,
  preparación RDS, migración y staging aprobados. Producción bloqueada hasta E5.
- e0-preflight-42430538070.json: artefacto 13596459500 del preflight de lectura.
  Solo booleanos, sin saldos, correo ni respuestas financieras completas.

Los reportes no son una firma de tercero ni certifican las funciones futuras
E1–E5. El SHA/digest, plano de control y probes son comprobaciones distintas.
Fuentes y contexto de aceptación en ../../PROGRESS.md. RFS09/10/13/14/22,
CA-S09/10/13/14/22. La guarda está configurada; no se presenta una ejecución
futura de parada como ya realizada.

## Base preparatoria E1 (sin aceptación funcional)

`e1-base-staging-6efb4ed.json`: copia del artefacto 13602056856, CD
[42441787035](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42441787035).
Publish/prepare/migrate/staging aprobados, CI main 42441266774 aprobada. La imagen
se contrastó con las tareas en ejecución. Los probes siguen siendo E0 y
`E1_IDENTITY_ENABLED=false`: este reporte no acepta identidad, MFA, WORM o portal
E1. Producción permanece bloqueada hasta E5.

`e1-base-staging-26d7d47.json`: artefacto 13605265154 del CD
[42448253673](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42448253673).
Publish/prepare/migrate/staging aprobados; CI main 42447792803 aprobada. Se
comprobó el SHA-256 del ZIP original y el SHA/digest/probes del reporte. Incluye
las migraciones identity 0003/evidence 0011–0012. E1 desactivada, e1_accepted=false;
no acredita MFA/fixtures/archivo E1 reales. Producción bloqueada hasta E5.

## Primer ensayo E1 con fixtures reales (aceptación incompleta)

Workflow [42449912611](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42449912611),
SHA 26d7d47. ZIPs contrastados por SHA-256 del registro de artefactos:

- e1-trial-staging-26d7d47.json, artefacto 13605930697: API/archivador por digest,
  E1 habilitada solo en ensayo. No aceptación integral.
- e1-browser-26d7d47.json, artefacto 13606035804: tres logins escolares y lector
  aprobados; móvil PADRE falló. No ocultar ni reemplazar este fallo por un PASS.
- e1-cloud-26d7d47.json, artefacto 13605373093: Cognito, WORM/KMS/denegaciones y
  19 eventos firmados/versionados aprobados; no compara todavía una copia SQL.
- APK staging compilado, contenido/configuración y firma debug verificados por
  el job. Manifiesto 13605631927; no implica prueba física ni distribución privada.

El fallo móvil se reprodujo en la captura de response de Chromium para protocolos
nativos. La corrección se verifica por separado; los resultados de 26d7d47 se
conservan sin reinterpretarlos como aprobación de toda E1.
