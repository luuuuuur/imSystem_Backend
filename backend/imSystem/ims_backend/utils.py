import pyotp
import secrets
import string

def generate_password():
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(16))
def generate_totp():
    key = pyotp.random_base32()
    totp = pyotp.TOTP(key)
    return (key, totp)