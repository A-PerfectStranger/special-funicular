# E1 — identidad, aislamiento y evidencia

Estado: ensayo integrado aprobado; cierre pendiente del control privado y del CD
con E1 habilitada. Fuente funcional: `0ca43742fd1a5ad77311a64ee522ef932682922d`,
OCI `sha256:9faea8109c88f3cc94718868dfa9bbb05e100fb56b93832ed4c47b10b6c544a8`.
Solo datos sintéticos; retiros y producción deshabilitados.

## Matriz de aceptación

| ID | Contrato y referencias | Evidencia verificada / pendiente |
| --- | --- | --- |
| E1-01 | Cuatro roles; OIDC Code/PKCE móvil, BFF web, MFA reciente, sesiones de 5 min, idle por rol, refresh/replay, logout y baja online. AT04; RFS01/03/07/08/09/19; AB09/11/12. | Ensayo 42501830048: web ADMIN_SISTEMA/ADMIN_ESCUELA y protocolo compartido PADRE/GUARDIA con Cognito/TOTP real, reauth, refresh, logout y baja/restauración sin reactivar access vigente. Backend 5/15 medido realmente en 42456781366. Pendiente recuperación y bloqueo nativo Cognito privados. Límites temporales/replay/carreras cubiertos también con PostgreSQL real local. |
| E1-02 | Escuelas/sedes, estudiantes, padres y vínculos, exactamente un principal activo; claims/inputs no asignan hijos. AT02; RF03/14; RFS02/03; AB02/10/24. | Restricciones y cruce de escuelas/familias en PostgreSQL real; roster AWS original de 13 identidades, dos escuelas/seis estudiantes. Pendiente contraste privado del conjunto cerrado y vínculos tras recuperación/bajas. Bulk e invitaciones corresponden a E2. |
| E1-03 | RLS ENABLE/FORCE y contexto transaccional del actor; credenciales SQL separadas sin propiedad, DDL, BYPASSRLS ni rol escritor; lector sin menores. AT02/05; RFS02/12/22; AB02/10/14. | Roles reales locales, conexión reutilizada/rollback, mutaciones y SET ROLE denegados. API/archivo por digest con credenciales separadas; DTO real mínimo sin datos de menores. Pendiente inspección privada de grants/RLS/políticas efectivas de AWS. |
| E1-04 | Eventos canónicos append-only mediante funciones estrechas; evento/outbox atómicos; archivo idempotente con leases y recuperación. AT05; RFS11/12/13/23; AB14/21/22/23. | PostgreSQL real: rollback, head sin huecos, crash/reclaim, lease antiguo rechazado, recibo único. Worker AWS real; drill 42501830048: archivo ausente deniega, worker recuperado y recibo tardío no reabre. Intento denegado 86 protegido, verificado externamente hasta 91. |
| E1-05 | WORM COMPLIANCE/KMS de ensayo; bytes/hash/versión/retención exactos; manifiestos firmados fuera de SQL y detección externa. AT05/06; RFS10/12/17/23; AB22/25. | AWS real: siete días, versionado privado/cifrado, claves separadas activas, Sign/Put/delete de versión/reducción de retención denegados. Verificación externa hasta 91, digest e7ae0bde5be75547d0116fbe9a9b000bb12ff7e7e42309069b7e36a25b066804. Pendiente copia SQL original/reescrita y custodia/políticas efectivas privadas. |
| E1-06 | Proteger login escolar antes de abrir sesión; deduplicación, cierre ante fallo, admin sistema solo lee accesos paginados con lectura auditada. RF16/17; CA-F16/17; RFS14/21/22; AB10/21. | Cognito real: tres logins/tres accesos OPENED; reauth/callback inválido no duplican ingreso; filtros/DTO/paginación y logout aprobados. Drill real: sin archivo, callback/portal 401 y registro DENIED; después del archivo tardío sigue DENIED, mientras un login nuevo protegido abre. |

## Procedencia

- CI main 42501082447 aprobó calidad, PostgreSQL/RLS, Chromium, auditorías,
  imagen y APK; 160 pruebas Python y nueve JS. Cuatro regresiones reales de
  Chromium comprueban captura/rechazo de callbacks nativos HTTP/JavaScript.
- CD 42501790742 aprobó publicación, preparación, migración y staging con E1
  desactivada. Producción bloqueada por E5; esos probes técnicos no aceptan E1.
- Ensayo [42501830048](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42501830048)
  aprobó todos los jobs, incluidos browser, cloud, staging-apk y archive-drill.
  Los JSON originales y SHA-256 de sus ZIP se conservan en docs/evidence.
- El manifiesto APK identifica el binario/configuración/firma de desarrollo;
  no se publicó el APK en el repositorio público. No acredita instalación ni
  retorno Android físico, distribución privada o firma productiva (E5).

## Integración y límites

El workflow compartido e1-checks.yml ejecuta browser/cloud/APK/archive-drill
para el ensayo manual y para CD cuando e1_enabled=true. Un gate fallido bloquea
promoción. La activación continua sigue pendiente hasta completar el control
privado y verificar su ejecución real. Producción permanece bloqueada hasta E5.

Cognito exponencial y backend 5/15 son políticas distintas autorizadas por el
usuario. COMPLIANCE siete días solo conserva evidencia sintética; la política
institucional/productiva sigue pendiente. E2–E5, retiros, datos reales, avisos,
restauración integral del dominio desde backup y pruebas físicas no se aceptan
como parte de esta fase.

Los fallos previos de 26d7d47/5ac4f02 y el origen anterior de 8bb56b8 se preservan
sin reinterpretarlos como PASS. La retirada programada deja Express INACTIVE;
la recreación requiere etiquetado acotado y puede cambiar la URL. El nuevo origen
y el callback deben coincidir antes de introducir las credenciales de ensayo.
