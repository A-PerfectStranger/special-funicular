# Tarifas consultadas para preparar staging E0

Consulta: 7 de noviembre de 2026, región `us-east-1`. Fuente: catálogo público
AWS Price List, sin descuento de créditos ni suposición de Free Tier. Los JSON
originales se descargaron en `work/downloads/pricing-*.json` (temporales).
**Estimación de referencia, no garantía de coste**. El preflight de gasto y
las alertas ya se aplicaron. La ventana E0 reserva 3 USD y la base retenida hasta
27 USD de la reserva existente; configuración y evidencia en PROGRESS.md.

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
1 tarea de 0.25 vCPU/0.5 GB, 1 ALB, 1 LCU, 3 IPv4 públicas y una RDS PostgreSQL db.t4g.micro,
durante 3 horas, suman `3 × (0.25×0.04048 + 0.5×0.004445 + 0.0225 + 0.008 +
3×0.005 + 0.016) = 0.2215275 USD`. Faltan I/O, almacenamiento, PITR/backups,
ECR, logs, métricas, transferencia, claves/versiones, secretos, requests e impuestos.
Su coste retenido debe calcularse hasta su vencimiento, incluso con compute detenido.
No extrapolar este ejemplo a seis meses ni al flujo de negocio E1–E5.

## URL sin comprar dominio

El usuario delegó la elección y no dispone de dominio. La documentación actual
indica que [App Runner no admite clientes nuevos](https://docs.aws.amazon.com/apprunner/latest/dg/service-source-image.html).
[ECS Express Mode](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-getting-started.html)
ofrece una URL `https://<servicio>.ecs.us-east-1.on.aws` y certificado administrado.
Es el destino de staging sintético aplicado y verificado en E0; evidencia por
SHA/digest en PROGRESS.md. Crea ALB/Fargate y otros recursos facturables: hay que acotar
duración/escalado y verificar su retirada. El servicio se desplegó sin registrar dominio propio.

El techo total sigue siendo 150 USD y la reserva de 30 USD no se consume sin
contabilizar las obligaciones futuras de almacenamiento/claves. Ajustar la
distribución entre fases antes de nuevos recursos: E0 tiene reserva de 3 USD,
reasignados de E1 (22 USD), con el mismo techo total de 150 USD. No equivale
a gasto cero de cuenta ni a operación indefinida.

## Selección compatible con Free Plan: RDS privado

Aurora Express no admite VPC; se descarta. RDS PostgreSQL db.t4g.micro Single-AZ
está tarifado a 0.016 USD/h (`9HPEGXQTDDGH53C9`, mismo catálogo AmazonRDS citado).
La instancia se limita a 20 GB y se detiene fuera de ensayos, con guarda para el
reinicio automático semanal. Almacenamiento y cuatro secretos se estiman en
3.90 USD/mes, sin confundir detención con gasto cero. La reserva destinada a base
hasta mayo se ajusta a 27 USD dentro de los 30 existentes. Es una estimación,
pendiente de confirmar con el inventario real y gasto facturado.
