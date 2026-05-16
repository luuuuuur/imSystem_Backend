import pyotp
#funcion auxiliar de autenticacion
def authentication(user_key, user_input):
    totp = pyotp.TOTP(user_key)
    return bool(totp.verify(user_input))