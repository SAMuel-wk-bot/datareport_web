from cryptography.fernet import Fernet

from app import app
from encrypted_storage import decrypted_file, encrypt_file


def test_security_headers_present():
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    response = app.test_client().get("/cuenta/ingresar")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "object-src 'none'" in response.headers["Content-Security-Policy"]


def test_encrypted_storage_round_trip(tmp_path):
    app.config.update(DATA_ENCRYPTION_KEY=Fernet.generate_key().decode())
    source = tmp_path / "datos.csv"
    source.write_bytes(b"nombre,total\nA,20\n")
    with app.app_context():
        encrypted = encrypt_file(str(source))
        assert not source.exists()
        with open(encrypted, "rb") as encrypted_file:
            assert b"nombre,total" not in encrypted_file.read()
        with decrypted_file(encrypted, ".csv") as clear_path, open(clear_path, "rb") as clear_file:
            assert clear_file.read() == b"nombre,total\nA,20\n"
