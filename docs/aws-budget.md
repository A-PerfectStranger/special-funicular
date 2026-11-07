# AWS: presupuesto total de USD 150

Decisión del usuario: AWS. Límite **total de créditos**, no USD 150 mensuales. No se han creado recursos ni consultado saldo/facturación en esta sesión. Gasto AWS generado por esta sesión: USD 0 (solo trabajo local). Saldo real y elegibilidad de cada servicio para créditos: sin verificar.

| Uso | Tope reservado USD |
| --- | ---: |
| E0 local y builds locales/CI | 0 |
| E1–E4: ensayos breves de IdP, RDS, KMS y S3 Object Lock | 30 |
| Staging integral y ensayos E5 | 35 |
| Primera ventana de despliegue productivo | 40 |
| Reserva: logs, copias, evidencia retenida, red y contingencias | 45 |
| Total | 150 |

Estos son sobres de gasto, no cotizaciones ni límites impuestos por AWS. Antes de crear recursos: verificar saldo y vencimiento, región, precios actuales, compatibilidad de créditos, horas previstas y coste de recursos ya existentes. Un AWS Budget alerta con retraso: NO es un corte automático ni garantiza evitar cargos. No prometer operación indefinida con USD150.

Desarrollo habitual con Docker/PostgreSQL y datos sintéticos. Staging bajo demanda, en una sola región, con etiquetas `project`, `environment`, `owner`, `expires-at`. Apagar cómputo al acabar; RDS detenido sigue cobrando almacenamiento y vuelve a iniciar tras su límite de parada. No dejar staging permanente. Evitar NAT Gateway, balanceadores, endpoints privados y clústeres sobredimensionados sin comparar su coste fijo; no abrir PostgreSQL a internet para ahorrar. Mantener PostgreSQL administrado, aislamiento, TLS, KMS, WORM y PITR exigidos.

Antes de aprovisionar, comparar un entorno mínimo RDS + cómputo de aplicación/worker y entrada TLS1.3 con costes por hora y almacenamiento/red; elegir IaC solo con cuenta/región confirmadas. Producir un plan de coste por recurso y duración, no una estimación global sin precios. No reducir retención, eliminar evidencia ni destruir claves para ahorrar. Retención institucional pendiente: no inventar días productivos ni activar datos reales. La reserva contempla objetos y backups que no se puedan borrar al finalizar ensayos.

Configurar alarmas acumuladas al 25/50/75/90% del saldo efectivamente disponible y forecast cuando sea aplicable. Al 75%, detener nuevas pruebas de pago y revisar consumo; al 90%, suspender aprovisionamiento y apagar solo recursos descartables sintéticos. Proteger evidencia y backups. Etiquetas/horarios y alertas se verificarán realmente tras login; aún NO están creados.

Expo/EAS, GitHub Actions y almacenamiento de APK pueden tener cuotas/cargos externos a los créditos AWS: verificar el plan antes de ejecutar builds remotos. El repositorio es público; no publicar APK internos en artifacts/releases públicos. La entrega local de ensayo no es distribución productiva.
