from django.db import transaction
from ims_backend.toolbox import exceptions
from ims_backend.serializers import PayloadSerializer
from ims_backend.models import (Despacho,Ambulancia,Atencion,SignosVitales,
Cronologia,DetalleInsumoAtencion,PreInforme,StockInsumo,Documento, Paciente)
from django.shortcuts import get_object_or_404
from django.forms.models import model_to_dict
from ims_backend.task_package.task_s3 import enviar_s3
from ims_backend.task_package.task_log_atencion import agregar_log_atencion
import json
import base64
from ims_backend.toolbox.customencoder import CustomEncoder
from django.db.models   import F
import rustjson
from ims_backend.task_package.task_notificaciones import notificacion
from ims_backend.toolbox.Despachos_package.change_status import change_despacho_status
def add_atencion(data, user):
    serializer = PayloadSerializer(data=data)
    if serializer.is_valid():
        valid_data = serializer.validated_data
        paciente = valid_data["paciente"]
        svd = valid_data['signos_vitales']
        preinforme_data = valid_data['preinforme']
        cronologia_data = valid_data['cronologia']
        insumos_data = valid_data['insumos_utilizados']
        despacho_data = valid_data['despacho']
        despacho = get_object_or_404(Despacho, id=despacho_data['despacho_id'])
        ambulancia = get_object_or_404(Ambulancia, id=despacho_data['ambulancia_id'])
        #se obtiene paciente para editar datos en caso de que vengan
        temp = Paciente.objects.only("fecha_nacimiento","telefono","condicion_paciente").get(rut=paciente["rut"])

        if despacho.estado not in (Despacho.ASIGNADO, Despacho.EMERGENCIA):
            raise exceptions.ConflictException(detail="El despacho no está en un estado válido para registrar una atención")
        if Atencion.objects.filter(despacho=despacho).exists():
            raise exceptions.ConflictException(detail="Esta atencion ya fue despachada")
        try:
            with transaction.atomic():
                temp.fecha_nacimiento = paciente["fecha_nacimiento"]
                temp.condicion_paciente = paciente["condicion_paciente"]
                temp.telefono = paciente["telefono"]
                temp.save(update_fields=["fecha_nacimiento", "condicion_paciente", "telefono"])

                atencion = Atencion.objects.create(
                    ambulancia=ambulancia, despacho=despacho,
                    hora_salida=despacho_data['hora_salida'],
                    hora_llegada=despacho_data.get('hora_llegada'),
                    rut_registrador=user, rut_receptor=valid_data["rut_receptor"]
                )

                SignosVitales.objects.bulk_create([SignosVitales(atencion=atencion, **sv) for sv in svd])
                pre = PreInforme.objects.create(
                    atencion=atencion,
                    pre_informe=preinforme_data['pre_informe'],
                    motivo_llamado=preinforme_data['motivo_llamado'],
                    estado_paciente=preinforme_data['estado_paciente']
                )
                crono = Cronologia.objects.create(
                    atencion=atencion,
                    hora_llamada=cronologia_data['hora_llamada'],
                    despacho_movil=cronologia_data['despacho_movil'],
                    llegada_qth1=cronologia_data['llegada_qth1'],
                    salida_qth1=cronologia_data['salida_qth1'],
                    llegada_qth2=cronologia_data['llegada_qth2'],
                    salida_qth2=cronologia_data['salida_qth2'],
                    categoria=cronologia_data['categoria']
                )
                ids_presentaciones = [item['presentacion_id'] for item in insumos_data]
                stock_locked = {i.presentacion_id: i for i in StockInsumo.objects.select_for_update().filter(presentacion__id__in=ids_presentaciones, ambulancia=ambulancia)}
                
                for presentacion in insumos_data:
                    insumo = stock_locked[presentacion["presentacion_id"]]
                    if insumo.stock < presentacion["cantidad_usada"]:
                        raise exceptions.ConflictException
                for presentacion in insumos_data:
                    StockInsumo.objects.filter(presentacion__id = presentacion["presentacion_id"], ambulancia=ambulancia).update(stock=F('stock') - presentacion["cantidad_usada"])
                    DetalleInsumoAtencion.objects.bulk_create([DetalleInsumoAtencion(
                        atencion=atencion,
                        insumo_id=presentacion["presentacion_id"],
                        observaciones=presentacion["observaciones"],
                        cantidad_usada=presentacion["cantidad_usada"]
                    )])
                document = {
                    "atencion": model_to_dict(atencion),
                    "paciente": {
                        "nombre_completo": despacho.paciente.nombre_completo,
                        "rut": despacho.paciente.rut
                    },
                    "registrado_por": {
                        "nombre_completo": user.full_name,
                        "rut": user.rut,
                        "rol": user.rol.nombre_rol
                    },
                    "recibido_por":atencion.rut_receptor,
                    "signos_vitales": list(SignosVitales.objects.filter(atencion=atencion).values(
                        'id', 'atencion_id', 'timestamp', 'presion_sistolica', 'presion_diastolica',
                        'frecuencia_cardiaca', 'saturacion_oxigeno', 'temperatura', 'fr', 'fio2',
                        'hgt', 'gcs', 'eva', 'hora', 'observaciones'
                    )),
                    "preinforme": model_to_dict(pre),
                    "cronologia": model_to_dict(crono),
                    "insumos_utilizados": list(DetalleInsumoAtencion.objects.filter(atencion=atencion)
                                               .values('insumo__insumo__nombre_insumo', 'cantidad_usada', 'observaciones')),
                }
                prepared_data = json.dumps(document, sort_keys=True, ensure_ascii=False, cls=CustomEncoder).encode('utf-8')
                hash_bytes, signature = rustjson.data(prepared_data)
                document["Hash"] = hash_bytes.hex()
                document["Firma"] = base64.b64encode(signature).decode()
                s3_key_json = f"documentos/{document['Hash']}.json"
                s3_key_sig = f"documentos/{document['Hash']}.sig"
                atencion.sello_electronico = f"{hash_bytes.hex()}:{base64.b64encode(signature).decode()}"
                atencion.estado_sello = "Firmado"
                atencion.save(update_fields=["sello_electronico", "estado_sello"])
                Documento.objects.create(
                    archivo_s3_key=s3_key_json,
                    firma_s3_key=s3_key_sig,
                    archivo_hash=hash_bytes.hex(),
                    atencion=atencion
                )
                change_despacho_status(type=Despacho.FINALIZADO,despacho=despacho)
                file_json = json.dumps(document, ensure_ascii=False, cls=CustomEncoder)
                sig_b64   = base64.b64encode(signature).decode()
                hash_hex  = hash_bytes.hex()
                transaction.on_commit(lambda: enviar_s3.delay(file_json, hash_hex, sig_b64))
                transaction.on_commit(lambda: agregar_log_atencion.delay(documento=document))
                transaction.on_commit(lambda: notificacion.delay(Atencion.REGISTRADA, fecha=str(despacho.fecha_finalizacion)))
        except ValueError as ve:
            raise exceptions.BadRequestException(detail=str(ve))
        except Exception as e:
            raise exceptions.InternalServerException(detail=str(e))
        return {"success": "Succeeded", "hash": hash_bytes.hex()}
    else:
        raise exceptions.BadRequestException(detail=serializer.errors)