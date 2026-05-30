import uuid
from datetime import datetime

from django.db.models import Prefetch

# CAMBIO: Todos los imports ahora usan el módulo R4B
from fhir.resources.R4B.address import Address
from fhir.resources.R4B.bundle import Bundle, BundleEntry, BundleEntryRequest
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.contactpoint import ContactPoint
from fhir.resources.R4B.encounter import Encounter, EncounterParticipant
from fhir.resources.R4B.humanname import HumanName
from fhir.resources.R4B.identifier import Identifier
from fhir.resources.R4B.medicationadministration import (
    MedicationAdministration,
    MedicationAdministrationDosage,
    MedicationAdministrationPerformer,
)
from fhir.resources.R4B.observation import Observation
from fhir.resources.R4B.patient import Patient
from fhir.resources.R4B.period import Period
from fhir.resources.R4B.practitioner import Practitioner, PractitionerQualification
from fhir.resources.R4B.quantity import Quantity
from fhir.resources.R4B.reference import Reference

from ims_backend.models import Atencion, DetalleInsumoAtencion


SYSTEM_RUT = "https://hl7chile.cl/fhir/ig/clcore/CodeSystem/CSIdentificadores"
LOINC      = "http://loinc.org"
UCUM       = "http://unitsofmeasure.org"
OBS_CAT    = "http://terminology.hl7.org/CodeSystem/observation-category"
PART_TYPE  = "http://terminology.hl7.org/CodeSystem/v3-ParticipationType"
ACT_CODE   = "http://terminology.hl7.org/CodeSystem/v3-ActCode"

CL = "https://hl7chile.cl/fhir/ig/clcore/StructureDefinition"
PROFILE_PATIENT      = f"{CL}/CorePacienteCl"
PROFILE_PRACTITIONER = f"{CL}/CorePrestadorCl"
PROFILE_ENCOUNTER    = f"{CL}/EncounterCL"
PROFILE_OBSERVATION  = f"{CL}/CoreObservacionCL"

SYSTEM_CATEGORIA = "https://956.duckdns.org/fhir/CodeSystem/CategoriaAtencion"   
SYSTEM_CRONOEV   = "https://956.duckdns.org/fhir/CodeSystem/EventoCronologia"    

STATUS_MAP = {
    "Firmado":   "completed",
    "Pendiente": "in-progress",
}


VITAL_LOINC = {
    "presion_sistolica":   ("8480-6",  "Systolic blood pressure",          "mm[Hg]"),
    "presion_diastolica":  ("8462-4",  "Diastolic blood pressure",         "mm[Hg]"),
    "frecuencia_cardiaca": ("8867-4",  "Heart rate",                       "/min"),
    "saturacion_oxigeno":  ("59408-5", "Oxygen saturation (pulse ox)",     "%"),
    "temperatura":         ("8310-5",  "Body temperature",                 "Cel"),
    "fr":                  ("9279-1",  "Respiratory rate",                 "/min"),
    "fio2":                ("3150-0",  "Inhaled oxygen concentration",     "%"),
    "hgt":                 ("2339-0",  "Glucose [Mass/volume] in Blood",   "mg/dL"),
    "gcs":                 ("9269-2",  "Glasgow coma score total",         "{score}"),
    "eva":                 ("72514-3", "Pain severity 0-10 numeric rating", "{score}"),
}

CRONO_EVENTS = {
    "hora_llamada":   ("hora-llamada",   "Hora de la llamada al servicio"),
    "despacho_movil": ("despacho-movil", "Despacho del móvil"),
    "llegada_qth1":   ("llegada-qth1",   "Llegada al lugar del paciente (QTH1)"),
    "salida_qth1":    ("salida-qth1",    "Salida desde el lugar del paciente (QTH1)"),
    "llegada_qth2":   ("llegada-qth2",   "Llegada al destino (QTH2)"),
    "salida_qth2":    ("salida-qth2",    "Salida desde el destino (QTH2)"),
}

def _to_iso(val):
    if not val:
        return None
    if isinstance(val, str):
        return val
    return val.isoformat()

def _rut_identifier(rut):
    return Identifier(value=rut, system=SYSTEM_RUT)

def _entry(full_url, resource, resource_type):
    return BundleEntry(
        fullUrl=full_url,
        resource=resource,
        request=BundleEntryRequest(method="POST", url=resource_type),
    )

def export_hl7(atencion_id):
    atencion = (
        Atencion.objects
        .select_related(
            "despacho__paciente",
            "despacho__ambulancia",
            "rut_registrador__rol",
            "preinforme_atencion",
            "crono_atencion",
        )
        .prefetch_related(
            "signos_vitales",
            Prefetch(
                "detalleinsumoatencion_set",
                queryset=DetalleInsumoAtencion.objects.select_related(
                    "insumo__insumo", "insumo__unidad_medida"
                ),
            ),
        )
        .get(id=atencion_id)
    )

    paciente    = atencion.despacho.paciente
    practicante = atencion.rut_registrador
    crono       = getattr(atencion, "crono_atencion", None)
    preinforme  = getattr(atencion, "preinforme_atencion", None)

    patient_uuid      = f"urn:uuid:{uuid.uuid4()}"
    practitioner_uuid = f"urn:uuid:{uuid.uuid4()}"
    receiver_uuid     = f"urn:uuid:{uuid.uuid4()}" if atencion.rut_receptor else None
    encounter_uuid    = f"urn:uuid:{uuid.uuid4()}"

    entries = []
    direccion_limpia = paciente.direccion.strip() if paciente.direccion else None
    comuna_limpia = paciente.comuna.strip() if paciente.comuna else None
    
    address_list = []
    if direccion_limpia or comuna_limpia:
        address_list.append(Address(
            text=direccion_limpia, 
            city=comuna_limpia
        ))

    telefono_limpio = paciente.telefono.strip() if paciente.telefono else None  
    patient = Patient(
        meta={"profile": [PROFILE_PATIENT]},
        identifier=[_rut_identifier(paciente.rut)],
        name=[HumanName(text=paciente.nombre_completo)],
        birthDate=_to_iso(paciente.fecha_nacimiento) if paciente.fecha_nacimiento else None,
        address= address_list if address_list else None,
        telecom=(
            [ContactPoint(system="phone", value=telefono_limpio)]
            if paciente.telefono else None
        ),
    )
    entries.append(_entry(patient_uuid, patient, "Patient"))
    
    qualifications = []
    if practicante.rol:
        qualifications.append(PractitionerQualification(
            code=CodeableConcept(text=practicante.rol.nombre_rol)
        ))
    practitioner = Practitioner(
        meta={"profile": [PROFILE_PRACTITIONER]},
        identifier=[_rut_identifier(practicante.rut)],
        name=[HumanName(text=practicante.full_name)],
        qualification=qualifications or None,
    )
    entries.append(_entry(practitioner_uuid, practitioner, "Practitioner"))
    
    if receiver_uuid:
        receiver = Practitioner(
            meta={"profile": [PROFILE_PRACTITIONER]},
            identifier=[_rut_identifier(atencion.rut_receptor)],
        )
        entries.append(_entry(receiver_uuid, receiver, "Practitioner"))

    motivo_txt = (
        preinforme.motivo_llamado
        if preinforme and preinforme.motivo_llamado
        else "Atención prehospitalaria"
    )

    participants = [
        EncounterParticipant(
            type=[CodeableConcept(coding=[Coding(
                system=PART_TYPE, code="ATND", display="attender"
            )])],
            individual={
                "reference": practitioner_uuid, 
                "display": practicante.full_name
            },
        )
    ]
    
    if receiver_uuid:
        participants.append(EncounterParticipant(
            type=[CodeableConcept(coding=[Coding(
                system=PART_TYPE, code="REF", display="referrer"
            )])],
            individual={
                "reference": receiver_uuid, 
                "display": "Receptor"
            },
        ))
    
    encounter_kwargs = {
        "meta": {"profile": [PROFILE_ENCOUNTER]},
        "status": STATUS_MAP.get(atencion.estado_sello, "unknown"),
        
        "class_fhir": {
            "system": ACT_CODE, 
            "code": "EMER", 
            "display": "emergency"
        },
        "subject": {
            "reference": patient_uuid, 
            "display": paciente.nombre_completo
        },
        "participant": participants,
        
        "period": {
            "start": _to_iso(atencion.hora_salida) if atencion.hora_salida else None,
            "end": _to_iso(atencion.hora_llegada) if atencion.hora_llegada else None,
        },
        
        "reasonCode": [
            {
                "text": motivo_txt
            }
        ],
    }

    if crono and crono.categoria:
        encounter_kwargs["priority"] = {
            "coding": [{
                "system": SYSTEM_CATEGORIA, 
                "code": crono.categoria, 
                "display": f"Categoría {crono.categoria}"
            }]
        }
    encounter = Encounter(**encounter_kwargs)
    entries.append(_entry(encounter_uuid, encounter, "Encounter"))
    
    for sv in atencion.signos_vitales.all():
        effective_iso = _to_iso(sv.timestamp)
        for field, (code, display, unit) in VITAL_LOINC.items():
            value = getattr(sv, field, None)
            if value is None:
                continue
            obs_uuid = f"urn:uuid:{uuid.uuid4()}"
            obs = Observation(
                meta={"profile": [PROFILE_OBSERVATION]},
                status="final",
                category=[CodeableConcept(coding=[Coding(
                    system=OBS_CAT, code="vital-signs", display="Vital Signs"
                )])],
                code=CodeableConcept(coding=[Coding(
                    system=LOINC, code=code, display=display
                )]),
                subject=Reference(reference=patient_uuid),
                encounter=Reference(reference=encounter_uuid),
                effectiveDateTime=effective_iso,
                performer=[Reference(reference=practitioner_uuid)],
                valueQuantity=Quantity(
                    value=float(value), unit=unit, system=UCUM, code=unit
                ),
            )
            if sv.observaciones:
                obs.note = [{"text": sv.observaciones}]
            entries.append(_entry(obs_uuid, obs, "Observation"))

    if crono:
        for field, (code, display) in CRONO_EVENTS.items():
            ts = getattr(crono, field, None)
            if not ts:
                continue
            obs_uuid = f"urn:uuid:{uuid.uuid4()}"
            obs = Observation(
                meta={"profile": [PROFILE_OBSERVATION]},
                status="final",
                category=[CodeableConcept(coding=[Coding(
                    system=OBS_CAT, code="exam", display="Exam"
                )])],
                code=CodeableConcept(coding=[Coding(
                    system=SYSTEM_CRONOEV, code=code, display=display
                )]),
                subject=Reference(reference=patient_uuid),
                encounter=Reference(reference=encounter_uuid),
                effectiveDateTime=_to_iso(ts),
                performer=[Reference(reference=practitioner_uuid)],
            )
            entries.append(_entry(obs_uuid, obs, "Observation"))

    medeff_start = _to_iso(atencion.hora_salida) if atencion.hora_salida else None
    medeff_end   = _to_iso(atencion.hora_llegada) if atencion.hora_llegada else None

    for detalle in atencion.detalleinsumoatencion_set.all():
        presentacion = detalle.insumo
        insumo_nombre = presentacion.insumo.nombre_insumo
        unidad = presentacion.unidad_medida.unit if presentacion.unidad_medida else ""
        med_text = f"{insumo_nombre} {presentacion.cantidad} {unidad}".strip()
        med_uuid = f"urn:uuid:{uuid.uuid4()}"
        
        ma_kwargs = {
            "status": "completed",
            
            "medicationCodeableConcept": {
                "text": med_text
            },
            
            "subject": {
                "reference": patient_uuid, 
                "display": paciente.nombre_completo
            },
            
            "context": {
                "reference": encounter_uuid
            },
            
            "performer": [
                {
                    "actor": {
                        "reference": practitioner_uuid, 
                        "display": practicante.full_name
                    }
                }
            ],
            
            "dosage": {
                "dose": {
                    "value": float(detalle.cantidad_usada),
                    "unit": unidad or None,
                },
                "text": detalle.observaciones or None,
            },
        }

        if medeff_start and medeff_end:
            ma_kwargs["effectivePeriod"] = {"start": medeff_start, "end": medeff_end}
        elif medeff_start:
            ma_kwargs["effectiveDateTime"] = medeff_start

        med_admin = MedicationAdministration(**ma_kwargs)
        entries.append(_entry(med_uuid, med_admin, "MedicationAdministration"))

    bundle = Bundle(
        type="transaction",
        timestamp=_to_iso(datetime.now()) + "Z",
        entry=entries,
    )

    return bundle.dict(by_alias=True)