from django.contrib.auth import authenticate, login
from ims_backend.toolbox.exceptions import UnauthorizedException
from ims_backend.totp_auth.authentication import authentication
from ims_backend.models import Personal
def autenticar(request, data):
    user = authenticate(username=data["username"], password=data["password"])
    if user is None:
        raise UnauthorizedException(detail="Credenciales incorrectas")
    if not user.is_active:
        raise UnauthorizedException(detail="Usuario inactivo")
    request.session['pre_auth_user_id'] = user.id
    return True

def iniciar_sesion(request, data):
    user_id = request.session.get('pre_auth_user_id')
    user_data = Personal.objects.get(id=user_id)
    if not authentication(user_data.totp_secret, data["totp_code"]):
        raise UnauthorizedException(detail="Código TOTP incorrecto")
    
    login(request, user_data)
    del request.session['pre_auth_user_id']
    request.session['mfa_verified'] = True
    request.session.save()
    
    return {
        "session": request.session.session_key,
        "user_data": {
            "role": user.rol.nombre_rol,
            "first_name": user.first_name,
            "last_name": user.last_name
        }
    }