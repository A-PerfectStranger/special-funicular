# AWS: configuración y límite de créditos

Proveedor decidido por el usuario: AWS, `us-east-1`, perfil `aesir`.
Techo total 150 USD para TODO el desarrollo y primer despliegue.
No se ha leído facturación ni saldo: autenticación pendiente. No se han creado
recursos AWS desde esta sesión. Eso no demuestra gasto cero de la cuenta.

## Distribución propuesta del techo

Son límites de trabajo, **no cotizaciones ni precios de servicios**.

| Uso | Máximo reservado USD |
| --- | ---: |
| E0 local/CI, sin recursos AWS | 0 |
| E1: ensayos IdP/PostgreSQL/KMS/WORM sintéticos | 25 |
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
Budgets/alertas antes de crearlo; la plantilla no ha sido aplicada ni validada por AWS.

## Kit oficial: ejecución y bloqueo actual

Fuente solicitada:
https://raw.githubusercontent.com/aws/agent-toolkit-for-aws/refs/heads/main/setup-instructions/setup.md

Linux detectado; curl y uv disponibles. Acceso HTTPS a awscli.amazonaws.com verificado.
CLI 2.39.6 instalada con el instalador oficial y firma GPG verificada.
Ubicación local de esta sesión: `work/bin/aws`; configuración ignorada en
`work/aws/config`. No se escribió ninguna clave en Git. Perfil `aesir`, región `us-east-1`.

El navegador compartido falló con `the gaas-browser node_repl sandbox cannot be disabled`.
`aws login --remote` abrió el flujo externo pero el usuario no tiene terminal
del entorno para completar el intercambio. **Login, STS, wizard, MCP y catálogo no verificados.**
No marcar setup completo ni cerrar la sesión como si el toolkit estuviera activo.

Para continuar en este entorno una vez reparado el navegador/terminal:

```bash
export PATH="$PWD/work/bin:$PATH"
export AWS_CONFIG_FILE="$PWD/work/aws/config"
aws login --region us-east-1 --profile aesir --remote
aws sts get-caller-identity --profile aesir
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
