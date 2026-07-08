from flask import Flask, render_template, request
import pandas as pd
import os
import mysql.connector
import matplotlib.pyplot as plt

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"

def analizar_dataframe(df):
    resumen = {
        "filas": df.shape[0],
        "columnas": df.shape[1],
        "nulos": int(df.isnull().sum().sum()),
        "duplicados": int(df.duplicated().sum()),
        "columnas_lista": list(df.columns)
    }

    columnas_numericas = df.select_dtypes(include="number").columns
    estadisticas = None

    if len(columnas_numericas) > 0:
        estadisticas = df.describe().to_html(classes="tabla")

    vista_previa = df.head(10).to_html(classes="tabla", index=False)

    grafico = None

    if len(columnas_numericas) > 0:
        columna = columnas_numericas[0]
        plt.figure(figsize=(8, 4))
        df[columna].head(10).plot(kind="bar")
        plt.title("Grafico de " + columna)
        plt.xlabel("Registros")
        plt.ylabel(columna)
        grafico = "static/grafico.png"
        plt.tight_layout()
        plt.savefig(grafico)
        plt.close()

    return resumen, estadisticas, vista_previa, grafico

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/subir", methods=["POST"])
def subir_archivo():
    archivo = request.files["archivo"]

    if archivo.filename == "":
        return "No seleccionaste ningun archivo"

    ruta = os.path.join(app.config["UPLOAD_FOLDER"], archivo.filename)
    archivo.save(ruta)

    if archivo.filename.endswith(".csv"):
        df = pd.read_csv(ruta)
    elif archivo.filename.endswith(".xlsx") or archivo.filename.endswith(".xls"):
        df = pd.read_excel(ruta)
    else:
        return "Formato no permitido. Usa Excel o CSV."

    resumen, estadisticas, vista_previa, grafico = analizar_dataframe(df)

    return render_template(
        "reporte.html",
        resumen=resumen,
        estadisticas=estadisticas,
        vista_previa=vista_previa,
        grafico=grafico
    )

@app.route("/mysql", methods=["POST"])
def mysql_datos():
    host = request.form["host"]
    puerto = request.form["puerto"]
    usuario = request.form["usuario"]
    password = request.form["password"]
    base_datos = request.form["base_datos"]
    tabla = request.form["tabla"]

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

        resumen, estadisticas, vista_previa, grafico = analizar_dataframe(df)

        return render_template(
            "reporte.html",
            resumen=resumen,
            estadisticas=estadisticas,
            vista_previa=vista_previa,
            grafico=grafico
        )

    except Exception as e:
        return "Error al conectar con MySQL: " + str(e)

if __name__ == "__main__":
    app.run(debug=True)
