# Base modular E0

config contiene settings/urls/WSGI. core contiene sondas, pantalla sintética y el comando de comprobación del futuro worker. No instalar auth/admin públicos ni implementar permisos mediante un selector de rol de prueba.

Crear identity, school_roster, authorization, pickup, evidence, school_read, system_read, archive_worker y notification_worker con sus incrementos E1–E4 según requisitos §7.1. Compartir servicios de dominio entre API, templates y workers. Una única base transaccional para retiro; nunca un microservicio por tabla.

En E0 solo existe django_session (operativa) y django_migrations. Los grants por defecto del bootstrap local solo sirven para estas tablas operativas; al introducir evidencia en E1, reemplazarlos por grants explícitos/funcciones y roles separados, RLS forzado y pruebas directas. No aplicar el bootstrap local a AWS.
