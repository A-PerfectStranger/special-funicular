# E1 — alcance, aceptación y ejecución

Base revisada: `bbe48f4`, tras fetch de origin/main el 7 de noviembre de 2026
(America/Bogota). Rama: `feat/e1-identity-evidence`. AGENTS, PLAN, PROGRESS y
requisitos leídos antes de implementar. E0 aceptada; E2–E5 fuera de esta entrega.

## Criterios fijados antes de implementar

| ID | Resultado exigido | Referencias / comprobación |
| --- | --- | --- |
| E1-01 | Solo cuatro roles locales; OIDC Code/PKCE móvil y BFF web, MFA validada, callbacks correlacionados; tokens ≤5 min, inactividad 5/15 min, logout y baja online. Reautenticación ≤5 min. | AT04, RFS01/03/07/08/09/19, AB09/11/12. Firma/issuer/audience/nonce/tiempos, replay, recuperación sin asignación de hijos, backend: 5 fallos/15 min y bloqueo de 15 min; Cognito: bloqueo exponencial nativo autorizado. IdP real en staging. |
| E1-02 | Escuelas/sedes, estudiantes, padres y vínculos con referencias por escuela y exactamente un principal activo por estudiante activo. Claims/inputs no asignan permisos ni hijos. | AT02, RF03/14, RFS02/03, AB02/10/24. Dos escuelas/dos familias; principal/secundario; restricciones PostgreSQL. Activación/bulk se completan en E2. |
| E1-03 | RLS ENABLE/FORCE y contexto transaccional derivado del actor autenticado; identidades SQL separadas sin DDL/BYPASSRLS/propiedad; lector sistema sin menores. | AT02/05, RFS02/12/22, AB02/10/14. Roles reales, conexión reutilizada, accesos laterales y mutaciones denegados. |
| E1-04 | Eventos canónicos append-only construidos por funciones estrechas; evento y outbox atómicos; worker idempotente, reintentos y diagnóstico observable. | AT05, RFS11/12/13/23, AB14/21/22/23. Sin INSERT libre, rollback, crash/reintento, ausencia de secretos/PII excesiva. |
| E1-05 | S3 Object Lock COMPLIANCE/KMS de ensayo real; hash, versión y retención exactos verificados; manifiestos firmados/anclados fuera de BD; verificador independiente detecta huecos/divergencias. | AT05/06, RFS10/12/17/23, AB22/25. Denegación real de mutación/retención/clave; no sustituir por mocks. Retención sintética siete días autorizada; productiva sin definir. |
| E1-06 | Login escolar protegido antes de abrir sesión, deduplicación por login, fallos cierran acceso; admin sistema solo consulta accesos paginados y lectura auditada. | RF16/17, CA-F16/17, RFS14/21/22, AB10/21. Tres logins/tres eventos, refresh/callback duplicado sin duplicación, archivo ausente/tardío bloquea portal. |

## Etapas verificables

1. Persistencia: modelos, migraciones expand, roles SQL, funciones/RLS y pruebas
   PostgreSQL reales; no exponer rutas mientras falten los controles.
2. Identidad: adaptador OIDC, sesiones/reauth/revocación/límites y clientes web/móvil;
   contrato API y pruebas negativas/temporales.
3. Evidencia: archivo/recibos/manifiestos/verificador, consultas y login protegido;
   pruebas de permisos, replay y fallos; configuración de servicios de ensayo.
4. Integración: `make check`, seguridad y builds pertinentes, aceptación staging
   real por SHA/digest, matriz criterio→evidencia, PLAN/PROGRESS/README/runbooks.

## Dependencias y estado inicial

- No hay IdP humano ni WORM/KMS E1 configurados en el repositorio. El usuario
  confirmó Cognito para ensayo y siete días COMPLIANCE para evidencia sintética.
- La identidad AWS OIDC existente es CI/main; no es una credencial de operador
  ni permite asumir que esta sesión puede aprovisionar recursos nuevos.
- No se habilitan retiros, invitaciones, datos reales ni producción.
- Ningún criterio E1 se considera aprobado hasta registrar su evidencia.

## Verificación del checkpoint local (sin aceptación AWS)

| Criterio | Evidencia local | Falta para cierre |
| --- | --- | --- |
| E1-01 | test_oidc, test_e1_identity, test_e1_school_access y pruebas móvil: firmas, PKCE/binding/replay, roles/canales, reauth/idle, revocación/refresh, CSRF. | Cognito/MFA y recuperación reales; retorno nativo y destino integrado. |
| E1-02 | test_e1_isolation: dos escuelas/familias, principal obligatorio/único, referencias compuestas. | Verificar migración/provisión del esquema en destino real. |
| E1-03 | Credenciales reales locales; RLS, conexión reutilizada/rollback, mutaciones y SET ROLE denegados. Lector sistema sin SELECT de menores. | Mismos límites comprobados con credenciales AWS/SQL del destino. |
| E1-04 | test_e1_outbox: rollback sesión/evento/outbox, head sin huecos, crash/reclaim, lease antiguo rechazado, recibo único; test_archive: escritura idempotente. | Worker desplegado, fallos/reintentos/latencias reales y observabilidad del destino. |
| E1-05 | Canonical bytes, RSA-PSS, versiones/retención/hash y huecos/divergencia probados con adaptadores simulados; IaC cfn-lint aprobada. | WORM/KMS/denegaciones/manifiestos REALES, high-water externo y custodia de claves. |
| E1-06 | Tres sesiones/tres eventos, callbacks únicos, archivo tardío sin reapertura; DTO/fechas/paginación auditados y navegador local. | Login escolar completo con Cognito y recibo AWS dentro del plazo. |

Resultado: ninguna fila acredita por sí sola el cierre integral de E1. Las casillas
E1 de PLAN permanecen pendientes. La base preparatoria se integró por autorización expresa en `6efb4ed`. Su CI y
staging aprobaron con identidad E1 desactivada; producción sigue bloqueada E5.
El operador confirmó la comisión de recursos/roles desde `ede76aa`. El discovery
y formulario real Cognito responden, sin acreditar todavía un login/MFA completo.
La continuación `feat/e1-staging-acceptance` añade Managed Login v2, fixtures
privados, revocación de familia refresh y comparación con copia de BD. Sus checks
y aceptación real se registran por separado; no heredan el resultado del SHA base.

Decisión del usuario del 7 de noviembre de 2026: se acepta el bloqueo exponencial
nativo de Cognito y se conserva el límite estricto 5/15 en los puntos de entrada
del backend. RFS07 refleja esa decisión. CA-S07 exige comprobar ambas políticas;
no se exige una configuración fija 5/15 que Cognito no admite.
