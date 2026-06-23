import random
from datetime import date
from django.core.management.base import BaseCommand
from ims_backend.models import Paciente

NOMBRES = [
    "Ana García", "Carlos López", "María Rodríguez", "José Martínez", "Laura Sánchez",
    "Pedro González", "Isabel Fernández", "Miguel Torres", "Carmen Díaz", "Francisco Ruiz",
    "Sofía Herrera", "Andrés Morales", "Valentina Castro", "Ricardo Jiménez", "Claudia Romero",
    "Sebastián Vargas", "Daniela Reyes", "Alejandro Flores", "Camila Ortiz", "Felipe Mendoza",
    "Gabriela Rojas", "Matías Silva", "Javiera Muñoz", "Rodrigo Álvarez", "Paula Espinoza",
    "Nicolás Campos", "Constanza Vega", "Tomás Núñez", "Francisca Ramos", "Diego Peña",
    "Isidora Bravo", "Cristóbal Soto", "Antonia Mora", "Gonzalo Gutiérrez", "Renata Cortés",
    "Ignacio Lara", "Pilar Navarro", "Maximiliano Ríos", "Carolina Molina", "Javier Fuentes",
    "Natalia Delgado", "Emilio Cabrera", "Victoria Aguilar", "Hugo Medina", "Beatriz Contreras",
    "Mauricio Sepúlveda", "Lorena Sandoval", "Patricio Ibáñez", "Elena Pizarro", "Samuel Acosta",
]

COMUNAS = [
    "Santiago", "Providencia", "Las Condes", "Ñuñoa", "Maipú", "La Florida",
    "Pudahuel", "Quilicura", "Peñalolén", "Lo Barnechea", "Macul", "San Miguel",
    "Estación Central", "Conchalí", "Independencia", "Recoleta", "Cerrillos", "Buin",
    "Talagante", "Melipilla",
]

DIRECCIONES = [
    "Av. Providencia 1234", "Calle Los Aromos 567", "Pasaje El Roble 89", "Av. Libertador 4520",
    "Calle Maipú 321", "Av. Grecia 980", "Los Nogales 12", "Calle Arturo Prat 765",
    "Av. O'Higgins 2100", "Calle Balmaceda 450", "Pasaje Los Pinos 33", "Av. Kennedy 5050",
    "Calle Irarrázaval 900", "Av. Vicuña Mackenna 3300", "Los Lirios 77", "Calle Tobalaba 2200",
    "Av. Colón 1560", "Calle Serrano 88", "Pasaje Las Rosas 14", "Av. Manuel Montt 780",
]

CONDICIONES = [
    "Diabetes tipo 2, en tratamiento con metformina.",
    "Hipertensión arterial controlada.",
    "Asma bronquial leve intermitente.",
    "Antecedente de infarto al miocardio (2019).",
    "Insuficiencia renal crónica estadio 3.",
    "EPOC moderado, usuario de broncodilatadores.",
    "Hipotiroidismo en tratamiento con levotiroxina.",
    "Epilepsia controlada con carbamazepina.",
    "Artritis reumatoide, en tratamiento biológico.",
    "Sin antecedentes mórbidos de relevancia.",
    "Obesidad mórbida IMC > 40.",
    "Depresión mayor, en tratamiento psiquiátrico.",
    "Fibrilación auricular permanente anticoagulada.",
    "Cáncer de colon en remisión.",
    "Cirrosis hepática Child-Pugh A.",
]


def _rut_digito(n: int) -> str:
    rev = reversed(str(n))
    factors = [2, 3, 4, 5, 6, 7]
    total = sum(int(d) * factors[i % 6] for i, d in enumerate(rev))
    remainder = 11 - (total % 11)
    if remainder == 11:
        return "0"
    if remainder == 10:
        return "K"
    return str(remainder)


def _generar_rut(n: int) -> str:
    dv = _rut_digito(n)
    return f"{n:,}".replace(",", ".") + "-" + dv


def _fecha_aleatoria() -> date:
    year = random.randint(1940, 2005)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return date(year, month, day)


def _telefono_aleatorio() -> str:
    return f"+569{random.randint(10000000, 99999999)}"


class Command(BaseCommand):
    help = "Genera 100 pacientes de prueba con datos variados."

    def handle(self, *args, **options):
        created = 0
        skipped = 0
        rut_base = random.randint(5_000_000, 25_000_000)

        for i in range(100):
            rut_num = rut_base + i * random.randint(3, 20)
            rut = _generar_rut(rut_num)

            if Paciente.objects.filter(rut=rut).exists():
                skipped += 1
                continue

            nombre = random.choice(NOMBRES)
            direccion = random.choice(DIRECCIONES)
            comuna = random.choice(COMUNAS)

            variant = i % 3

            if variant == 0:
                # Completo: todos los campos opcionales rellenos
                paciente = Paciente(
                    rut=rut,
                    nombre_completo=nombre,
                    direccion=direccion,
                    comuna=comuna,
                    fecha_nacimiento=_fecha_aleatoria(),
                    condicion_paciente=random.choice(CONDICIONES),
                    telefono=_telefono_aleatorio(),
                )
            elif variant == 1:
                # Sin fecha_nacimiento
                paciente = Paciente(
                    rut=rut,
                    nombre_completo=nombre,
                    direccion=direccion,
                    comuna=random.choice([comuna, None]),
                    fecha_nacimiento=None,
                    condicion_paciente=random.choice([random.choice(CONDICIONES), None]),
                    telefono=random.choice([_telefono_aleatorio(), None]),
                )
            else:
                # Parcial: solo algunos opcionales
                paciente = Paciente(
                    rut=rut,
                    nombre_completo=nombre,
                    direccion=direccion,
                    comuna=None,
                    fecha_nacimiento=random.choice([_fecha_aleatoria(), None]),
                    condicion_paciente=None,
                    telefono=random.choice([_telefono_aleatorio(), None]),
                )

            paciente.save()
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seeding completado: {created} pacientes creados, {skipped} RUTs ya existían."
        ))
