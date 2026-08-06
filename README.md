# DataReport Web

Aplicación web para importar, analizar y visualizar datos sin depender de herramientas complejas de inteligencia empresarial. Permite trabajar con Excel, CSV, exportaciones SQL y tablas MySQL.

## Funcionalidades

- Importación de `.xlsx`, `.xls`, `.csv` y `.sql`.
- Lectura segura de exportaciones SQL sin ejecutar sus instrucciones.
- Detección automática de fechas, categorías y métricas.
- Resúmenes, tablas, rankings y reportes mensuales.
- Constructor visual con gráficos de barras, líneas, circular, dona y área polar.
- Colores, agregaciones, orden y columnas personalizables.
- Conexión opcional con MySQL.
- Pantallas de error claras y adaptables a dispositivos móviles.

## Tecnologías

- Python y Flask
- pandas
- Matplotlib
- Chart.js
- HTML, CSS y JavaScript

## Instalación

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Abre [http://127.0.0.1:5000](http://127.0.0.1:5000) en el navegador.

## Guía de usuario

Consulta el [Manual de Usuario de DataReport](docs/Manual_de_Usuario_DataReport.pdf) para aprender a importar fuentes de datos, generar reportes, personalizar gráficos y resolver errores comunes.

## Flujo básico

1. Carga un archivo compatible o conecta una tabla MySQL.
2. Revisa las columnas detectadas y configura el análisis.
3. Genera un reporte clásico o abre el constructor visual.
4. Personaliza el gráfico, los colores, el cálculo y el orden de las columnas.

## Importación SQL

El importador busca instrucciones `CREATE TABLE` e `INSERT INTO ... VALUES`. No ejecuta el archivo. Si encuentra varias tablas, utiliza la que contenga más registros. El límite por archivo es de 50 MB.

## Seguridad

- No publiques credenciales ni archivos `.env`.
- Los archivos cargados, gráficos generados y entornos virtuales están excluidos de Git.
- Para producción, configura una clave secreta mediante variables de entorno y utiliza un servidor WSGI.

## Cuentas, SQL Server y correo

La aplicación usa SQLite durante el desarrollo y acepta SQL Server en producción mediante SQLAlchemy y `pyodbc`. Copia `.env.example`, genera secretos nuevos y configura `DATABASE_URL` con el controlador ODBC 18.

- Registro con contraseña robusta y verificación de correo.
- Recuperación de contraseña mediante enlaces firmados con vencimiento.
- Segundo factor TOTP compatible con aplicaciones autenticadoras.
- Cloudflare Turnstile configurable para proteger el registro.
- Bloqueo temporal y límites de solicitudes ante intentos repetidos.
- Fuentes y configuraciones de reporte asociadas a cada usuario.
- Exportación PDF con título, colores y orientación personalizados.

Nunca uses los valores de desarrollo en producción. Configura un servicio SMTP, Turnstile, HTTPS, Redis para los límites distribuidos y una clave Fernet independiente.

## Laboratorio estadístico

Después de cargar una fuente, abre **Laboratorio estadístico** desde la configuración. El módulo admite:

- media, mediana, moda, varianza y desviación estándar;
- media ponderada con una columna de ponderaciones;
- cuadrados y raíces cuadradas;
- transpuesta, determinante, inversa y multiplicación de matrices de hasta 10 × 10.

Cada cálculo presenta la fórmula, los valores utilizados, los pasos intermedios y el resultado. Los datos no numéricos se excluyen explícitamente y las matrices incompatibles generan mensajes de validación.

## Verificación de seguridad

Los archivos importados se cifran en reposo con Fernet. Para ejecutar pruebas funcionales, análisis estático y auditoría de dependencias:

```powershell
pip install -r requirements-dev.txt
.\security_checks.ps1
```

Consulta [SECURITY.md](SECURITY.md) para conocer controles, requisitos de producción, rotación de secretos y límites de las pruebas automatizadas.
