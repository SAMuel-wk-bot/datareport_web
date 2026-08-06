from datetime import datetime, timedelta, timezone

import pyotp
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from flask_mail import Message
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db, limiter, mail
from models import AuditEvent, User
from security import decrypt_value, encrypt_value, validate_password, verify_captcha

auth_bp = Blueprint("auth", __name__, url_prefix="/cuenta")


def _token(email, purpose):
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"]).dumps(email, salt=purpose)


def _read_token(token, purpose, max_age=3600):
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"]).loads(token, salt=purpose, max_age=max_age)


def _send_email(subject, recipient, body):
    if current_app.config.get("MAIL_SUPPRESS_SEND"):
        current_app.logger.info("Correo local para %s: %s", recipient, body)
        return
    mail.send(Message(subject=subject, recipients=[recipient], body=body))


def _audit(event, user_id=None):
    db.session.add(AuditEvent(user_id=user_id, event=event, ip_address=request.remote_addr))
    db.session.commit()


@auth_bp.route("/registro", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        errors = validate_password(password)
        if not verify_captcha(request.form.get("cf-turnstile-response")):
            errors.append("No fue posible validar el CAPTCHA.")
        if not name or "@" not in email:
            errors.append("Nombre y correo electrónico son obligatorios.")
        if User.query.filter_by(email=email).first():
            errors.append("Ya existe una cuenta con ese correo.")
        if errors:
            return render_template("auth/register.html", errors=errors), 400
        user = User(email=email, display_name=name, password_hash=generate_password_hash(password, method="scrypt"))
        db.session.add(user)
        db.session.commit()
        link = url_for("auth.verify_email", token=_token(email, "verify-email"), _external=True)
        _send_email("Verifica tu cuenta DataReport", email, f"Confirma tu cuenta: {link}")
        _audit("account_registered", user.id)
        flash("Cuenta creada. Revisa tu correo para verificarla.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", errors=[])


@auth_bp.route("/verificar/<token>")
def verify_email(token):
    try:
        email = _read_token(token, "verify-email", 86400)
    except (BadSignature, SignatureExpired):
        flash("El enlace de verificación no es válido o venció.", "error")
        return redirect(url_for("auth.login"))
    user = User.query.filter_by(email=email).first_or_404()
    user.email_verified = True
    db.session.commit()
    _audit("email_verified", user.id)
    flash("Correo verificado. Ya puedes iniciar sesión.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/ingresar", methods=["GET", "POST"])
@limiter.limit("10 per 15 minutes")
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        now = datetime.now(timezone.utc)
        if user and user.locked_until and user.locked_until > now:
            return render_template("auth/login.html", error="Cuenta bloqueada temporalmente."), 429
        if not user or not check_password_hash(user.password_hash, request.form.get("password", "")):
            if user:
                user.failed_logins += 1
                if user.failed_logins >= 5:
                    user.locked_until = now + timedelta(minutes=15)
                    user.failed_logins = 0
                db.session.commit()
            return render_template("auth/login.html", error="Credenciales incorrectas."), 401
        if not user.email_verified and not current_app.config.get("ALLOW_UNVERIFIED_LOGIN"):
            return render_template("auth/login.html", error="Debes verificar tu correo antes de ingresar."), 403
        if user.two_factor_enabled:
            session["pending_2fa_user"] = user.id
            return redirect(url_for("auth.two_factor_login"))
        user.failed_logins = 0
        user.locked_until = None
        db.session.commit()
        login_user(user)
        _audit("login_success", user.id)
        return redirect(url_for("dashboard"))
    return render_template("auth/login.html", error=None)


@auth_bp.route("/segundo-factor", methods=["GET", "POST"])
@limiter.limit("10 per 15 minutes")
def two_factor_login():
    user = db.session.get(User, session.get("pending_2fa_user"))
    if not user:
        return redirect(url_for("auth.login"))
    if request.method == "POST" and pyotp.TOTP(decrypt_value(user.totp_secret_encrypted)).verify(request.form.get("code", ""), valid_window=1):
        session.pop("pending_2fa_user", None)
        login_user(user)
        _audit("login_2fa_success", user.id)
        return redirect(url_for("dashboard"))
    return render_template("auth/two_factor.html", setup=False, secret=None, error="Código inválido." if request.method == "POST" else None)


@auth_bp.route("/activar-2fa", methods=["GET", "POST"])
@login_required
def enable_two_factor():
    secret = session.setdefault("new_totp_secret", pyotp.random_base32())
    if request.method == "POST":
        if not pyotp.TOTP(secret).verify(request.form.get("code", ""), valid_window=1):
            return render_template("auth/two_factor.html", setup=True, secret=secret, error="Código inválido."), 400
        current_user.totp_secret_encrypted = encrypt_value(secret)
        current_user.two_factor_enabled = True
        db.session.commit()
        session.pop("new_totp_secret", None)
        _audit("two_factor_enabled", current_user.id)
        flash("Verificación en dos pasos activada.", "success")
        return redirect(url_for("dashboard"))
    return render_template("auth/two_factor.html", setup=True, secret=secret, error=None)


@auth_bp.route("/recuperar", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            link = url_for("auth.reset_password", token=_token(email, "reset-password"), _external=True)
            _send_email("Recupera tu contraseña DataReport", email, f"Crea una nueva contraseña: {link}")
        flash("Si la cuenta existe, recibirás un enlace de recuperación.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot.html")


@auth_bp.route("/restablecer/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = _read_token(token, "reset-password", 3600)
    except (BadSignature, SignatureExpired):
        return render_template("auth/reset.html", errors=["El enlace no es válido o venció."]), 400
    if request.method == "POST":
        errors = validate_password(request.form.get("password", ""))
        if errors:
            return render_template("auth/reset.html", errors=errors), 400
        user = User.query.filter_by(email=email).first_or_404()
        user.password_hash = generate_password_hash(request.form["password"], method="scrypt")
        db.session.commit()
        _audit("password_reset", user.id)
        flash("Contraseña actualizada.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset.html", errors=[])


@auth_bp.route("/salir", methods=["POST"])
@login_required
def logout():
    user_id = current_user.id
    logout_user()
    _audit("logout", user_id)
    return redirect(url_for("auth.login"))
