import uuid
from datetime import datetime, timezone

from django.db.models import Prefetch

from fhir.resources.R4B.address import Address
from fhir.resources.R4B.bundle import Bundle, BundleEntry, BundleEntryRequest
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.contactpoint import ContactPoint
from fhir.resources.R4B.encounter import Encounter, EncounterParticipant
from fhir.resources.R4B.humanname import HumanName
from fhir.resources.R4B.identifier import Identifier
from fhir.resources.R4B.medicationadministration import MedicationAdministration
from fhir.resources.R4B.observation import Observation
from fhir.resources.R4B.patient import Patient
from fhir.resources.R4B.practitioner import Practitioner, PractitionerQualification
from fhir.resources.R4B.quantity import Quantity
from fhir.resources.R4B.reference import Reference

from ims_backend.models import Atencion, DetalleInsumoAtencion

# ── Systems ───────────────────────────────────────────────────────────────────
# http:// — the clcore package registers this URI without the 's'
SYSTEM_RUT = "http://hl7chile.cl/fhir/ig/clcore/CodeSystem/CSIdentificadores"
LOINC      = "http://loinc.org"
UCUM       = "http://unitsofmeasure.org"
OBS_CAT    = "http://terminology.hl7.org/CodeSystem/observation-category"
PART_TYPE  = "http://terminology.hl7.org/CodeSystem/v3-ParticipationType"
ACT_CODE   = "http://terminology.hl7.org/CodeSystem/v3-ActCode"

# ── clcore v1.9.4 profiles ────────────────────────────────────────────────────
CL = "https://hl7chile.cl/fhir/ig/clcore/StructureDefinition"
PROFILE_PATIENT      = f"{CL}/CorePacienteCl"
PROFILE_PRACTITIONER = f"{CL}/CorePrestadorCl"
PROFILE_ENCOUNTER    = f"{CL}/EncounterCL"
PROFILE_OBSERVATION  = f"{CL}/CoreObservacionCL"


# ── Value mappings ────────────────────────────────────────────────────────────
STATUS_MAP = {
    "Firmado":   "finished",
    "Pendiente": "in-progress",
}
UCUM_MAP = {
    "MG":         "mg",
    "ML":         "mL",
    "UNIDAD":     "{unidad}",
    "comprimido": "{comprimido}",
}
# Each entry: (loinc_code, display, unit_display, ucum_code, obs_category)
# Fix #4: hgt → laboratory; gcs/eva → survey (not vital-signs)
# Fix #5: /min is ambiguous — use canonical 1/min as code; beats/min as display for HR
VITAL_LOINC = {
    "frecuencia_cardiaca": ("8867-4",  "Heart rate",                                                    "beats/min", "/min",    "vital-signs"),
    "saturacion_oxigeno":  ("2708-6",  "Oxygen saturation in Arterial blood",                           "%",         "%",       "vital-signs"),
    "temperatura":         ("8310-5",  "Body temperature",                                              "Cel",       "Cel",     "vital-signs"),
    "fr":                  ("9279-1",  "Respiratory rate",                                              "/min",      "/min",    "vital-signs"),
    "fio2":                ("3150-0",  "Inhaled oxygen concentration",                                  "%",         "%",       "vital-signs"),
    "hgt":                 ("2339-0",  "Glucose [Mass/volume] in Blood",                                "mg/dL",     "mg/dL",   "laboratory"),
    "gcs":                 ("9269-2",  "Glasgow coma score total",                                      "{score}",   "{score}", "survey"),
    "eva":                 ("72514-3", "Pain severity - 0-10 verbal numeric rating [Score] - Reported", "{score}",   "{score}", "survey"),
}
CAT_DISPLAY = {
    "vital-signs": "Vital Signs",
    "laboratory":  "Laboratory",
    "survey":      "Survey",
}
CRONO_EVENTS = {
    "hora_llamada":   ("hora-llamada",   "Hora de la llamada al servicio"),
    "despacho_movil": ("despacho-movil", "Despacho del móvil"),
    "llegada_qth1":   ("llegada-qth1",   "Llegada al lugar del paciente (QTH1)"),
    "salida_qth1":    ("salida-qth1",    "Salida desde el lugar del paciente (QTH1)"),
    "llegada_qth2":   ("llegada-qth2",   "Llegada al destino (QTH2)"),
    "salida_qth2":    ("salida-qth2",    "Salida desde el destino (QTH2)"),
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _to_iso(val) -> str | None:
    if not val:
        return None
    if isinstance(val, str):
        return val
    return val.isoformat()

def _narrative(text: str) -> dict:
    return {"status": "generated", "div": f'<div xmlns="http://www.w3.org/1999/xhtml">{text}</div>'}

_INVALID_RUTS = {"0-0", "0", "0-K", ""}

def _is_valid_rut(rut: str) -> bool:
    return bool(rut) and rut.strip() not in _INVALID_RUTS

def _rut_identifier(rut: str) -> Identifier | None:
    """
    Returns a Chilean RUN identifier conformant with CorePacienteCl / CorePrestadorCl,
    or None when the RUT is invalid/unknown. Callers must filter out None before building
    the identifier list. type is intentionally omitted — see original comment above.
    """
    if _is_valid_rut(rut):
        return Identifier(use="official", system=SYSTEM_RUT, value=rut)
    return None

def _split_nombre(nombre_completo: str) -> tuple[list[str], str]:
    """Best-effort split of a full-name string into (given_names, family)."""
    parts = (nombre_completo or "").strip().split()
    if not parts:
        return [], ""
    return parts[:-1], parts[-1]

def _entry(full_url: str, resource, resource_type: str) -> BundleEntry:
    return BundleEntry(
        fullUrl=full_url,
        resource=resource,
        request=BundleEntryRequest(method="POST", url=resource_type),
    )

# ── Export ────────────────────────────────────────────────────────────────────

def export_hl7(atencion_id) -> dict:
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

    # ── Patient ───────────────────────────────────────────────────────────────
    given_names, family_name = _split_nombre(paciente.nombre_completo)

    address_list = []
    if paciente.direccion or paciente.comuna:
        # CL Core cl-address requires Address.city to carry a coded ComunasCl extension
        # (CODEMA code). We only have plain text, so we omit city and put everything in
        # text to avoid the mandatory-extension validation error.
        addr_parts = [p.strip() for p in [paciente.direccion, paciente.comuna] if p and p.strip()]
        address_list.append(Address(text=", ".join(addr_parts) if addr_parts else None))

    patient_id = _rut_identifier(paciente.rut)
    patient = Patient(
        meta={"profile": [PROFILE_PATIENT]},
        text=_narrative(f"Paciente: {paciente.nombre_completo} — RUT {paciente.rut}"),
        identifier=[patient_id] if patient_id else None,
        name=[HumanName(
            use="official",
            text=paciente.nombre_completo,
            family=family_name or None,
            given=given_names or None,
        )],
        birthDate=_to_iso(paciente.fecha_nacimiento) if paciente.fecha_nacimiento else None,
        address=address_list or None,
        telecom=(
            [ContactPoint(system="phone", value=paciente.telefono.strip())]
            if paciente.telefono else None
        ),
    )
    entries.append(_entry(patient_uuid, patient, "Patient"))

    # ── Practitioner (registrador) ────────────────────────────────────────────
    qualifications = []
    if practicante.rol:
        qualifications.append(PractitionerQualification(
            code=CodeableConcept(text=practicante.rol.nombre_rol)
        ))

    prac_id = _rut_identifier(practicante.rut)
    practitioner = Practitioner(
        meta={"profile": [PROFILE_PRACTITIONER]},
        text=_narrative(f"Prestador: {practicante.full_name} — RUT {practicante.rut}"),
        identifier=[prac_id] if prac_id else None,
        name=[HumanName(
            use="official",
            text=practicante.full_name,
            family=practicante.last_name or None,
            given=[practicante.first_name] if practicante.first_name else None,
        )],
        qualification=qualifications or None,
    )
    entries.append(_entry(practitioner_uuid, practitioner, "Practitioner"))

    # ── Receiver / receptor (optional) ────────────────────────────────────────
    # Fix #1: Practitioner requires name per CL Core CorePrestadorCl profile
    if receiver_uuid:
        recv_id = _rut_identifier(atencion.rut_receptor)
        receiver = Practitioner(
            text=_narrative(f"Receptor — RUT {atencion.rut_receptor}"),
            identifier=[recv_id] if recv_id else None,
            name=[HumanName(text="Receptor desconocido")],
        )
        entries.append(_entry(receiver_uuid, receiver, "Practitioner"))

    # ── Encounter ─────────────────────────────────────────────────────────────
    motivo_txt = (
        preinforme.motivo_llamado
        if preinforme and preinforme.motivo_llamado
        else "Atención prehospitalaria"
    )

    participants = [
        EncounterParticipant(
            type=[CodeableConcept(coding=[Coding(system=PART_TYPE, code="ATND", display="attender")])],
            individual={"reference": practitioner_uuid, "display": practicante.full_name},
        )
    ]
    if receiver_uuid:
        participants.append(EncounterParticipant(
            type=[CodeableConcept(coding=[Coding(system=PART_TYPE, code="REF", display="referrer")])],
            individual={"reference": receiver_uuid, "display": "Receptor"},
        ))

    # Fix #6: status "finished" requires period.end — fall back to now() if hora_llegada absent
    encounter_status = STATUS_MAP.get(atencion.estado_sello, "unknown")
    period_start = _to_iso(atencion.hora_salida)  if atencion.hora_salida  else None
    period_end   = _to_iso(atencion.hora_llegada) if atencion.hora_llegada else None
    if encounter_status == "finished" and not period_end:
        period_end = _now_utc()
    encounter_period = {"start": period_start, "end": period_end} if (period_start or period_end) else None

    encounter_kwargs = {
        "meta":       {"profile": [PROFILE_ENCOUNTER]},
        "text":       _narrative(f"Atención prehospitalaria de emergencia — {paciente.nombre_completo}"),
        "status":     encounter_status,
        "class_fhir": {"system": ACT_CODE, "code": "EMER", "display": "emergency"},
        "subject":    {"reference": patient_uuid, "display": paciente.nombre_completo},
        "participant": participants,
        "reasonCode": [{"text": motivo_txt}],
    }
    if encounter_period:
        encounter_kwargs["period"] = encounter_period
    if crono and crono.categoria:
        encounter_kwargs["priority"] = {"text": f"Categoría {crono.categoria}"}
    entries.append(_entry(encounter_uuid, Encounter(**encounter_kwargs), "Encounter"))

    # ── Observations: signos vitales ──────────────────────────────────────────
    fecha_base = atencion.hora_salida.date() if atencion.hora_salida else None

    for sv in atencion.signos_vitales.all():
        if sv.hora and fecha_base:
            h = str(sv.hora).strip()
            if ":" not in h and len(h) == 4:
                h = f"{h[:2]}:{h[2:]}"
            effective_iso = f"{fecha_base.isoformat()}T{h}:00Z"
        else:
            effective_iso = _to_iso(sv.timestamp)

        if sv.presion_sistolica is not None and sv.presion_diastolica is not None:
            bp_uuid = f"urn:uuid:{uuid.uuid4()}"
            bp_kwargs = dict(
                meta={"profile": [PROFILE_OBSERVATION]},
                text=_narrative(f"Tensión arterial: {sv.presion_sistolica}/{sv.presion_diastolica} mm[Hg]"),
                status="final",
                category=[CodeableConcept(coding=[Coding(system=OBS_CAT, code="vital-signs", display="Vital Signs")])],
                code=CodeableConcept(coding=[Coding(system=LOINC, code="85354-9", display="Blood pressure panel with all children optional")]),
                subject=Reference(reference=patient_uuid),
                encounter=Reference(reference=encounter_uuid),
                effectiveDateTime=effective_iso,
                performer=[Reference(reference=practitioner_uuid)],
                component=[
                    {
                        "code": {"coding": [{"system": LOINC, "code": "8480-6", "display": "Systolic blood pressure"}]},
                        "valueQuantity": {"value": float(sv.presion_sistolica), "unit": "mm[Hg]", "system": UCUM, "code": "mm[Hg]"},
                    },
                    {
                        "code": {"coding": [{"system": LOINC, "code": "8462-4", "display": "Diastolic blood pressure"}]},
                        "valueQuantity": {"value": float(sv.presion_diastolica), "unit": "mm[Hg]", "system": UCUM, "code": "mm[Hg]"},
                    },
                ],
            )
            if sv.observaciones:
                bp_kwargs["note"] = [{"text": sv.observaciones}]
            entries.append(_entry(bp_uuid, Observation(**bp_kwargs), "Observation"))

        for field, (code, display, unit_display, ucum_code, obs_category) in VITAL_LOINC.items():
            value = getattr(sv, field, None)
            if value is None:
                continue
            obs_uuid = f"urn:uuid:{uuid.uuid4()}"
            obs_kwargs = dict(
                meta={"profile": [PROFILE_OBSERVATION]},
                text=_narrative(f"{display}: {value} {unit_display}"),
                status="final",
                category=[CodeableConcept(coding=[Coding(system=OBS_CAT, code=obs_category, display=CAT_DISPLAY.get(obs_category, obs_category))])],
                code=CodeableConcept(coding=[Coding(system=LOINC, code=code, display=display)]),
                subject=Reference(reference=patient_uuid),
                encounter=Reference(reference=encounter_uuid),
                effectiveDateTime=effective_iso,
                performer=[Reference(reference=practitioner_uuid)],
                valueQuantity=Quantity(value=float(value), unit=unit_display, system=UCUM, code=ucum_code),
            )
            if sv.observaciones:
                obs_kwargs["note"] = [{"text": sv.observaciones}]
            entries.append(_entry(obs_uuid, Observation(**obs_kwargs), "Observation"))

    # ── Observations: cronología ──────────────────────────────────────────────
    if crono:
        for field, (code, display) in CRONO_EVENTS.items():
            ts = getattr(crono, field, None)
            if not ts:
                continue
            if isinstance(ts, datetime):
                effective_iso = _to_iso(ts)
            elif fecha_base and hasattr(ts, 'hour'):
                effective_iso = _to_iso(datetime.combine(fecha_base, ts))
            else:
                ts_str = str(ts).strip()
                if ":" not in ts_str and len(ts_str) == 4:
                    ts_str = f"{ts_str[:2]}:{ts_str[2:]}"
                effective_iso = f"{fecha_base.isoformat()}T{ts_str}:00Z" if fecha_base else None
            if not effective_iso:
                continue
            obs_uuid = f"urn:uuid:{uuid.uuid4()}"
            entries.append(_entry(obs_uuid, Observation(
                meta={"profile": [PROFILE_OBSERVATION]},
                text=_narrative(f"Cronología — {display}"),
                status="final",
                category=[CodeableConcept(coding=[Coding(system=OBS_CAT, code="survey", display="Survey")])],
                code=CodeableConcept(text=display),
                subject=Reference(reference=patient_uuid),
                encounter=Reference(reference=encounter_uuid),
                effectiveDateTime=effective_iso,
                valueDateTime=effective_iso,
                performer=[Reference(reference=practitioner_uuid)],
            ), "Observation"))

    # ── MedicationAdministration ──────────────────────────────────────────────
    medeff_start = _to_iso(atencion.hora_salida)  if atencion.hora_salida  else None
    medeff_end   = _to_iso(atencion.hora_llegada) if atencion.hora_llegada else None

    for detalle in atencion.detalleinsumoatencion_set.all():
        presentacion  = detalle.insumo
        insumo_nombre = presentacion.insumo.nombre_insumo
        unidad_raw    = presentacion.unidad_medida.unit if presentacion.unidad_medida else None
        unidad_ucum   = UCUM_MAP.get(unidad_raw, f"{{{unidad_raw}}}" if unidad_raw else None)
        med_text      = f"{insumo_nombre} {presentacion.cantidad} {unidad_raw or ''}".strip()
        med_uuid      = f"urn:uuid:{uuid.uuid4()}"

        ma_kwargs = {
            "text":    _narrative(f"Administración de medicamento: {med_text}"),
            "status":  "completed",
            "medicationCodeableConcept": {"text": med_text},
            "subject":   {"reference": patient_uuid, "display": paciente.nombre_completo},
            "context":   {"reference": encounter_uuid},
            "performer": [{"actor": {"reference": practitioner_uuid, "display": practicante.full_name}}],
            "dosage": {
                "dose": {
                    "value": float(detalle.cantidad_usada) * float(presentacion.cantidad),
                    "unit":   unidad_ucum,
                    "system": UCUM,
                    "code":   unidad_ucum,
                },
                "text": detalle.observaciones or None,
            },
        }
        if medeff_start and medeff_end:
            ma_kwargs["effectivePeriod"] = {"start": medeff_start, "end": medeff_end}
        elif medeff_start:
            ma_kwargs["effectiveDateTime"] = medeff_start

        entries.append(_entry(med_uuid, MedicationAdministration(**ma_kwargs), "MedicationAdministration"))

    bundle = Bundle(
        type="transaction",
        timestamp=_now_utc(),
        entry=entries,
    )
    return bundle.dict(by_alias=True)
