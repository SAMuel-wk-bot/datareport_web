
import io

import pandas as pd

from app import app
from extensions import db
from pdf_reports import build_dataset_pdf


def test_pdf_has_valid_signature():
    pdf = build_dataset_pdf(pd.DataFrame({"Categoría": ["A", "B"], "Total": [10, 20]}), "Reporte de prueba", "Analista")
    assert pdf.read(5) == b"%PDF-"


def test_register_login_and_dashboard(tmp_path):
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SQLALCHEMY_DATABASE_URI=f"sqlite:///{tmp_path / 'test.db'}", ALLOW_LOCAL_CAPTCHA_BYPASS=True, ALLOW_UNVERIFIED_LOGIN=True)
    with app.app_context():
        db.drop_all()
        db.create_all()
    client = app.test_client()
    response = client.post("/cuenta/registro", data={"display_name": "Analista", "email": "analista@example.com", "password": "ClaveSegura#2026", "password_confirmation": "ClaveSegura#2026", "cf-turnstile-response": "local"})
    assert response.status_code == 302
    response = client.post("/cuenta/ingresar", data={"email": "analista@example.com", "password": "ClaveSegura#2026"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    assert client.get("/panel").status_code == 200


def test_guest_can_open_main_page():
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    client = app.test_client()
    assert client.get("/").status_code == 200
    assert client.get("/panel").status_code == 302


def test_guest_can_upload_and_analyze_csv():
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    client = app.test_client()
    response = client.post("/subir", data={"archivo": (io.BytesIO(b"categoria,total\nA,20\nB,30\n"), "datos.csv")}, content_type="multipart/form-data")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/analisis")
    assert client.get("/analisis").status_code == 200


def test_password_confirmation_is_required():
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, ALLOW_LOCAL_CAPTCHA_BYPASS=True)
    response = app.test_client().post("/cuenta/registro", data={"display_name": "Prueba", "email": "otra@example.com", "password": "ClaveSegura#2026", "password_confirmation": "Distinta#2026", "cf-turnstile-response": "local"})
    assert response.status_code == 400
    assert "no coinciden" in response.get_data(as_text=True)
