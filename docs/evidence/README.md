# Evidencia de AWS

## Base integrada 0ca4374

`e1-base-staging-0ca4374.json`: CD
[42501790742](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42501790742),
artefacto 13626615085, ZIP SHA-256
e34ede66e93b9e58f529c030c8a64b866417847a94997724b2237e57f8e2c4eb
verificado. CI main 42501082447 aprobada; publish/prepare/migrate/staging
aprobados. Producción bloqueada E5. E1 false en el CD preparatorio; sus probes
no acreditan todavía los flujos de identidad. El origen observado coincide con
la configuración nueva y el digest en tareas reales se verificó desde el runner.

## Recreación de staging 8bb56b8

Workflow 42497020512, reintento posterior a la aplicación de lifecycle e328c43
por el operador. Los ZIP originales se verificaron por SHA-256 antes de copiar:

| Reporte | Artefacto | SHA-256 ZIP |
| --- | --- | --- |
| e1-trial-staging-8bb56b8.json | 13624802150 | d1dd9ba8909e1fcc6790b999da723d5c801c72966512f7bb7aacb813b2e063c2 |
| e1-browser-8bb56b8.json | 13624972586 | 2655edff3ea7fe7458daec2e0e03313e1717b6bd915b64174361e3aa6cdcd68c |
| e1-cloud-8bb56b8.json | 13624677814 | ba06694565108d563d6586d6d4c4aa817a2df784af6aee10d1ac15e88e7c5414 |

Despliegue por digest/TLS/red aprobado. Express cambió el origen a
re-dc7939bf752047ff8947f600b81bc157.ecs.us-east-1.on.aws. Browser falló antes
del login al conservar la referencia anterior; no acredita identidad móvil/web.
Se preserva el fallo y se actualizan entorno/callback antes del siguiente ensayo.
Cloud es una verificación independiente; ningún reporte acepta E1 por sí solo.

Copias sin credenciales de los artefactos reales de GitHub Actions. Los ZIP
originales tienen retención limitada; estas copias conservan el resultado por SHA.

- e0-staging-33f3ac6.json: artefacto 13598188946 del CD 42433511451. Publicación,
  preparación RDS, migración y staging aprobados. Producción bloqueada hasta E5.
- e0-preflight-42430538070.json: artefacto 13596459500 del preflight de lectura.
  Solo booleanos, sin saldos, correo ni respuestas financieras completas.

Los reportes no son una firma de tercero ni certifican las funciones futuras
E1–E5. El SHA/digest, plano de control y probes son comprobaciones distintas.
Fuentes y contexto de aceptación en ../../PROGRESS.md. RFS09/10/13/14/22,
CA-S09/10/13/14/22. La guarda está configurada; no se presenta una ejecución
futura de parada como ya realizada.

## Base preparatoria E1 (sin aceptación funcional)

`e1-base-staging-6efb4ed.json`: copia del artefacto 13602056856, CD
[42441787035](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42441787035).
Publish/prepare/migrate/staging aprobados, CI main 42441266774 aprobada. La imagen
se contrastó con las tareas en ejecución. Los probes siguen siendo E0 y
`E1_IDENTITY_ENABLED=false`: este reporte no acepta identidad, MFA, WORM o portal
E1. Producción permanece bloqueada hasta E5.

`e1-base-staging-26d7d47.json`: artefacto 13605265154 del CD
[42448253673](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42448253673).
Publish/prepare/migrate/staging aprobados; CI main 42447792803 aprobada. Se
comprobó el SHA-256 del ZIP original y el SHA/digest/probes del reporte. Incluye
las migraciones identity 0003/evidence 0011–0012. E1 desactivada, e1_accepted=false;
no acredita MFA/fixtures/archivo E1 reales. Producción bloqueada hasta E5.

## Primer ensayo E1 con fixtures reales (aceptación incompleta)

Workflow [42449912611](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42449912611),
SHA 26d7d47. ZIPs contrastados por SHA-256 del registro de artefactos:

- e1-trial-staging-26d7d47.json, artefacto 13605930697: API/archivador por digest,
  E1 habilitada solo en ensayo. No aceptación integral.
- e1-browser-26d7d47.json, artefacto 13606035804: tres logins escolares y lector
  aprobados; móvil PADRE falló. No ocultar ni reemplazar este fallo por un PASS.
- e1-cloud-26d7d47.json, artefacto 13605373093: Cognito, WORM/KMS/denegaciones y
  19 eventos firmados/versionados aprobados; no compara todavía una copia SQL.
- APK staging compilado, contenido/configuración y firma debug verificados por
  el job. Manifiesto 13605631927; no implica prueba física ni distribución privada.

El fallo móvil se reprodujo en la captura de response de Chromium para protocolos
nativos. La corrección se verifica por separado; los resultados de 26d7d47 se
conservan sin reinterpretarlos como aprobación de toda E1.

## Segundo ensayo 5ac4f02 (sin aceptación integral)

Workflow [42454301027](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42454301027).
Las copias se extrajeron tras verificar SHA-256 de cada ZIP original:

| Copia | Artefacto | SHA-256 ZIP |
| --- | --- | --- |
| e1-trial-staging-5ac4f02.json | 13606304888 | 7cf1f6cbd1f92909f184086b9520a3bf17b09d5ac5b3f53095af9028d791f59c |
| e1-browser-5ac4f02.json | 13606943244 | e0d1b162c0de8158668b04f08051d0acb09624e7ccd7b757cebb0fdd1f64d7fb |
| e1-cloud-5ac4f02.json | 13606969728 | 9bee13f0db3b7940628b78cc515cedabdd609fa2f1a98aece1d2258de656661f |
| e1-apk-manifest-5ac4f02.json | 13607316973 | a1d8bb1afc2631d84e57fe64edf79304ec7d8446230e0fc078671a0d09145d96 |

Browser conserva su fallo mobile_native_return; escuela aprobada, GUARDIA no
alcanzado, archive-drill omitido. Cloud verificó 37 eventos independientemente.
El APK solo acredita compilación/configuración/firma de desarrollo; no prueba
física ni distribución. Ningún reporte se transforma en aceptación completa.

## Backend 5/15 real sobre 5ac4f02

`e1-backend-limits-5ac4f02.json`: workflow
[42456781366](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42456781366),
artefacto 13608038881, ZIP SHA-256
8e98045a58baefb2af61a1dc4e0aaf4bbaf21e4d7953f34229a0ac38aa708a39 verificado.
Código del sondeo 5744794; release/digest observados contrastados con el reporte
de despliegue estable 5ac4f02. Cinco fallos bloquearon un inicio válido; el web
continuó disponible, hubo denegación a 890,272 s y recuperación a 905,530 s.
Muestreo real sin adelantar relojes, sin SQL, AWS o credenciales. No demuestra el
bloqueo de Cognito ni acepta por sí solo E1. No se desplegó otro SHA durante la
medición; el PR #11 se integró después de completarla.

## Base preparatoria be8f1df

`e1-base-staging-be8f1df.json`: artefacto 13609012854 del CD
[42458832112](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42458832112).
ZIP SHA-256 35e3826a1ce7d0c1bbd9abd71d755352dbaf4127b15439262ab1db293c87a1ed
verificado de nuevo contra el artefacto original al reanudar. CI main
42458226675 aprobada; publish/prepare/migrate/staging aprobados, evidence 0014
incluida. Producción bloqueada E5 y gate E1 omitido por flag false. E1 desactivada,
sin aceptación funcional. La copia se recuperó de la rama documental al reanudar.

## Ensayo integrado 0ca4374

Workflow [42501830048](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42501830048), todos sus jobs aprobados. Copias *-0ca4374.json extraídas después de verificar cada ZIP:

| Artefacto | ID | SHA-256 ZIP |
| --- | --- | --- |
| e1-cloud-acceptance | 13627165558 | d3565efeeb2658f61e0cfc2df3ee34f69664caf19bcab05fafdde88feb430e98 |
| e1-browser-acceptance | 13626991572 | 05654e60112731ec4d3a71d203a9a3ffb9784256e529bf5dc17866ecbc6c09d9 |
| e1-trial-deployment | 13626313377 | 7a003a64715efbbdb5f9bc7e2255328da74a81934543d810b36ca719517e9f68 |
| staging-apk-manifest | 13626254415 | c669687b3b77893f28c84130acbba7a004fef387bbfbd8ba04d87bb883248c8b |
| e1-archive-drill | 13626034115 | 9e0b587b85b029cf651742fb93ca9928de17ef123192967f2f0ed7c189076267 |

Browser aprobó web y protocolo móvil PADRE/GUARDIA, MFA, baja/restauración y sesiones. Cloud inicial verificó 82 eventos; después del drill verificó 91. El intento 86 siguió DENIED tras archivo tardío y el worker se recuperó. No acredita todavía recuperación Cognito/copia SQL ni Android físico.

## Recuperación privada independiente 0ca4374

`e1-recovery-0ca4374.json`: workflow
[42507955250](https://github.com/A-PerfectStranger/special-funicular/actions/runs/42507955250),
artefacto 13628600924, ZIP SHA-256
 d964e798a802a0473bc6418522d9bbbe3358b7315831b2d51e14690c8f68731d
verificado. El operador ejecutó el controlador 36954c0 contra API/SQL 0ca4374.
Los diez límites efectivos y seis controles Cognito aprobaron; las cotas nativas
se conservan en el reporte. Verificador sin SQL/Sign/Put: original coincide con 92
eventos, reescritura con cadena local válida rechazada específicamente contra el
archivo protegido. Mínimo externo suministrado: 91. Las copias/contraseñas/semillas
permanecen privadas; el JSON público solo contiene resultados y high-water.
