from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
from flask import jsonify, send_file
from flask_login import current_user, login_required
import json
import csv
import io
import os
import uuid
import re
import mysql.connector
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from werkzeug.utils import secure_filename

from auth import auth_bp
from extensions import csrf, db, limiter, login_manager, mail
from models import Dataset, User
from security import development_fernet_key
from models import SavedReport
from pdf_reports import build_dataset_pdf

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "development-only-change-me"),
    SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", "sqlite:///datareport.db"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
    DATA_ENCRYPTION_KEY=os.environ.get("DATA_ENCRYPTION_KEY", development_fernet_key()),
    TURNSTILE_SITE_KEY=os.environ.get("TURNSTILE_SITE_KEY"),
    TURNSTILE_SECRET_KEY=os.environ.get("TURNSTILE_SECRET_KEY"),
    ALLOW_LOCAL_CAPTCHA_BYPASS=os.environ.get("FLASK_ENV") != "production",
    ALLOW_UNVERIFIED_LOGIN=os.environ.get("FLASK_ENV") != "production",
    MAIL_SERVER=os.environ.get("MAIL_SERVER", "localhost"),
    MAIL_PORT=int(os.environ.get("MAIL_PORT", "25")),
    MAIL_USE_TLS=os.environ.get("MAIL_USE_TLS", "0") == "1",
    MAIL_USERNAME=os.environ.get("MAIL_USERNAME"),
    MAIL_PASSWORD=os.environ.get("MAIL_PASSWORD"),
    MAIL_DEFAULT_SENDER=os.environ.get("MAIL_DEFAULT_SENDER", "no-reply@datareport.local"),
    MAIL_SUPPRESS_SEND=os.environ.get("MAIL_SUPPRESS_SEND", "1") == "1",
    RATELIMIT_STORAGE_URI=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
)

UPLOAD_FOLDER = "uploads"
CHART_FOLDER = "static/reportes"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Inicia sesión para continuar."
csrf.init_app(app)
mail.init_app(app)
limiter.init_app(app)
app.register_blueprint(auth_bp)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


with app.app_context():
    db.create_all()

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CHART_FOLDER, exist_ok=True)


def respuesta_error(titulo, mensaje, estado=400, sugerencias=None):
    if request.path.startswith("/api/"):
        return jsonify({"error": mensaje}), estado
    return render_template(
        "error.html",
        titulo=titulo,
        mensaje=mensaje,
        estado=estado,
        sugerencias=sugerencias or [],
    ), estado


def _separar_tuplas_sql(bloque):
    tuplas = []
    inicio = None
    profundidad = 0
    entre_comillas = False
    escape = False

    indice = 0
    while indice < len(bloque):
        caracter = bloque[indice]
        if escape:
            escape = False
            indice += 1
            continue
        if caracter == "\\" and entre_comillas:
            escape = True
            indice += 1
            continue
        if caracter == "'":
            if entre_comillas and indice + 1 < len(bloque) and bloque[indice + 1] == "'":
                indice += 2
                continue
            entre_comillas = not entre_comillas
        elif not entre_comillas:
            if caracter == "(":
                if profundidad == 0:
                    inicio = indice + 1
                profundidad += 1
            elif caracter == ")" and profundidad:
                profundidad -= 1
                if profundidad == 0 and inicio is not None:
                    tuplas.append(bloque[inicio:indice])
                    inicio = None
        indice += 1
    return tuplas


def _convertir_literal_sql(valor):
    valor = valor.strip()
    if valor.upper() == "NULL":
        return None
    if valor.upper() == "TRUE":
        return True
    if valor.upper() == "FALSE":
        return False
    try:
        return int(valor)
    except ValueError:
        try:
            return float(valor)
        except ValueError:
            return valor


def leer_sql(ruta):
    if os.path.getsize(ruta) > 50 * 1024 * 1024:
        raise ValueError("El archivo SQL supera el límite de 50 MB.")

    try:
        with open(ruta, "r", encoding="utf-8-sig") as archivo:
            contenido = archivo.read()
    except UnicodeDecodeError:
        with open(ruta, "r", encoding="latin1") as archivo:
            contenido = archivo.read()

    columnas_por_tabla = {}
    patron_create = re.compile(
        r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+[`\"\[]?([\w.-]+)[`\"\]]?\s*\((.*?)\)\s*;",
        re.IGNORECASE | re.DOTALL,
    )
    for coincidencia in patron_create.finditer(contenido):
        tabla, definicion = coincidencia.groups()
        columnas = []
        for linea in definicion.splitlines():
            linea = linea.strip().rstrip(",")
            columna = re.match(r"[`\"\[]?([\w.-]+)[`\"\]]?\s+", linea)
            if columna and columna.group(1).upper() not in {"PRIMARY", "UNIQUE", "KEY", "CONSTRAINT", "FOREIGN", "CHECK"}:
                columnas.append(columna.group(1))
        if columnas:
            columnas_por_tabla[tabla] = columnas

    filas_por_tabla = {}
    patron_insert = re.compile(
        r"INSERT\s+INTO\s+[`\"\[]?([\w.-]+)[`\"\]]?\s*(?:\((.*?)\))?\s*VALUES\s*(.*?);",
        re.IGNORECASE | re.DOTALL,
    )
    for coincidencia in patron_insert.finditer(contenido):
        tabla, columnas_insert, bloque_valores = coincidencia.groups()
        if columnas_insert:
            columnas = [parte.strip().strip('`"[] ') for parte in columnas_insert.split(",")]
            columnas_por_tabla[tabla] = columnas
        else:
            columnas = columnas_por_tabla.get(tabla, [])

        for tupla in _separar_tuplas_sql(bloque_valores):
            lector = csv.reader(io.StringIO(tupla), delimiter=",", quotechar="'", escapechar="\\", skipinitialspace=True)
            valores = [_convertir_literal_sql(valor) for valor in next(lector)]
            if not columnas:
                columnas = [f"columna_{indice + 1}" for indice in range(len(valores))]
                columnas_por_tabla[tabla] = columnas
            if len(valores) == len(columnas):
                filas_por_tabla.setdefault(tabla, []).append(dict(zip(columnas, valores)))

    if not filas_por_tabla:
        raise ValueError("No se encontraron instrucciones INSERT INTO ... VALUES compatibles en el archivo SQL.")

    tabla = max(filas_por_tabla, key=lambda nombre: len(filas_por_tabla[nombre]))
    df = pd.DataFrame(filas_por_tabla[tabla], columns=columnas_por_tabla.get(tabla))
    df.attrs["sql_table"] = tabla
    df.attrs["sql_tables_found"] = len(filas_por_tabla)
    return df


def leer_archivo(ruta):
    extension = os.path.splitext(ruta)[1].lower()

    if extension == ".csv":
        try:
            return pd.read_csv(ruta)
        except UnicodeDecodeError:
            return pd.read_csv(ruta, encoding="latin1")

    if extension in [".xlsx", ".xls"]:
        return pd.read_excel(ruta)

    if extension == ".sql":
        return leer_sql(ruta)

    raise ValueError("Formato no permitido.")


def convertir_numero(serie):
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(serie, errors="coerce")

    def limpiar_valor(valor):
        if pd.isna(valor):
            return None

        texto = str(valor).strip()
        texto = re.sub(r"[^\d,.\-]", "", texto)

        if texto == "":
            return None

        if "," in texto and "." in texto:
            if texto.rfind(",") > texto.rfind("."):
                texto = texto.replace(".", "").replace(",", ".")
            else:
                texto = texto.replace(",", "")
        elif "," in texto:
            partes = texto.split(",")
            if len(partes[-1]) == 3 and len(partes) > 1:
                texto = "".join(partes)
            else:
                texto = texto.replace(",", ".")

        try:
            return float(texto)
        except (TypeError, ValueError):
            return None

    return serie.apply(limpiar_valor)


def convertir_fecha(serie):
    return pd.to_datetime(serie, errors="coerce", dayfirst=True, format="mixed")


def obtener_dataframe_actual():
    ruta = session.get("data_file")

    if not ruta or not os.path.exists(ruta):
        return None

    return leer_archivo(ruta)


def generar_resumen(df):
    return {
        "filas": df.shape[0],
        "columnas": df.shape[1],
        "nulos": int(df.isnull().sum().sum()),
        "duplicados": int(df.duplicated().sum()),
        "columnas_lista": list(df.columns)
    }


def detectar_columnas(df):
    columnas = list(df.columns)

    numericas = []
    fechas = []
    categorias = []

    for columna in columnas:
        serie = df[columna]
        nombre_columna = columna.lower()
        nombre_sugiere_fecha = any(
            termino in nombre_columna for termino in ("fecha", "date", "mes")
        )
        es_fecha = pd.api.types.is_datetime64_any_dtype(serie)

        if not es_fecha and not pd.api.types.is_numeric_dtype(serie):
            fecha_convertida = convertir_fecha(serie)
            es_fecha = fecha_convertida.notna().mean() >= 0.45

        if es_fecha or nombre_sugiere_fecha:
            fechas.append(columna)

        numerica_convertida = convertir_numero(serie)
        porcentaje_numerico = numerica_convertida.notna().mean()
        es_numerica = not (es_fecha or nombre_sugiere_fecha) and porcentaje_numerico >= 0.6

        if es_numerica:
            numericas.append(columna)

        if not (es_fecha or nombre_sugiere_fecha or es_numerica):
            categorias.append(columna)

    return columnas, numericas, fechas, categorias


def crear_grafico_mensual(tabla_mensual, valor_col):
    if tabla_mensual is None or tabla_mensual.empty:
        return None

    nombre = f"mensual_{uuid.uuid4().hex}.png"
    ruta = os.path.join(CHART_FOLDER, nombre)

    plt.figure(figsize=(10, 5))
    plt.plot(tabla_mensual["mes"], tabla_mensual["resultado"], marker="o")
    plt.title("Reporte mensual")
    plt.xlabel("Mes")
    plt.ylabel(valor_col)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(ruta)
    plt.close()

    return f"reportes/{nombre}"


def crear_grafico_categoria(tabla_categoria, valor_col):
    if tabla_categoria is None or tabla_categoria.empty:
        return None

    nombre = f"categoria_{uuid.uuid4().hex}.png"
    ruta = os.path.join(CHART_FOLDER, nombre)

    plt.figure(figsize=(10, 5))
    plt.bar(tabla_categoria["categoria"].astype(str), tabla_categoria["resultado"])
    plt.title("Ranking por categoría")
    plt.xlabel("Categoría")
    plt.ylabel(valor_col)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(ruta)
    plt.close()

    return f"reportes/{nombre}"


@app.route("/")
def index():
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    return render_template("index.html")


@app.route("/panel")
@login_required
def dashboard():
    datasets = Dataset.query.filter_by(user_id=current_user.id).order_by(Dataset.created_at.desc()).limit(20).all()
    return render_template("dashboard.html", datasets=datasets)


@app.route("/subir", methods=["POST"])
@login_required
def subir_archivo():
    archivo = request.files.get("archivo")

    if not archivo or archivo.filename == "":
        return respuesta_error(
            "Falta seleccionar un archivo",
            "Selecciona un archivo antes de continuar.",
            sugerencias=["Usa un archivo CSV, Excel o SQL.", "Comprueba que el archivo no esté vacío."],
        )

    extension = os.path.splitext(archivo.filename)[1].lower()
    if extension not in {".csv", ".xlsx", ".xls", ".sql"}:
        return respuesta_error(
            "Formato no compatible",
            f"El archivo {archivo.filename} no tiene un formato admitido.",
            sugerencias=["Formatos disponibles: .csv, .xlsx, .xls y .sql.", "Exporta tus datos a uno de esos formatos e inténtalo nuevamente."],
        )

    filename = secure_filename(archivo.filename)
    nombre_unico = f"{uuid.uuid4().hex}_{filename}"
    ruta = os.path.join(app.config["UPLOAD_FOLDER"], nombre_unico)

    archivo.save(ruta)

    try:
        df_validacion = leer_archivo(ruta)
    except (ValueError, OSError, pd.errors.ParserError) as error:
        if os.path.exists(ruta):
            os.remove(ruta)
        return respuesta_error(
            "No pudimos leer el archivo",
            str(error),
            sugerencias=["Verifica que el archivo no esté dañado.", "Si es SQL, debe contener instrucciones INSERT INTO ... VALUES."],
        )

    session["data_file"] = ruta
    if extension == ".sql":
        tabla_sql = df_validacion.attrs.get("sql_table", "tabla importada")
        session["data_name"] = f"{filename} · tabla: {tabla_sql}"
    else:
        session["data_name"] = filename
    session["data_source"] = "archivo"

    dataset = Dataset(user_id=current_user.id, name=session["data_name"], source_type="archivo", storage_path=ruta, row_count=df_validacion.shape[0], column_count=df_validacion.shape[1])
    db.session.add(dataset)
    db.session.commit()
    session["dataset_id"] = dataset.id

    return redirect(url_for("analisis"))


@app.route("/mysql", methods=["POST"])
@login_required
def mysql_datos():
    host = request.form.get("host", "").strip()
    puerto = request.form.get("puerto", "3306").strip()
    usuario = request.form.get("usuario", "").strip()
    password = request.form.get("password", "")
    base_datos = request.form.get("base_datos", "").strip()
    tabla = request.form.get("tabla", "").strip()

    if not all((host, puerto, usuario, base_datos, tabla)):
        return respuesta_error(
            "Datos de conexión incompletos",
            "Completa host, puerto, usuario, base de datos y tabla.",
            sugerencias=["El puerto habitual de MySQL es 3306.", "Si tienes un archivo exportado, puedes subir directamente el archivo .sql."],
        )

    if not puerto.isdigit() or not 1 <= int(puerto) <= 65535:
        return respuesta_error("Puerto no válido", "Escribe un puerto entre 1 y 65535.")

    if not re.fullmatch(r"[A-Za-z0-9_$]+", tabla):
        return respuesta_error("Nombre de tabla no válido", "La tabla solo puede contener letras, números, guion bajo o signo de dólar.")

    try:
        conexion = mysql.connector.connect(
            host=host,
            port=puerto,
            user=usuario,
            password=password,
            database=base_datos
        )

        consulta = "SELECT * FROM " + tabla
        df = pd.read_sql(consulta, conexion)
        conexion.close()

        nombre_unico = f"mysql_{uuid.uuid4().hex}.csv"
        ruta = os.path.join(app.config["UPLOAD_FOLDER"], nombre_unico)
        df.to_csv(ruta, index=False, encoding="utf-8")

        session["data_file"] = ruta
        session["data_name"] = f"MySQL: {base_datos}.{tabla}"
        session["data_source"] = "mysql"

        dataset = Dataset(user_id=current_user.id, name=session["data_name"], source_type="mysql", storage_path=ruta, row_count=df.shape[0], column_count=df.shape[1])
        db.session.add(dataset)
        db.session.commit()
        session["dataset_id"] = dataset.id

        return redirect(url_for("analisis"))

    except mysql.connector.Error as error:
        app.logger.warning("Fallo de conexión MySQL: %s", error)
        return respuesta_error(
            "No fue posible conectar con MySQL",
            "Revisa los datos de conexión y confirma que el servidor esté disponible.",
            sugerencias=["Verifica host, puerto, usuario y contraseña.", "Confirma que la base y la tabla existan.", "También puedes exportar la tabla y subir el archivo .sql."],
        )


@app.route("/analisis")
@login_required
def analisis():
    df = obtener_dataframe_actual()

    if df is None:
        return respuesta_error(
            "No hay datos cargados",
            "Primero carga un archivo o conecta una fuente de datos.",
            404,
            ["Regresa al inicio para seleccionar tus datos."],
        )

    resumen = generar_resumen(df)
    columnas, numericas, fechas, categorias = detectar_columnas(df)

    vista_previa = df.head(8).to_html(classes="tabla", index=False)

    return render_template(
        "analisis.html",
        nombre=session.get("data_name", "Datos cargados"),
        resumen=resumen,
        columnas=columnas,
        numericas=numericas,
        fechas=fechas,
        categorias=categorias,
        fecha_sugerida=fechas[0] if fechas else None,
        numerica_sugerida=numericas[0] if numericas else None,
        categoria_sugerida=categorias[0] if categorias else None,
        vista_previa=vista_previa
    )


@app.route("/constructor")
@login_required
def constructor():
    df = obtener_dataframe_actual()
    if df is None:
        return respuesta_error(
            "No hay datos cargados",
            "La sesión no contiene un archivo disponible para analizar.",
            404,
            ["Regresa al inicio y carga nuevamente tus datos."],
        )

    columnas, numericas, fechas, categorias = detectar_columnas(df)
    return render_template(
        "constructor.html",
        nombre=session.get("data_name", "Datos cargados"),
        columnas=columnas,
        numericas=numericas,
        fechas=fechas,
        categorias=categorias,
    )


@app.route("/api/datos")
@login_required
def api_datos():
    df = obtener_dataframe_actual()
    if df is None:
        return jsonify({"error": "No hay datos cargados."}), 404

    columnas, numericas, fechas, categorias = detectar_columnas(df)
    vista = df.head(250).copy().astype(object)
    vista = vista.where(pd.notna(vista), None)
    return jsonify({
        "nombre": session.get("data_name", "Datos cargados"),
        "columnas": columnas,
        "numericas": numericas,
        "fechas": fechas,
        "categorias": categorias,
        "total_filas": int(df.shape[0]),
        "filas": json.loads(vista.to_json(orient="records", date_format="iso")),
    })


@app.route("/api/visualizacion", methods=["POST"])
@csrf.exempt
@login_required
def api_visualizacion():
    df = obtener_dataframe_actual()
    if df is None:
        return jsonify({"error": "No hay datos cargados."}), 404

    config = request.get_json(silent=True) or {}
    dimension = config.get("dimension")
    metrica = config.get("metrica")
    agregacion = config.get("agregacion", "sum")
    orden = config.get("orden", "desc")

    try:
        limite = max(1, min(50, int(config.get("limite", 12))))
    except (TypeError, ValueError):
        limite = 12

    if dimension not in df.columns:
        return jsonify({"error": "Selecciona una dimensión válida."}), 400

    trabajo = df.copy()
    trabajo["_dimension"] = trabajo[dimension].fillna("Sin dato").astype(str)
    if metrica:
        if metrica not in df.columns:
            return jsonify({"error": "Selecciona una métrica válida."}), 400
        trabajo["_metrica"] = convertir_numero(trabajo[metrica])
    else:
        trabajo["_metrica"] = 1

    operaciones = {"sum": "sum", "mean": "mean", "count": "count", "min": "min", "max": "max"}
    resultado = trabajo.groupby("_dimension", dropna=False)["_metrica"].agg(operaciones.get(agregacion, "sum"))
    resultado = resultado.dropna().sort_values(ascending=orden != "asc").head(limite)
    valores = [round(float(valor), 2) for valor in resultado.tolist()]

    return jsonify({
        "etiquetas": resultado.index.tolist(),
        "valores": valores,
        "resumen": {
            "categorias": len(resultado),
            "total": round(float(sum(valores)), 2),
            "promedio": round(float(sum(valores) / len(valores)), 2) if valores else 0,
        },
    })


@app.route("/reporte", methods=["POST"])
@login_required
def reporte():
    df = obtener_dataframe_actual()

    if df is None:
        return respuesta_error("No hay datos cargados", "Carga un archivo antes de generar el reporte.", 404)

    fecha_col = request.form.get("fecha_col")
    valor_col = request.form.get("valor_col")
    categoria_col = request.form.get("categoria_col")
    tipo_calculo = request.form.get("tipo_calculo", "sum")
    fecha_inicio = request.form.get("fecha_inicio")
    fecha_fin = request.form.get("fecha_fin")
    try:
        top_n = max(1, min(50, int(request.form.get("top_n", 10))))
    except (TypeError, ValueError):
        top_n = 10

    columnas_validas = set(df.columns)
    for columna in (fecha_col, valor_col, categoria_col):
        if columna and columna not in columnas_validas:
            return respuesta_error(
                "Configuración no válida",
                "Una de las columnas seleccionadas ya no existe en los datos.",
                sugerencias=["Vuelve a Configurar y selecciona nuevamente los campos."],
            )

    if tipo_calculo not in {"sum", "mean", "count"}:
        tipo_calculo = "sum"

    df_trabajo = df.copy()

    if valor_col:
        df_trabajo["_valor"] = convertir_numero(df_trabajo[valor_col])
    else:
        df_trabajo["_valor"] = 1
        valor_col = "Cantidad de registros"

    if fecha_col:
        df_trabajo["_fecha"] = convertir_fecha(df_trabajo[fecha_col])

        if fecha_inicio:
            inicio = pd.to_datetime(fecha_inicio)
            df_trabajo = df_trabajo[df_trabajo["_fecha"] >= inicio]

        if fecha_fin:
            fin = pd.to_datetime(fecha_fin)
            df_trabajo = df_trabajo[df_trabajo["_fecha"] <= fin]

    df_valido = df_trabajo.dropna(subset=["_valor"])

    total = df_valido["_valor"].sum()
    promedio = df_valido["_valor"].mean()
    maximo = df_valido["_valor"].max()
    minimo = df_valido["_valor"].min()

    metricas = {
        "registros": int(df_trabajo.shape[0]),
        "total": round(float(total), 2) if pd.notna(total) else 0,
        "promedio": round(float(promedio), 2) if pd.notna(promedio) else 0,
        "maximo": round(float(maximo), 2) if pd.notna(maximo) else 0,
        "minimo": round(float(minimo), 2) if pd.notna(minimo) else 0,
        "datos_validos": int(df_valido.shape[0]),
        "datos_invalidos": int(df_trabajo["_valor"].isna().sum())
    }

    tabla_mensual = None
    tabla_categoria = None

    if fecha_col:
        df_fecha = df_trabajo.dropna(subset=["_fecha"]).copy()
        df_fecha["_mes"] = df_fecha["_fecha"].dt.to_period("M").astype(str)

        if tipo_calculo == "mean":
            tabla_mensual = df_fecha.groupby("_mes")["_valor"].mean().reset_index()
        elif tipo_calculo == "count":
            tabla_mensual = df_fecha.groupby("_mes")["_valor"].count().reset_index()
        else:
            tabla_mensual = df_fecha.groupby("_mes")["_valor"].sum().reset_index()

        tabla_mensual.columns = ["mes", "resultado"]

    if categoria_col:
        df_categoria = df_trabajo.copy()
        df_categoria["categoria"] = df_categoria[categoria_col].astype(str)

        if tipo_calculo == "mean":
            tabla_categoria = df_categoria.groupby("categoria")["_valor"].mean().reset_index()
        elif tipo_calculo == "count":
            tabla_categoria = df_categoria.groupby("categoria")["_valor"].count().reset_index()
        else:
            tabla_categoria = df_categoria.groupby("categoria")["_valor"].sum().reset_index()

        tabla_categoria.columns = ["categoria", "resultado"]
        tabla_categoria = tabla_categoria.sort_values("resultado", ascending=False).head(top_n)

    grafico_mensual = crear_grafico_mensual(tabla_mensual, valor_col)
    grafico_categoria = crear_grafico_categoria(tabla_categoria, valor_col)

    tabla_mensual_html = None
    tabla_categoria_html = None

    if tabla_mensual is not None:
        tabla_mensual_html = tabla_mensual.to_html(classes="tabla", index=False)

    if tabla_categoria is not None:
        tabla_categoria_html = tabla_categoria.to_html(classes="tabla", index=False)

    vista_previa = df_trabajo.head(10).drop(columns=[col for col in ["_valor", "_fecha"] if col in df_trabajo.columns]).to_html(classes="tabla", index=False)

    return render_template(
        "reporte.html",
        nombre=session.get("data_name", "Datos cargados"),
        metricas=metricas,
        valor_col=valor_col,
        fecha_col=fecha_col,
        categoria_col=categoria_col,
        tipo_calculo=tipo_calculo,
        tabla_mensual=tabla_mensual_html,
        tabla_categoria=tabla_categoria_html,
        grafico_mensual=grafico_mensual,
        grafico_categoria=grafico_categoria,
        vista_previa=vista_previa
    )


@app.route("/reporte/pdf", methods=["POST"])
@login_required
def exportar_reporte_pdf():
    df = obtener_dataframe_actual()
    if df is None:
        return respuesta_error("No hay datos cargados", "Carga datos antes de exportar.", 404)
    title = request.form.get("pdf_title", "Reporte DataReport").strip()[:180] or "Reporte DataReport"
    primary = request.form.get("primary_color", "#6F2DBD")
    secondary = request.form.get("secondary_color", "#B58CFF")
    orientation = request.form.get("orientation", "portrait")
    if orientation not in {"portrait", "landscape"}:
        orientation = "portrait"
    report = SavedReport(user_id=current_user.id, dataset_id=session.get("dataset_id"), title=title, configuration={"primary": primary, "secondary": secondary, "orientation": orientation})
    db.session.add(report)
    db.session.commit()
    pdf = build_dataset_pdf(df, title, current_user.display_name, primary, secondary, orientation)
    return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=f"datareport-{report.id}.pdf")


@app.errorhandler(404)
def pagina_no_encontrada(error):
    return respuesta_error(
        "Página no encontrada",
        "La dirección solicitada no existe o fue movida.",
        404,
        ["Revisa la dirección o regresa al inicio."],
    )


@app.errorhandler(405)
def metodo_no_permitido(error):
    return respuesta_error(
        "Acción no permitida",
        "Esta operación no puede realizarse desde esta pantalla.",
        405,
        ["Regresa a la pantalla anterior e inténtalo nuevamente."],
    )


@app.errorhandler(413)
def archivo_demasiado_grande(error):
    return respuesta_error(
        "El archivo es demasiado grande",
        "Data Reporter admite archivos de hasta 50 MB.",
        413,
        ["Reduce el archivo, elimina columnas innecesarias o divídelo en varias partes."],
    )


@app.errorhandler(500)
def error_interno(error):
    app.logger.exception("Error interno no controlado: %s", error)
    return respuesta_error(
        "Algo no salió como esperábamos",
        "Ocurrió un error interno. Tus archivos originales no fueron modificados.",
        500,
        ["Vuelve al inicio e inténtalo nuevamente.", "Si el problema continúa, prueba con un archivo más pequeño."],
    )


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
