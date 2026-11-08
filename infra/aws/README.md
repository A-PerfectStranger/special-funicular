# AWS: configuración y límite de créditos

Proveedor decidido por el usuario: AWS, `us-east-1`, perfil `aesir`.
Techo total 150 USD para TODO el desarrollo y primer despliegue.
El usuario confirmó saldo suficiente y plazo de financiación hasta el 6 de mayo
de 2027. El techo del proyecto sigue siendo **150 USD totales**. El importe real
se mantiene fuera del repositorio público. AWS ya confirmó créditos suficientes
y vigencia; Cost Explorer y el preflight completo ya aprobaron. Presupuesto,
base privada y staging están aplicados/verificados, con evidencia en PROGRESS.md.
CloudShell se usó para bootstrap y GitHub OIDC para publicación/migración/deploy;
el login interactivo del kit descrito abajo sigue sin acreditarse. No equivale
a gasto cero de la cuenta ni a operación indefinida.

## Distribución propuesta del techo

Son límites de trabajo, **no cotizaciones ni precios de servicios**.

| Uso | Máximo reservado USD |
| --- | ---: |
| E0: ventana inicial de staging, además de local/CI | 3 |
| E1: ensayos IdP/PostgreSQL/KMS/WORM sintéticos | 22 |
| E2/E3: integración y concurrencia | 35 |
| E4: avisos/consulta/observabilidad | 20 |
| E5 y primera ventana de despliegue | 40 |
| Reserva para incidentes, almacenamiento retenido y variación | 30 |
| Total | 150 |

Antes de gastar: verificar créditos restantes/fecha de expiración, consultar
precios actuales oficiales de la región y presupuestar por horas, almacenamiento,
PITR, claves, requests, logs y transferencia. Revisar gasto al inicio/fin de cada
sesión cloud. Si el saldo no cubre la reserva y lo que resta del plan, no aprovisionar.
El tiempo de servicio sostenible depende del uso; 150 USD no garantiza operación indefinida.

Preferir builds/pruebas locales y GitHub Actions sobre máquinas AWS de build.
Activar staging solo durante ensayos. Evitar NAT Gateway, balanceadores, endpoints
privados y réplicas siempre encendidos sin cálculo previo; no eliminar controles
de seguridad para ahorrar. RDS detenido conserva costes de almacenamiento y puede
reiniciarse automáticamente; no usar «stop» como garantía de gasto cero.
No destruir WORM ni claves retenidas: su coste debe quedar reservado hasta vencimiento.

`budget.yaml` prepara un presupuesto TOTAL de coste bruto, sin descontar créditos,
con alertas 25/50/75/90/100%. Requiere correo y fechas reales de vigencia.
AWS Budgets tiene demoras y no impone un corte rígido de gasto. Revisar costes de
Budgets/alertas antes de crearlo. La plantilla ya se aplicó y el presupuesto bruto real se contrastó en la comisión.

### Histórico: bloqueo de facturación resuelto

Este bloqueo histórico se resolvió: el preflight completo 42430538070 aprobó tras habilitar Cost Explorer. La evidencia anterior se conserva para diagnóstico.

El segundo preflight comprobó STS, denegación de acceso IAM ajeno y créditos/vigencia:
https://github.com/A-PerfectStranger/special-funicular/actions/runs/42386350234.
El gasto quedó pendiente. El usuario ejecutó la consulta desde CloudShell y AWS
devolvió `DataUnavailableException`; también confirmó que Facturas no tiene datos.
No equivale a coste cero y no se resuelve ampliando IAM.

[AWS documenta](https://docs.aws.amazon.com/cost-management/latest/userguide/ce-enable.html)
que hay que abrir Cost Explorer y pulsar **Launch Cost Explorer** si aún no está
habilitado; la API no puede habilitarlo. Los datos del mes suelen estar disponibles
unas 24 horas después. Verificar el estado de la consola antes de asumir que ese
plazo empezó. No aprovisionar mientras siga sin acreditarse el gasto.

Para repetir la comprobación actual, ejecutar el workflow con el mismo rol:

```bash
gh workflow run aws-preflight.yml --ref main \
  -f role_arn=arn:aws:iam::CUENTA:role/retiro-seguro-github-preflight
```

Después de aprobarlo siguen siendo necesarios cotización completa, alertas,
IaC de aplicación, identidades de despliegue/migración y adaptador live, antes
de ejecutar los probes de staging. No marcar E0 terminado por aprobar solo OIDC.
Ver [tarifas consultadas y límites de la estimación](cost-estimate.md).

## Conexión alternativa desde AWS CloudShell

El usuario confirmó acceso a CloudShell; no puede acceder al Desktop compartido.
`github-preflight.yaml` crea un rol OIDC de **solo lectura**, confiando exactamente
en `repo:A-PerfectStranger@144553443/special-funicular@1449067177:ref:refs/heads/main` y audiencia
`sts.amazonaws.com`. Solo permite `freetier:GetAccountPlanState` y `ce:GetCostAndUsage`.
No permite desplegar, modificar IAM, leer secretos o asumir el rol desde PR/forks.
El proveedor OIDC existente se reutiliza sin modificarlo; si falta, se crea y retiene.

GitHub confirmó mediante `GET /repos/A-PerfectStranger/special-funicular/actions/oidc/customization/sub`
que `use_immutable_subject=true`, con el prefijo que incluye los IDs de propietario
y repositorio. Se usa ese sujeto exacto con `:ref:refs/heads/main`; el formato
antiguo sin IDs no coincide y el primer preflight no pudo asumir el rol.
No sustituirlo por un wildcard para resolverlo. Un cambio de repositorio o de
personalización OIDC requiere contrastar los metadatos y actualizar template/pruebas.

Revisar el template/script en el commit que se va a ejecutar y, desde CloudShell:

```bash
retiro_sha=SHA_COMPLETO_REVISADO
curl --proto '=https' --tlsv1.3 -fsSL \
  "https://raw.githubusercontent.com/A-PerfectStranger/special-funicular/$retiro_sha/scripts/bootstrap-aws-preflight.sh" \
  -o /tmp/retiro-bootstrap.sh
bash /tmp/retiro-bootstrap.sh "$retiro_sha"
```

El script valida el template en AWS y aplica únicamente el stack
`retiro-seguro-github-preflight`, sin claves permanentes. El ARN devuelto no es
una credencial; permite lanzar desde main el workflow manual `AWS read-only preflight`.
Su sesión efímera comprueba STS, la denegación de `iam:ListUsers`, créditos,
vencimiento y gasto bruto mensual excluyendo créditos/reembolsos. Cost Explorer
puede cobrar la consulta de su API. No crea recursos de aplicación.

El repo es público: el artefacto contiene exclusivamente comprobaciones booleanas,
sin balances, respuestas AWS, credenciales o correo de alertas. Un resultado ausente
o permiso denegado en facturación mantiene el bloqueo. Tampoco un preflight aprobado
acredita por sí solo el presupuesto completo: comprobar cotización, alertas y
costes de recursos/retención antes de nuevos aprovisionamientos. La autorización de despliegue/migración
ya se configuró mediante roles separados; no ampliar este rol de lectura para ese fin.

## Login interactivo: evidencia y selectores privados

La variable `AWS_VERIFICATION_CODE` está disponible en la sesión del 7 de noviembre.
Ese código corresponde a un intento anterior; **no es una credencial AWS ni permite
iniciar un login nuevo**. La CLI genera `state`, un verificador PKCE y una clave
privada por intento; un código de otro proceso no los reemplaza. No imprimirlo ni
guardarlo en Git. No trasladar códigos entre contenedores reiniciados.

La CLI 2.39.6 se reinstaló desde AWS con firma GPG verificada. STS devolvió
`NoCredentials`, sin identidad autenticada. La herramienta de control de navegador
sigue fallando con `the gaas-browser node_repl sandbox cannot be disabled`, pero
se consiguió abrir Chromium directamente en **el escritorio compartido**. La
pantalla de sign-in AWS fue observada; el login nuevo necesita la intervención
del usuario en ese escritorio. Como el usuario no pudo acceder a Desktop, el
intento se canceló y se preparó la ruta CloudShell/OIDC anterior.
Un navegador abierto no acredita STS ni el toolkit.

Todas las órdenes de la sesión deben usar los mismos selectores privados:

```bash
source scripts/aws-env.sh
aws login --region us-east-1 --profile aesir
aws sts get-caller-identity --profile aesir
```

El helper configura perfil, región, configuración y caché de login bajo `work/aws/`
(ignorado); no escribe en el directorio personal. Si la CLI no existe, reinstalarla
desde el instalador oficial con firma, usando `XDG_DATA_HOME="$PWD/work/tools"` y
`XDG_BIN_HOME="$PWD/work/bin"`. No usar `--skip-signature-verification`.
Si el navegador no se abre, `aws login --remote` requiere que el **mismo proceso**
siga vivo y que el código nuevo se introduzca directamente en su terminal privada.
Actualizar un secreto que solo llega a una instancia nueva no completa ese flujo.

## Kit oficial: instalación después de autenticar

Fuente solicitada:
https://raw.githubusercontent.com/aws/agent-toolkit-for-aws/refs/heads/main/setup-instructions/setup.md

Después de STS aprobado, continuar con el wizard y el catálogo. **Login, STS,
wizard, MCP y catálogo aún no verificados.** No marcar setup completo sin evidencia.

```bash
source scripts/aws-env.sh
aws configure agent-toolkit --yes --region us-east-1 --profile aesir
aws agent-toolkit list-available-skills --region us-east-1 --profile aesir
```

La autenticación y los prompts del wizard los completa el humano. Nunca pedir
access keys/secret keys en chat. Credenciales: 12 h, renovables hasta 90 días sin
repetir login de navegador. El endpoint del toolkit siempre es `us-east-1`.
Si el usuario prefiere instalarlo en su propio equipo, seguir la misma guía
oficial y usar esos comandos con su CLI local; ese login no autentica este contenedor.

Después del wizard, añadir exclusivamente a cada entrada `aws-mcp` generada:

```json
"env": {"AWS_MCP_PROXY_PROFILES": "aesir"}
```

Preservar command/args/timeout/transport y otros servidores. Si ya existe una
entrada, preguntar cómo reconciliarla. Las reglas avanzadas oficiales se descargaron
para revisión; su incorporación idempotente en AGENTS.md entre marcadores
`BEGIN/END AWS Agent Toolkit rules` sigue pendiente del flujo de instalación.
Las instrucciones propias del proyecto prevalecen. Verificar catálogo antes de
declarar instalación completa. Para otra cuenta: `aws login --profile <nombre>`,
añadir el nombre a la lista separada por espacios `AWS_MCP_PROXY_PROFILES` y reiniciar
la herramienta de IA tras terminar la configuración.

## Comprobaciones de la superficie pública E0

Cuando exista el destino, ejecutar desde un runner con confianza CA normal:

```bash
uv run python scripts/verify_staging.py https://DOMINIO-STAGING --report work/staging-probes.json
```

Exige TLS 1.3 con certificado/hostname verificados, readiness DB, capabilities
exactas con retiros deshabilitados, rutas de negocio/admin ausentes, escrituras
rechazadas, cabeceras de seguridad y ausencia de cookies. No sigue redirecciones
ni registra cuerpos, cookies o excepciones remotas. Un fallo devuelve 1;
configuración inválida devuelve 2. Las pruebas usan un servidor HTTPS local real
con certificado sintético y verifican también rechazo de TLS 1.2/certificado no
confiable. No son evidencia de despliegue AWS.

El reporte solo acredita esa superficie. No certifica IAM, presupuesto, SHA/digest
de las tareas, IdP, WORM/KMS ni E1–E5. Si existe un proxy que intercepta TLS, el
reporte señala el límite: la negociación cliente-proxy no acredita el TLS del
origen. Completar la aceptación desde un runner sin interceptación y conservar
por separado la evidencia del plano de control, costes y procedencia de release.
