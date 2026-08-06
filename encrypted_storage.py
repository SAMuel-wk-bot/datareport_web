import os
import tempfile
from contextlib import contextmanager

from security import _fernet


def encrypt_file(path):
    encrypted_path = f"{path}.enc"
    with open(path, "rb") as source:
        encrypted = _fernet().encrypt(source.read())
    with open(encrypted_path, "wb") as target:
        target.write(encrypted)
    os.remove(path)
    return encrypted_path


@contextmanager
def decrypted_file(path, suffix):
    if not path.endswith(".enc"):
        yield path
        return
    with open(path, "rb") as source:
        content = _fernet().decrypt(source.read())
    descriptor, temporary_path = tempfile.mkstemp(prefix="datareport_", suffix=suffix)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(content)
        yield temporary_path
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)
