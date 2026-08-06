# Seguridad de DataReport

## Controles incorporados

- Contraseñas con `scrypt`, política mínima y bloqueo temporal.
- Recuperación y verificación mediante tokens firmados con vencimiento.
- Segundo factor TOTP; el secreto se cifra con Fernet.
- Archivos de usuario cifrados en reposo y descifrados solo en temporales efímeros.
- CSRF en formularios, cookies `HttpOnly`, `SameSite` y `Secure` en producción.
- CAPTCHA Turnstile, límites de solicitudes y registro de eventos de autenticación.
- Validación de propiedad antes de leer un conjunto de datos.
- CSP y cabeceras contra MIME sniffing, framing y filtración de referentes.
- SQL Server mediante SQLAlchemy/ODBC sin credenciales en el código.

## Requisitos de producción

Use HTTPS detrás de un proxy actualizado, SQL Server con TLS, Redis para límites distribuidos, SMTP autenticado y secretos administrados por el proveedor de despliegue. Rote `SECRET_KEY`, `DATA_ENCRYPTION_KEY` y credenciales periódicamente. Una rotación de Fernet requiere recifrar los datos existentes.

## Auditoría

Ejecute `security_checks.ps1` antes de publicar. El flujo automatizado ejecuta pruebas, Bandit y `pip-audit`. Estas verificaciones reducen riesgos conocidos, pero no sustituyen una revisión profesional de infraestructura ni una prueba de penetración autorizada sobre el entorno desplegado.

## Reporte responsable

No publique vulnerabilidades ni datos reales en issues públicos. Contacte de manera privada al propietario del repositorio e incluya pasos de reproducción sin información sensible.
