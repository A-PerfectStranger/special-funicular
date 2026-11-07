# Agent Toolkit for AWS

Fuente solicitada por el usuario: https://raw.githubusercontent.com/aws/agent-toolkit-for-aws/refs/heads/main/setup-instructions/setup.md (consultada el 7 de noviembre de 2026). Seguir su versión vigente y troubleshooting; este documento registra estado, no sustituye la guía.

Comprobado Linux, curl y uv. AWS CLI no instalado. La sonda a https://awscli.amazonaws.com devuelve `curl: (56) CONNECT tunnel failed, response 403`: bloqueo del proxy. El usuario está modificando el entorno. Faltan nombre del perfil, tipo de experiencia AWS (registro social y proyecto o cuenta avanzada) y región, ya solicitados. No solicitar claves en chat. El entorno no reporta identidades AWS ni secretos configurados.

Después de que el usuario confirme la red, refrescar environment_status y probar una conexión nueva. Instalar CLI v2 oficial y verificar versión. Iniciar `aws login --region REGION --profile PERFIL` (o `--remote` si lo requiere el navegador); la persona completa la autenticación. Credenciales válidas 12 horas, renovables durante 90 días sin reautenticación en navegador según la guía. Verificar con `aws sts get-caller-identity --profile PERFIL` sin registrar credenciales.

El asistente `aws configure agent-toolkit --yes --region us-east-1 --profile PERFIL` requiere interacción humana según la guía. La región del servicio Toolkit es us-east-1, independientemente de la región de infraestructura. Conservar entradas MCP existentes; si ya existe aws-mcp, consultar reconciliación. Añadir solo `env.AWS_MCP_PROXY_PROFILES` con el perfil a las entradas generadas. No sustituir command/args/timeout/transport. Verificar catálogo con `aws agent-toolkit list-available-skills --region us-east-1 --profile PERFIL`.

Tras conocer experiencia de cuenta, leer y añadir reglas oficiales correctas a AGENTS.md, conservando instrucciones existentes entre marcadores estables `<!-- BEGIN AWS Agent Toolkit rules -->` y `<!-- END AWS Agent Toolkit rules -->`. No elegir reglas avanzadas o de proyecto sin ese dato.

No declarar configuración completa hasta verificar todos los pasos. Para otra cuenta: `aws login --profile NOMBRE`, añadir ese nombre a la lista separada por espacios `AWS_MCP_PROXY_PROFILES` de cada configuración MCP y reiniciar la herramienta. La guía exige nueva sesión tras instalar reglas/skills; hacerlo una vez que E0 tenga estado persistido.
