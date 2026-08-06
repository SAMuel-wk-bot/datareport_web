import io

import pandas as pd

from app import app
from extensions import db
from models import User
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
    response = client.post("/cuenta/registro", data={"display_name": "Analista", "email": "analista@example.com", "password": "ClaveSegura#2026", "cf-turnstile-response": "local"})
    assert response.status_code == 302
    response = client.post("/cuenta/ingresar", data={"email": "analista@example.com", "password": "ClaveSegura#2026"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/panel")
    assert client.get("/panel").status_code == 200
