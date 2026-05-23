from django.db import transaction
import exceptions
from ims_backend.serializers import PayloadSerializer
from ims_backend.models import *
from django.shortcuts import get_object_or_404
from django.forms.models import model_to_dict
from ims_backend.tasks.task_s3 import enviar_s3
import json
import base64
import rustjson
from customencoder import CustomEncoder
from django.db.models   import F
import rustjson
def add_atencion(request):
    serializer = PayloadSerializer(data=request.data)
    if serializer.is_valid():
        valid_data = serializer.validated_data
        svd = valid_data['signos_vitales']
        preinforme_data = valid_data['preinforme']
        cronologia_data = valid_data['cronologia']
        insumos_data = valid_data['insumos_utilizados']
        despacho_data = valid_data['despacho']
        despacho = get_object_or_404(Despacho, id=despacho_data['despacho_id'])
        ambulancia = get_object_or_404(Ambulancia, id=despacho_data['ambulancia_id'])
        if despacho.estado != "asignado":
            raise exceptions.ConflictException(detail="Ya existe el despacho")
        if Atencion.objects.filter(despacho=despacho).exists():
            raise exceptions.ConflictException(detail="Esta atencion ya fue despachada")
        try:
            with transaction.atomic():
                atencion = Atencion.objects.create(
                    ambulancia=ambulancia, despacho=despacho,
                    hora_salida=despacho_data['hora_salida'],
                    hora_llegada=despacho_data['hora_llegada']
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
                ids_insumos = [item['insumo_id'] for item in insumos_data]
                insumos_locked = {i.id: i for i in InsumoMedico.objects.select_for_update().filter(id__in=ids_insumos)}
                for insumo_data in insumos_data:
                    insumo = insumos_locked[insumo_data['insumo_id']]
                    if insumo.stock_total < insumo_data['dosis']:
                        raise ValueError(f"Stock insuficiente para {insumo.nombre_insumo}")
                for insumo_data in insumos_data:
                    InsumoMedico.objects.filter(id=insumo_data['insumo_id']).update(
                        stock_total=F('stock_total') - insumo_data['dosis']
                    )
                    DetalleInsumoAtencion.objects.create(
                        atencion=atencion,
                        insumo_id=insumo_data['insumo_id'],
                        dosis=insumo_data['dosis'],
                        observaciones=insumo_data['observaciones']
                    )
                document = {
                    "atencion": model_to_dict(atencion),
                    "paciente": {
                        "nombre_completo": despacho.paciente.nombre_completo,
                        "rut": despacho.paciente.rut
                    },
                    "registrado_por": {
                        "nombre_completo": request.user.full_name,
                        "rut": request.user.rut,
                        "rol": request.user.rol.nombre_rol
                    },
                    "signos_vitales": list(SignosVitales.objects.filter(atencion=atencion).values(
                        'id', 'atencion_id', 'timestamp', 'presion_sistolica', 'presion_diastolica',
                        'frecuencia_cardiaca', 'saturacion_oxigeno', 'temperatura', 'fr', 'fio2',
                        'hgt', 'gcs', 'eva', 'hora', 'observaciones'
                    )),
                    "preinforme": model_to_dict(pre),
                    "cronologia": model_to_dict(crono),
                    "insumos_utilizados": list(DetalleInsumoAtencion.objects.filter(atencion=atencion)
                                               .values('insumo__nombre_insumo', 'dosis', 'observaciones')),
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
                despacho.estado = "finalizado"
                despacho.save(update_fields=["estado"])
        except ValueError as ve:
            raise exceptions.BadRequest(detail=str(ve))
        except Exception as e:
            raise exceptions.InternalServerException(detail=str(e))
        try:
            file_json = json.dumps(document, ensure_ascii=False, cls=CustomEncoder)
            enviar_s3.delay(file_json, hash_bytes.hex(), base64.b64encode(signature).decode())
            return {"success": "Succeeded", "hash": hash_bytes.hex()}
        except Exception:
            raise exceptions.InternalServerException(detail="Failed to upload to S3")
    else:
        raise exceptions.InternalServerException(detail="Serializer Error")