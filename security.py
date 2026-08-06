import base64
import os
import re

import requests
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app, request


def validate_password(password):
    errors = []
    if len(password) < 12:
        errors.append("Debe contener al menos 12 caracteres.")
    if not re.search(r"[A-Z]", password):
        errors.append("Debe incluir una mayúscula.")
    if not re.search(r"[a-z]", password):
        errors.append("Debe incluir una minúscula.")
    if not re.search(r"\d", password):
        errors.append("Debe incluir un número.")
    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append("Debe incluir un símbolo.")
    return errors


def _fernet():
    try:
        return Fernet(current_app.config["DATA_ENCRYPTION_KEY"].encode())
    except (ValueError, TypeError) as exc:
        raise RuntimeError("DATA_ENCRYPTION_KEY debe ser una clave Fernet válida.") from exc


def encrypt_value(value):
    return _fernet().encrypt(value.encode()).decode()


def decrypt_value(value):
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("No fue posible descifrar el valor protegido.") from exc


def verify_captcha(token):
    secret = current_app.config.get("TURNSTILE_SECRET_KEY")
    if not secret:
        return current_app.config.get("ALLOW_LOCAL_CAPTCHA_BYPASS", False)
    if not token:
        return False
    response = requests.post(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data={"secret": secret, "response": token, "remoteip": request.remote_addr},
        timeout=5,
    )
    return bool(response.ok and response.json().get("success"))


def development_fernet_key():
    seed = os.environ.get("SECRET_KEY", "development-only-change-me").encode()[:32].ljust(32, b"0")
    return base64.urlsafe_b64encode(seed).decode()
