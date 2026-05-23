from django.urls import path
from .views import *
urlpatterns = [
    path("api/login/", Login.as_view(), name="Login"),
    path("api/personal/",DataPersonal.as_view(), name="DataPersonal"),
    path("api/pacientes/", RegistrosPacientesAPI.as_view(),name="RegistroPacientesAPI"),
    path("api/grupo/",Grupos.as_view(),name="Grupos"),
    path("api/grupo/suscribir/", AddMemberToGroup.as_view(), name="AddMemberToGroup"),
    path("api/despachos/add/",CreateDespacho.as_view(), name="CreateDespacho"),
    path("api/despachos/asignar/",AsignarDespacho.as_view(), name="AsignarDespacho"),
    path("api/despachos/get/", DespachoASolicitudUsuario.as_view(), name="DespachoUsuarioAPI"),
    path("api/despachos/getall/", AllDespachos.as_view(), name="AllDespachos"),
    path("api/ambulancias/", AmbulanciaAPI.as_view(), name="AmbulanciaAPI"),
    path("api/atenciones/", RetornarAtencionAPI.as_view(), name="AtencionAPI"),
    path("api/inv/get/", InsumosAPI.as_view(),name="InsumosAPI"),
    path("api/atenciones/add/", RegistroAtencionAPI.as_view(), name="RegistroAtencionAPI"),
]

