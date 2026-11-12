# Continuidad

[PLAN](PLAN.md) concentra aceptación y pendientes; [README](README.md) y runbooks,
comandos. **E4/E5 y producción real siguen pendientes.** Sin activación escolar,
datos ni avisos reales. No atribuir aceptación a un candidato posterior.

## Base aprobada

Main `55263bd8a31e4954ff1acba5354e7f306894b994`, PR #37 integrada.
[CI 43165684917](https://github.com/A-PerfectStranger/special-funicular/actions/runs/43165684917)
aprobado. [CD 43167057252](https://github.com/A-PerfectStranger/special-funicular/actions/runs/43167057252)
aprobó publicación, migración/staging, E1/browser/cloud/archive-drill, APK privado,
E2/E3 y WORM independiente: 1.896 eventos en 61 s. Solo producción bloqueó por
configuración incompleta. El pool repuesto permitió los gates; no resetear ni
reutilizar cohortes consumidas.

Digest `sha256:d0efa19f27cce5d6c047b055b491077a86aca8c5f0d03f3f907f03308729053d`.
APK SHA-256 `18f8b34543b770b09c8f4444d328a6c54366d02277fe52e61c4d89ebd634249f`.
Descarga privada confirmada por el operador con versión/checksum/origen activos.
Redmi 10C/Android 13, comprobación conjunta confirmada por el responsable:
instalación al renombrar .apk_ a .apk, conexión, login e1-a-p1 con MFA y retorno
nativo, rol PADRE, A1/A2 como principal y zona America/Bogota. Bloqueo/retorno
cierra detalle y revalida; sin red oculta familia/exige conexión, con red recupera
sesión y familia. Permiso de notificaciones denegado correctamente.

El registro de avisos falla incluso con permiso concedido. El APK actual solo
muestra un error genérico; causa pendiente. No hay ADB ni registro/token/recepción
push confirmados. Faltan cámara, creación/revocación, puerta, actualización y demás
pruebas E5. Credenciales/MFA permanecen en la consola/vault privados, fuera de chat.

## Bloqueo productivo y corrección

Cuenta `028364485203`, región `us-east-1`, operador CloudShell, techo USD 150 y
plan FREE obligatorio. Base `retiro-production-base` en `ROLLBACK_COMPLETE`;
lifecycle ausente. La inspección de solo lectura confirmó ausencia de la BD en
RDS y el catálogo CFN: Database, DatabaseKey y tres secretos DELETE_SKIPPED;
los demás recursos DELETE_COMPLETE. La inspección completa bloqueó en Database:
el inspector aprobado solo contemplaba CREATE_FAILED para una BD ausente.
No hubo recuperación, retirada del stack ni aprovisionamiento productivo.

## Candidato de PR #38

[PR #38](https://github.com/A-PerfectStranger/special-funicular/pull/38), rama
fix/production-recovery-inspection: recuperación contempla DELETE_SKIPPED solo
para retiro-production ausente en RDS, identificador y Retain exactos. Preserva
validaciones de clave/secretos, plan privado y preflight antes de retirar registros.
La corrección de producción pasó CI sobre 83124e7; el candidato ampliado necesita
sus propios checks, imagen y APK. Sigue sin integrar ni aceptar en AWS.

El móvil separa permiso, token nativo, Expo y vinculación; códigos N01–N06 sin
textos de SDK/tokens/respuestas. Esperas de red de 15 s; respuestas tardías no
inician otro paso y registro de cuenta vencido se trata como sin confirmar.
Solo anuncia registro si el servidor devuelve registered=true. Falta probar el
APK nuevo para identificar la causa real; esto no acredita avisos funcionando.

Validación: suite Python de la corrección 558/558 con PostgreSQL/roles reales;
42 JavaScript, tipos/lint y bundle Android del candidato móvil aprobados.
Checks Django/Expo, migraciones, plantillas AWS y auditorías conservan su alcance;
los resultados por commit de CI/CD y el ensayo físico siguen siendo necesarios.

## Continuación concreta

1. Revisar CI del nuevo SHA de PR #38; integrar solo con todos los checks aprobados.
   Luego CI de main/CD y APK privado del mismo candidato; no esperar horas ni
   omitir controles. El APK de desarrollo de CI no sustituye el de staging.
2. Descargar y actualizar sobre la instalación existente, con la misma firma,
   desde custodia privada. Si CloudShell añade .apk_, renombrar a .apk.
   Repetir únicamente el registro de avisos y recoger el código N01–N06;
   resolver su causa antes de avanzar a recepción real.
3. Desde main limpio aprobado, repetir la inspección completa de
   [producción](docs/runbooks/production.md). En CloudShell se conserva el checkout
   `$HOME/retiro-operador-55263bd`; no asumir que existe un plan de recuperación
   válido tras la inspección bloqueada. No ejecutar código privilegiado de la rama.
4. Revalidar precios, gasto, crédito y vigencia FREE durante toda la custodia.
   Plan privado: reservas 40 nuevas + 50 retenidas + 30 contingencia, techo 150;
   no inventar una revisión vigente. Backup aprobado un día; evidencia 90 días y
   custodia mínima 97 días. Preservar claves, secretos, backups y evidencias.
5. Solo con inspección/fuentes/finanzas aprobadas, recuperar foundation según
   runbook, comisionar ventana técnica, verificar retirada efectiva y proponer
   configuración pública por PR. Funciones de negocio siguen apagadas.
6. Continuar [E5](docs/runbooks/e5.md) con el responsable, un paso por vez.
   Cerrar E4: notificador/Expo/allowlist/alarma reales, gate integrado y WORM del
   candidato. E5 conserva recuperación integral/epoch, carga/RTO, fallos,
   retención efectiva, firma/distribución productivas y ensayo presencial.

Staging mantiene e4_enabled=false; ambos destinos pickup_enabled=false y
synthetic_only=true. Una pasarela es efímera: comprobar origen/SHA/digest actuales.
Resultados por commit en Actions, scratch privado en work/ y evidencia/anclas
fuera del repositorio público. CI/CD se inicia al final y se entregan enlaces
sin esperar ejecuciones largas; sus resultados pendientes siguen pendientes.
