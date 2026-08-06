from io import BytesIO

import pandas as pd

from app import app
from call_center_analysis import analyze_distribution, analyze_wait_times


def test_positive_skew_uses_median_and_percentiles():
    waits = pd.Series([5, 6, 7, 7, 8, 8, 9, 10, 12, 55, 90])
    result = analyze_wait_times(waits, 15)
    assert result["skewness"] > 1
    assert result["mean"] > result["median"]
    assert result["p95"] > result["p90"] > result["median"]
    assert result["histogram_counts"]
    assert "positiva" in result["shape"].lower()


def test_service_target_percentage():
    result = analyze_wait_times(pd.Series([10, 20, 30, 40]), 25)
    assert result["within_target"] == 50


def test_generic_distribution_supports_minimum_targets():
    result = analyze_distribution(pd.Series([40, 60, 80, 100]), 70, "minimum", "Nota")
    assert result["within_target"] == 50
    assert result["target_direction"] == "minimum"


def test_excel_upload_can_generate_call_center_analysis():
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    workbook = BytesIO()
    pd.DataFrame({"tiempo_espera": [5, 6, 7, 8, 9, 12, 18, 45, 80], "agente": ["A"] * 9}).to_excel(workbook, index=False)
    workbook.seek(0)
    client = app.test_client()
    upload = client.post("/subir", data={"archivo": (workbook, "llamadas.xlsx")}, content_type="multipart/form-data")
    assert upload.status_code == 302
    response = client.post("/analisis/distribucion", data={"wait_column": "tiempo_espera", "target": "20", "target_direction": "maximum", "variable_label": "Tiempo de espera", "unit": "segundos"})
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Histograma de Tiempo de espera" in page
    assert "P95" in page
    assert "Asimetría positiva" in page


def test_distribution_works_for_sales_data():
    result = analyze_distribution(pd.Series([100, 110, 120, 130, 900]), 150, "maximum", "Ventas")
    assert result["mean"] > result["median"]
    assert "Ventas" in result["explanation"]
