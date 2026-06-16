from django.contrib.auth import authenticate, login
from ims_backend.toolbox.exceptions import UnAuthorizedException
from ims_backend.totp_auth.authentication import authentication
from ims_backend.models import Personal
def autenticar(request, data):
    user = authenticate(username=data["username"], password=data["password"])
    if user is None:
        raise UnAuthorizedException(detail="Credenciales incorrectas")
    if not user.is_active:
        raise UnAuthorizedException(detail="Usuario inactivo")
    request.session['pre_auth_user_id'] = user.id
    return True

def iniciar_sesion(request, data):
    user_id = request.session.get('pre_auth_user_id')
    user_data = Personal.objects.get(id=user_id)
    if not authentication(user_data.totp_secret, data["totp_code"]):
        raise UnAuthorizedException(detail="Código TOTP incorrecto")
    
    login(request, user_data)
    request.session.pop('pre_auth_user_id', None)
    request.session['mfa_verified'] = True
    request.session.save()
    
    return {
        "session": request.session.session_key,
        "user_data": {
            "role": user_data.rol.nombre_rol,
            "first_name": user_data.first_name,
            "last_name": user_data.last_name
        }
    }