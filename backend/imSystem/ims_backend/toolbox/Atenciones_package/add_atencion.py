from django.db import transaction
from ims_backend.toolbox import exceptions
from ims_backend.serializers import PayloadSerializer
from ims_backend.models import (Despacho, Ambulancia, Atencion, SignosVitales,
    Cronologia, DetalleInsumoAtencion, PreInforme, StockInsumo, Documento, Paciente)
from django.shortcuts import get_object_or_404
from django.forms.models import model_to_dict
from ims_backend.task_package.task_s3 import enviar_s3
from ims_backend.task_package.task_log_atencion import agregar_log_atencion
import logging
import json
import base64
from ims_backend.toolbox.customencoder import CustomEncoder
from django.db.models import F
import rustjson
from ims_backend.task_package.task_notificaciones import notificacion
from ims_backend.toolbox.Despachos_package.change_status import change_despacho_status


_PATIENT_UPDATE_FIELDS = ["fecha_nacimiento", "condicion_paciente", "telefono"]


def _actualizar_paciente(temp, paciente_data):
    fields_to_update = []
    for field in _PATIENT_UPDATE_FIELDS:
        value = paciente_data.get(field)
        if value not in (None, ""):
            setattr(temp, field, value)
            fields_to_update.append(field)
    if fields_to_update:
        temp.save(update_fields=fields_to_update)


def _crear_atencion(ambulancia, despacho, despacho_data, user, rut_receptor):
    return Atencion.objects.create(
        ambulancia=ambulancia,
        despacho=despacho,
        hora_salida=despacho_data['hora_salida'],
        hora_llegada=despacho_data.get('hora_llegada'),
        rut_registrador=user,
        rut_receptor=rut_receptor,
    )


def _registrar_signos_vitales(atencion, svd):
    SignosVitales.objects.bulk_create([SignosVitales(atencion=atencion, **sv) for sv in svd])


def _registrar_preinforme(atencion, preinforme_data):
    return PreInforme.objects.create(
        atencion=atencion,
        pre_informe=preinforme_data['pre_informe'],
        motivo_llamado=preinforme_data['motivo_llamado'],
        estado_paciente=preinforme_data['estado_paciente'],
    )


def _registrar_cronologia(atencion, cronologia_data):
    return Cronologia.objects.create(
        atencion=atencion,
        hora_llamada=cronologia_data['hora_llamada'],
        despacho_movil=cronologia_data['despacho_movil'],
        llegada_qth1=cronologia_data['llegada_qth1'],
        salida_qth1=cronologia_data['salida_qth1'],
        llegada_qth2=cronologia_data['llegada_qth2'],
        salida_qth2=cronologia_data['salida_qth2'],
        categoria=cronologia_data['categoria'],
    )


def _procesar_insumos(atencion, insumos_data, ambulancia):
    ids_presentaciones = [item['presentacion_id'] for item in insumos_data]
    stock_locked = {
        i.presentacion_id: i
        for i in StockInsumo.objects.select_for_update().filter(
            presentacion__id__in=ids_presentaciones, ambulancia=ambulancia
        )
    }
    for presentacion in insumos_data:
        insumo = stock_locked[presentacion["presentacion_id"]]
        if insumo.stock < presentacion["cantidad_usada"]:
            raise exceptions.ConflictException
    for presentacion in insumos_data:
        StockInsumo.objects.filter(
            presentacion__id=presentacion["presentacion_id"], ambulancia=ambulancia
        ).update(stock=F('stock') - presentacion["cantidad_usada"])
        DetalleInsumoAtencion.objects.bulk_create([DetalleInsumoAtencion(
            atencion=atencion,
            insumo_id=presentacion["presentacion_id"],
            observaciones=presentacion["observaciones"],
            cantidad_usada=presentacion["cantidad_usada"],
        )])


def _construir_documento(atencion, user, despacho, pre, crono):
    return {
        "atencion": model_to_dict(atencion),
        "paciente": {
            "nombre_completo": despacho.paciente.nombre_completo,
            "rut": despacho.paciente.rut,
        },
        "registrado_por": {
            "nombre_completo": user.full_name,
            "rut": user.rut,
            "rol": user.rol.nombre_rol,
        },
        "recibido_por": atencion.rut_receptor,
        "signos_vitales": list(SignosVitales.objects.filter(atencion=atencion).values(
            'id', 'atencion_id', 'timestamp', 'presion_sistolica', 'presion_diastolica',
            'frecuencia_cardiaca', 'saturacion_oxigeno', 'temperatura', 'fr', 'fio2',
            'hgt', 'gcs', 'eva', 'hora', 'observaciones',
        )),
        "preinforme": model_to_dict(pre),
        "cronologia": model_to_dict(crono),
        "insumos_utilizados": list(
            DetalleInsumoAtencion.objects.filter(atencion=atencion)
            .values('insumo__insumo__nombre_insumo', 'cantidad_usada', 'observaciones')
        ),
    }


def _firmar_documento(atencion, document):
    prepared_data = json.dumps(document, sort_keys=True, ensure_ascii=False, cls=CustomEncoder).encode('utf-8')
    hash_bytes, signature = rustjson.data(prepared_data)
    document["Hash"] = hash_bytes.hex()
    document["Firma"] = base64.b64encode(signature).decode()
    atencion.sello_electronico = f"{hash_bytes.hex()}:{base64.b64encode(signature).decode()}"
    atencion.estado_sello = "Firmado"
    atencion.save(update_fields=["sello_electronico", "estado_sello"])
    Documento.objects.create(
        archivo_s3_key=f"documentos/{document['Hash']}.json",
        firma_s3_key=f"documentos/{document['Hash']}.sig",
        archivo_hash=hash_bytes.hex(),
        atencion=atencion,
    )
    return hash_bytes, signature


def _preparar_contexto(data):
    serializer = PayloadSerializer(data=data)
    if not serializer.is_valid():
        raise exceptions.BadRequestException(detail=serializer.errors)

    valid_data    = serializer.validated_data
    despacho_data = valid_data['despacho']
    paciente_data = valid_data["paciente"]

    despacho   = get_object_or_404(Despacho,   id=despacho_data['despacho_id'])
    ambulancia = get_object_or_404(Ambulancia, id=despacho_data['ambulancia_id'])
    temp       = Paciente.objects.only("fecha_nacimiento", "telefono", "condicion_paciente").get(rut=paciente_data["rut"])

    if despacho.estado not in (Despacho.ASIGNADO, Despacho.EMERGENCIA):
        raise exceptions.ConflictException(detail="El despacho no está en un estado válido para registrar una atención")
    if Atencion.objects.filter(despacho=despacho).exists():
        raise exceptions.ConflictException(detail="Esta atencion ya fue despachada")

    return {
        "despacho":      despacho,
        "ambulancia":    ambulancia,
        "temp":          temp,
        "paciente_data": paciente_data,
        "despacho_data": despacho_data,
        "svd":           valid_data['signos_vitales'],
        "preinforme":    valid_data['preinforme'],
        "cronologia":    valid_data['cronologia'],
        "insumos":       valid_data['insumos_utilizados'],
        "rut_receptor":  valid_data['rut_receptor'],
    }


def _ejecutar_transaccion(despacho, ambulancia, temp, paciente_data, despacho_data,
                          svd, preinforme, cronologia, insumos, rut_receptor, user):
    with transaction.atomic():
        _actualizar_paciente(temp, paciente_data)

        atencion = _crear_atencion(ambulancia, despacho, despacho_data, user, rut_receptor)
        _registrar_signos_vitales(atencion, svd)
        pre   = _registrar_preinforme(atencion, preinforme)
        crono = _registrar_cronologia(atencion, cronologia)
        _procesar_insumos(atencion, insumos, ambulancia)

        document = _construir_documento(atencion, user, despacho, pre, crono)
        hash_bytes, signature = _firmar_documento(atencion, document)

        change_despacho_status(type=Despacho.FINALIZADO, despacho=despacho)

        file_json = json.dumps(document, ensure_ascii=False, cls=CustomEncoder)
        sig_b64   = base64.b64encode(signature).decode()
        hash_hex  = hash_bytes.hex()

        transaction.on_commit(lambda: enviar_s3.delay(file_json, hash_hex, sig_b64))
        transaction.on_commit(lambda: agregar_log_atencion.delay(documento=document))
        transaction.on_commit(lambda: notificacion.delay(Atencion.REGISTRADA, fecha=str(despacho.fecha_finalizacion)))

    return hash_hex


import logging
logger = logging.getLogger(__name__)


def add_atencion(data, user):
    logger.error(f"PAYLOAD RECIBIDO: {data}")
    contexto = _preparar_contexto(data)
    try:
        hash_hex = _ejecutar_transaccion(**contexto, user=user)
    except ValueError as ve:
        raise exceptions.BadRequestException(detail=str(ve))
    except Exception as e:
        logger.error(f"ERROR EN ATENCION: {e}", exc_info=True)
        raise exceptions.InternalServerException(detail=str(e))
    return {"success": "Succeeded", "hash": hash_hex}
