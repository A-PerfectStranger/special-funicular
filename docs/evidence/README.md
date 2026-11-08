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
