# Dependencias de Expo SDK 56

No cambiar de SDK incidentalmente. Base: expo 56.0.24, React 19.2.3 y RN 0.85.3 según bundledNativeModules.json del SDK. Lockfile raíz npm para el workspace.

Auditoría inicial: 19 avisos transitivos (2 low, 15 moderate, 2 high). `npm audit fix --force` proponía bajar Expo a SDK52: rechazado por incompatibilidad con el contrato. Overrides raíz explícitos, no supresiones del auditor:

| Dependencia | Versión fijada | Motivo |
| --- | --- | --- |
| glob | 14.0.4 | GHSA-3g3m-2fjr-6pw4 |
| minimatch en rango >=7 <11.0.1 | 11.0.5 | GHSA-g3hv-75wg-m249; conservar minimatch3 usado por ESLint |
| zod | 4.6.7 | GHSA-mrhx-c7xc-m3w5 |
| deepmerge | 4.1.1 | GHSA-gcqx-w48m-w2h4 afecta 4.2.0–4.3.1; 4.1.1 fuera del rango reportado |

Cambios de major en herramientas transitivas requieren validación: lint, typecheck, test, expo config, export Android y prebuild. EAS/devtools y build nativo deben verificarse por separado; un bundle correcto no acredita esos flujos. Revisar con próximas revisiones de Expo56 y retirar overrides cuando las dependencias originales estén corregidas. El APK no está aceptado hasta completar build nativo y verificar firma/paquete.

El prebuild sin plantilla fijada descargó una plantilla SDK57 (avisó Expo57/RN0.86). Se fija `expo-template-bare-minimum@56.0.38` por URL y SHA256 en build-apk.sh; su package.json declara Expo~56.0.24/React19.2.3/RN0.85.3. No aceptar silenciosamente una plantilla del siguiente SDK.
