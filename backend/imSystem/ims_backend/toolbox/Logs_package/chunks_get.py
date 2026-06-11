from ims_backend.models import LogAuditoria
from django.http import StreamingHttpResponse
import json
def get_by_chunks()->StreamingHttpResponse:
    def generate():
        for log in LogAuditoria.objects.all().iterator(chunk_size=50):
            yield json.dumps({
                "id":log.id,
                "tipo":log.tipo,
                "atencion_id":log.atencion_id if log.atencion else None,
                "usuario": log.usuario.id,
                "rut":log.rut_usuario,
                "descripcion": log.descripcion,
                "created_at": log.timestamp.isoformat() if log.timestamp else None
            })
    
    return StreamingHttpResponse(generate(), content_type='application/x-ndjson')