from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
import os
from pathlib import Path
from dotenv import load_dotenv
from cryptography.hazmat.backends import default_backend

BASE_DIR = Path(__file__).resolve().parent.parent
if os.path.exists(BASE_DIR / 'id_ed25519.pem'):
    raise RuntimeError("Clave ya existe, no sobreescribir")
load_dotenv(BASE_DIR / '.mikufile')
private_key = ed25519.Ed25519PrivateKey.generate()
public_key = private_key.public_key()


DIR = Path(__file__).resolve().parent
load_dotenv(DIR / ".mikufile")
pwd = os.getenv("PASSWORD_KEY")
if pwd is None:
    raise ValueError("NO SE ENCONTRO EL PASSWORD_KEY EN EL .MIKUFILE")
pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format= serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.BestAvailableEncryption(pwd.encode("utf-8"))
)

pub = public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)
with open('id_ed25519.pem', 'wb')as f:
    f.write(pem)

with open('id_ed25519.pub', 'wb')as f:
    f.write(pub)

os.chmod("id_ed25519.pem", 0o400)
