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
Redmi 10C/Android 13 rechaza la instalación con «App no instalada»; causa pendiente.
Solo está disponible el teléfono, sin ADB. La copia llegó por otra vía, pesa
37,1 MB y hay 22 GB libres. Se solicitó descargar directamente desde CloudShell
al Redmi y comprobar un único intento; resultado pendiente. No modificar APK ni firma
sin un diagnóstico. No hay login ni avisos físicos acreditados.
No acreditar instalación, cámara, retorno OIDC ni avisos a partir de la descarga.

## Bloqueo productivo y corrección

Cuenta `028364485203`, región `us-east-1`, operador CloudShell, techo USD 150 y
plan FREE obligatorio. Base `retiro-production-base` en `ROLLBACK_COMPLETE`;
lifecycle ausente. La inspección de solo lectura confirmó ausencia de la BD en
RDS y el catálogo CFN: Database, DatabaseKey y tres secretos DELETE_SKIPPED;
los demás recursos DELETE_COMPLETE. La inspección completa bloqueó en Database:
el inspector aprobado solo contemplaba CREATE_FAILED para una BD ausente.
No hubo recuperación, retirada del stack ni aprovisionamiento productivo.

Rama `fix/production-recovery-inspection`: contempla DELETE_SKIPPED únicamente
para retiro-production con ausencia RDS y ambas políticas Retain comprobadas.
Conserva validación de claves/secretos, comparación del plan privado y preflight
antes de cualquier retirada. Añade códigos fijos de diagnóstico sin respuestas
remotas, secretos ni identificadores físicos. Pruebas de BD existente, permisos
denegados, deriva, estado ajeno y preservación de recursos aprobadas localmente.
Validación local: make check completo aprobado, 558 pruebas Python con PostgreSQL
y roles reales, 27 JavaScript, lint/tipos, migraciones, plantillas AWS y checks
Django/Expo; gitleaks y auditorías Python/npm sin hallazgos. CI y aceptación AWS
de esta corrección quedan pendientes hasta sus resultados.

## Continuación concreta

1. Revisar checks del PR de la rama; integrar solo con todos aprobados. Consultar
   CI de main y gates por SHA; no esperar horas ni omitir controles.
2. Desde main limpio aprobado, repetir la inspección completa de
   [producción](docs/runbooks/production.md). En CloudShell se conserva el checkout
   `$HOME/retiro-operador-55263bd`; no asumir que existe un plan de recuperación
   válido tras la inspección bloqueada. No ejecutar código privilegiado de la rama.
3. Revalidar precios, gasto, crédito y vigencia FREE durante toda la custodia.
   Plan privado: reservas 40 nuevas + 50 retenidas + 30 contingencia, techo 150;
   no inventar una revisión vigente. Backup aprobado un día; evidencia 90 días y
   custodia mínima 97 días. Preservar claves, secretos, backups y evidencias.
4. Solo con inspección/fuentes/finanzas aprobadas, recuperar foundation según
   runbook, comisionar ventana técnica, verificar retirada efectiva y proponer
   configuración pública por PR. Funciones de negocio siguen apagadas.
5. Resolver el rechazo Android antes del siguiente paso presencial. APK privado
   en `work/mobile-download/` del checkout CloudShell; no publicar el binario.
   Tras instalación, continuar [E5](docs/runbooks/e5.md) paso a paso con el operador.
6. Cerrar E4: notificador/Expo/allowlist/alarma reales, gate integrado y WORM del
   candidato. E5 conserva recuperación integral/epoch, carga/RTO, fallos,
   retención efectiva, firma/distribución productivas y ensayo presencial.

Staging mantiene e4_enabled=false; ambos destinos pickup_enabled=false y
synthetic_only=true. Una pasarela es efímera: comprobar origen/SHA/digest actuales.
Resultados por commit en Actions, scratch privado en work/ y evidencia/anclas
fuera del repositorio público. CI/CD se inicia al final y se entregan enlaces
sin esperar ejecuciones largas; sus resultados pendientes siguen pendientes.
