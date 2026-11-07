# E0: alcance y criterios antes de implementar

Base remota revisada: main c711ff9ea266b8e797f4c207d813bfd18aae4762. Solo documentos; PROGRESS.md inexistente. Arquitectura: Django modular con templates, PostgreSQL, Expo SDK 56; AWS seleccionado por el usuario. No extender E0 a RF01–RF19 ni presentar mocks como aceptacion de RFS.

1. A0: checkout limpio, dependencias bloqueadas, comandos reales y configuracion sintetica.
2. A1: home renderizada por Django, GET live/ready sin datos sensibles; ready falla con DB caida/migraciones pendientes. API v1 documentada; retiro siempre deshabilitado. Sin Django Admin ni endpoints funcionales parciales. Apoya RFS13/14/15; no acredita sus CA completos.
3. A2: Expo 56 con TypeScript, flujos informativos padre/guardia, sin autoasignar rol ni permitir operaciones; tests y bundle Android.
4. A3: CI ejecutable con lint/tipos/unitarias/contratos/PostgreSQL/migraciones, escaneo de secretos/dependencias; runtime sin DDL/superusuario/BYPASSRLS. Controles RFS22 de base, RLS de negocio en E1.
5. A4: misma imagen backend/futuro worker sin privilegios, revision OCI y digest; APK sintetico interno firmado para desarrollo con SHA/checksum. No equivale a firma ni distribucion productivas.
6. A5: estructura CD, configuracion fail-closed, credenciales efimeras y serializacion previstas. AWS no configurado impide desplegar; nunca reportar deploy exitoso. Conectar/validar staging requiere cuenta, red y destino reales.
7. A6: docs de arranque, presupuesto total maximo USD150, estado real de cada prueba/artefacto y siguientes pasos en PROGRESS.md.

Etapas: base/contratos → movil → CI/artefactos/CD → verificacion y continuidad. Usar PostgreSQL real; no SQLite. Gastar USD0 en AWS durante la base local. Configuracion del toolkit AWS independiente del build; bloquea por inputs, red o login humano cuando corresponda.
