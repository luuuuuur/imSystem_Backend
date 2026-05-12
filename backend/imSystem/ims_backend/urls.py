from django.urls import path
from .views import *
urlpatterns = [
    path("api/login/", Login.as_view(), name="Login"),
    path("api/allpersonal/",DataPersonal.as_view(), name="allpersonal"),
    path("api/registroPacientes/", RegistrosPacientesAPI.as_view(),name="RegistroPacientesAPI"),
    path("api/suscribirAgrupo/",Grupos.as_view(),name="Grupos"),
    path("api/suscribirAgrupo/AddMember/", AddMemberToGroup.as_view(), name="AddMemberToGroup"),
    path("api/despachos/create/",CreateDespacho.as_view(), name="CreateDespacho"),
    path("api/despachos/asignar/",AsignarDespacho.as_view(), name="AsignarDespacho"),
    path("api/despachos/get/", DespachoUsuarioAPI.as_view(), name="DespachoUsuarioAPI"),
    path("api/ambulancias/", AmbulanciaAPI.as_view(), name="AmbulanciaAPI"),
    path("api/atenciones/", AtencionAPI.as_view(), name="AtencionAPI"),
    path("api/atenciones/<int:id>/", AtencionDetalleAPI.as_view(), name="AtencionDetalleAPI"),
    path("api/register/worker/", DataPersonal.as_view(), name="DataPersonal"),
]

