# Tarifas consultadas para preparar staging E0

Consulta: 7 de noviembre de 2026, región `us-east-1`. Fuente: catálogo público
AWS Price List, sin descuento de créditos ni suposición de Free Tier. Los JSON
originales se descargaron en `work/downloads/pricing-*.json` (temporales).
**No es una cotización final ni autoriza aprovisionar**: faltan gasto real,
cantidades, duración, políticas de conservación y alertas aplicadas.

| Concepto | USD por unidad | Unidad / SKU AWS |
| --- | ---: | --- |
| Fargate x86 Linux CPU | 0.04048 | vCPU-h, `8CESGAFWKAJ98PME` |
| Fargate memoria | 0.004445 | GB-h, `PBZNQUSEXZUC34C9` |
| ALB | 0.0225 | hora o fracción, `37CUWUT8GSNQEPUV` |
| Capacidad ALB | 0.008 | LCU-h, `P2XGEJ8N3KU52WA8` |
| IPv4 pública en uso | 0.005 | dirección-h, `4GQUNXTFWVSGPUZK` |
| Aurora PostgreSQL Serverless v2, Standard | 0.12 | ACU-h, `AVKW7ZJP8D72HNQC` |
| Aurora PostgreSQL almacenamiento | 0.10 | GB-mes, `7GYUVAA992PFJPCB` |
| KMS, versión de clave administrada por cliente | 1.00 | mes, `U553K98XGDXCYHWS` |
| Secrets Manager | 0.40 | secreto-mes, `BJ3PQ9BYGU6P632F` |
| Secrets Manager requests | 0.000005 | request, `4MDZ5VNEJPMUTG9B` |

Archivos oficiales y fecha de publicación del catálogo consultado:

- [AmazonECS](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonECS/20261019224317/us-east-1/index.json): 19 de octubre de 2026.
- [AWSELB](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSELB/20261105220241/us-east-1/index.json): 5 de noviembre de 2026.
- [AmazonVPC](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonVPC/20261105181945/us-east-1/index.json): 5 de noviembre de 2026.
- [AmazonRDS](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonRDS/20261029070635/us-east-1/index.json): 29 de octubre de 2026.
- [awskms](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/awskms/20261026201814/us-east-1/index.json): 26 de octubre de 2026.
- [AWSSecretsManager](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSSecretsManager/20260911124610/us-east-1/index.json): 11 de septiembre de 2026.

Ejemplo aritmético de cómputo/red, sin prometer configuración ni coste total:
1 tarea de 0.25 vCPU/0.5 GB, 1 ALB, 1 LCU, 3 IPv4 públicas y hasta 1 ACU,
durante 3 horas, suman `3 × (0.25×0.04048 + 0.5×0.004445 + 0.0225 + 0.008 +
3×0.005 + 0.12) = 0.5346675 USD`. Faltan I/O, almacenamiento, PITR/backups,
ECR, logs, métricas, transferencia, claves/versiones, secretos, requests e impuestos.
Su coste retenido debe calcularse hasta su vencimiento, incluso con compute detenido.
No extrapolar este ejemplo a seis meses ni al flujo de negocio E1–E5.

## URL sin comprar dominio

El usuario delegó la elección y no dispone de dominio. La documentación actual
indica que [App Runner no admite clientes nuevos](https://docs.aws.amazon.com/apprunner/latest/dg/service-source-image.html).
[ECS Express Mode](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-getting-started.html)
ofrece una URL `https://<servicio>.ecs.us-east-1.on.aws` y certificado administrado.
Es un candidato para el staging sintético, pendiente de IaC y prueba real de canal,
red, permisos y costes. Crea ALB/Fargate y otros recursos facturables: hay que acotar
duración/escalado y verificar su retirada. No se ha desplegado ni registrado dominio.

El techo total sigue siendo 150 USD y la reserva de 30 USD no se consume sin
contabilizar las obligaciones futuras de almacenamiento/claves. Ajustar la
distribución propuesta entre fases antes de un E0 con recursos de pago; la fila
E0 de 0 USD del README describe la base local/CI, sin certificar gasto cero de cuenta.
