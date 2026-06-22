import sys
import json
import time
import threading
import csv
import requests
from datetime import datetime
from statistics import mean, median

sys.path.insert(0, '/home/miku/Documents/tests/javi')
from funciones import BASE_URL, HEADERS_BASE, DESPACHO_URL, PAYLOAD_DESPACHO

AUTH_URL          = f"{BASE_URL}/auth/"
LOGIN_URL         = f"{BASE_URL}/login/"
LOGS_URL          = f"{BASE_URL}/logs/"
DESPACHOS_ALL_URL = f"{BASE_URL}/despachos/all/"
ASIGNAR_URL       = f"{BASE_URL}/despachos/asignar/"
PROGRAMAR_URL     = f"{BASE_URL}/despachos/programar/"
ATENCION_URL      = f"{BASE_URL}/atenciones/add/"
ESTADOS_URL       = f"{BASE_URL}/ambulancias/estados/"
VERIFICAR_URL     = f"{BASE_URL}/documentos/verificar/"
SENALES_URL       = f"{BASE_URL}/senales/"
CANCELAR_URL      = f"{BASE_URL}/despachos/cancelar/"

resultados_lock = threading.Lock()

# read-only mode
resultados: list[tuple[int, float]] = []
paginas_por_hilo: list[int] = []

# mixed mode
resultados_lectura:  list[tuple[int, float]] = []
resultados_escritura: list[tuple[int, float]] = []
paginas_por_hilo_lectura: list[int] = []


# ── Auth ──────────────────────────────────────────────────────────────────────

def autenticar(s: requests.Session) -> bool:
    username = input("Usuario (RUT): ").strip()
    password = input("Contraseña: ").strip()
    res = s.post(AUTH_URL, json={"username": username, "password": password}, headers=HEADERS_BASE)
    if res.status_code != 200:
        print(f"AUTH falló [{res.status_code}]:", res.text)
        return False
    print(f"AUTH ok [{res.status_code}]")

    totp = input("TOTP code: ").strip()

    s.get(LOGIN_URL, headers=HEADERS_BASE)
    csrf = s.cookies.get("csrftoken")

    res_login = s.post(
        LOGIN_URL,
        json={"totp_code": totp},
        headers={**HEADERS_BASE, "X-CSRFToken": csrf},
    )
    print(f"LOGIN [{res_login.status_code}]:", res_login.text)
    return res_login.status_code == 200


# ── Paginator browser ─────────────────────────────────────────────────────────

def fetch_page(s: requests.Session, url: str) -> dict | None:
    csrf = s.cookies.get("csrftoken")
    res = s.get(url, headers={**HEADERS_BASE, "X-CSRFToken": csrf})
    if res.status_code != 200:
        print(f"Error [{res.status_code}]:", res.text)
        return None
    return res.json()


def modo_paginas(s: requests.Session):
    url: str | None = LOGS_URL
    page_num = 1

    while url:
        print(f"\n{'=' * 60}")
        print(f"  Página {page_num}  |  {url}")
        print("=" * 60)

        data = fetch_page(s, url)
        if data is None:
            break

        print(f"Resultados en esta página: {len(data.get('results', []))}")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        next_url = data.get("next")
        print(f"\n  next     → {next_url}")
        print(f"  previous → {data.get('previous')}")

        if not next_url:
            print("\nFin de los resultados.")
            break

        action = input("\n[Enter] siguiente  |  [q] salir: ").strip().lower()
        if action == "q":
            break

        url = next_url
        page_num += 1


# ── Concurrent load test ──────────────────────────────────────────────────────

def worker(s: requests.Session, csrf: str):
    url: str | None = LOGS_URL
    paginas = 0
    try:
        while url:
            r = s.get(url, headers={**HEADERS_BASE, "X-CSRFToken": csrf})
            with resultados_lock:
                resultados.append((r.status_code, r.elapsed.total_seconds() * 1000))
            if r.status_code != 200:
                break
            url = r.json().get("next")
            paginas += 1
    except requests.exceptions.RequestException as e:
        with resultados_lock:
            resultados.append((0, 0.0))
        print(f"  [CONN ERROR] {type(e).__name__}: {e}")
    finally:
        with resultados_lock:
            paginas_por_hilo.append(paginas)


def calcular_stats(res: list[tuple[int, float]], paginas: list[int]) -> dict:
    codigos = [r[0] for r in res]
    tiempos = [r[1] for r in res]
    total   = len(res)
    errores = sum(1 for c in codigos if c == 0 or c >= 400)

    promedio = mean(tiempos)   if tiempos else 0.0
    med      = median(tiempos) if tiempos else 0.0
    minimo   = min(tiempos)    if tiempos else 0.0
    maximo   = max(tiempos)    if tiempos else 0.0
    sorted_t = sorted(tiempos)
    p95      = sorted_t[max(0, int(len(sorted_t) * 0.95) - 1)] if sorted_t else 0.0

    return {
        "total_requests": total,
        "errores":        errores,
        "error_rate":     errores / total if total else 0.0,
        "avg_paginas":    round(mean(paginas), 1) if paginas else None,
        "promedio_ms":    round(promedio, 1),
        "mediana_ms":     round(med,      1),
        "p95_ms":         round(p95,      1),
        "min_ms":         round(minimo,   1),
        "max_ms":         round(maximo,   1),
        "codigos":        codigos,
    }


def ejecutar_carga(s: requests.Session, n: int) -> dict:
    csrf = s.cookies.get("csrftoken")
    resultados.clear()
    paginas_por_hilo.clear()

    hilos = [threading.Thread(target=worker, args=(s, csrf)) for _ in range(n)]

    inicio = time.time()
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    duracion_total = time.time() - inicio

    stats = calcular_stats(resultados, paginas_por_hilo)
    return {"n": n, "duracion_total_s": round(duracion_total, 2), **stats}


# ── Mixed mode workers ────────────────────────────────────────────────────────

def worker_lectura_mixta(s: requests.Session, csrf: str):
    url: str | None = LOGS_URL
    paginas = 0
    try:
        while url:
            r = s.get(url, headers={**HEADERS_BASE, "X-CSRFToken": csrf})
            with resultados_lock:
                resultados_lectura.append((r.status_code, r.elapsed.total_seconds() * 1000))
            if r.status_code != 200:
                break
            url = r.json().get("next")
            paginas += 1
    except requests.exceptions.RequestException as e:
        with resultados_lock:
            resultados_lectura.append((0, 0.0))
        print(f"  [CONN ERROR lectura] {type(e).__name__}: {e}")
    finally:
        with resultados_lock:
            paginas_por_hilo_lectura.append(paginas)


def worker_escritura(s: requests.Session, csrf: str):
    try:
        r = s.post(DESPACHO_URL, json=PAYLOAD_DESPACHO,
                   headers={**HEADERS_BASE, "X-CSRFToken": csrf})
        with resultados_lock:
            resultados_escritura.append((r.status_code, r.elapsed.total_seconds() * 1000))
    except requests.exceptions.RequestException as e:
        with resultados_lock:
            resultados_escritura.append((0, 0.0))
        print(f"  [CONN ERROR escritura] {type(e).__name__}: {e}")


def ejecutar_carga_mixta(s: requests.Session, n: int) -> dict:
    csrf  = s.cookies.get("csrftoken")
    n_lec = n // 2
    n_esc = n - n_lec

    resultados_lectura.clear()
    resultados_escritura.clear()
    paginas_por_hilo_lectura.clear()

    hilos = (
        [threading.Thread(target=worker_lectura_mixta, args=(s, csrf)) for _ in range(n_lec)] +
        [threading.Thread(target=worker_escritura,     args=(s, csrf)) for _ in range(n_esc)]
    )

    inicio = time.time()
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    duracion_total = time.time() - inicio

    return {
        "n":               n,
        "n_lec":           n_lec,
        "n_esc":           n_esc,
        "lectura":         calcular_stats(resultados_lectura,  paginas_por_hilo_lectura),
        "escritura":       calcular_stats(resultados_escritura, []),
        "duracion_total_s": round(duracion_total, 2),
    }


def _bloque_stats(label: str, st: dict, n_hilos: int):
    from collections import Counter
    exitosos = st["total_requests"] - st["errores"]
    print(f"  ── {label} ({n_hilos} hilos) ──────────────────────────")
    print(f"  Requests   : {st['total_requests']}  |  Exitosos: {exitosos}  |  Errores: {st['errores']} ({st['error_rate']*100:.1f}%)")
    if st["avg_paginas"] is not None:
        print(f"  Pág/hilo   : ~{st['avg_paginas']}")
    print(f"  Promedio   : {st['promedio_ms']} ms  |  Mediana: {st['mediana_ms']} ms  |  P95: {st['p95_ms']} ms")
    print(f"  Min: {st['min_ms']} ms  |  Max: {st['max_ms']} ms")
    print(f"  HTTP codes : {dict(sorted(Counter(st['codigos']).items()))}")


def mostrar_metricas_mixta(m: dict):
    print(f"\n{'=' * 60}")
    print(f"  MIXTO — {m['n']} hilos  ({m['n_lec']} lectura / {m['n_esc']} escritura)")
    print(f"{'=' * 60}")
    _bloque_stats("LECTURA",   m["lectura"],   m["n_lec"])
    print()
    _bloque_stats("ESCRITURA", m["escritura"], m["n_esc"])
    print(f"  ─────────────────────────────────────────")
    print(f"  Tiempo total : {m['duracion_total_s']} s")

    # Rating based on combined error rate
    total_req = m["lectura"]["total_requests"] + m["escritura"]["total_requests"]
    total_err = m["lectura"]["errores"]         + m["escritura"]["errores"]
    er  = total_err / total_req if total_req else 0
    avg = (m["lectura"]["promedio_ms"] + m["escritura"]["promedio_ms"]) / 2

    if   er == 0   and avg < 500:
        rating = "Excelente  — escritura y lectura sin interferencia"
    elif er == 0   and avg < 1500:
        rating = "Bueno      — sin errores, algo de contención en DB"
    elif er == 0:
        rating = "Regular    — sin errores pero latencia alta, revisar pool"
    elif er < 0.05:
        rating = "Degradado  — escrituras compiten con lecturas, errores esporádicos"
    elif er < 0.15:
        rating = "Malo       — contención severa entre lecturas y escrituras"
    else:
        rating = "Crítico    — el backend no soporta esta carga mixta"

    print(f"\n  Evaluacion   : {rating}")
    print(f"{'=' * 60}")


def mostrar_metricas(m: dict):
    from collections import Counter
    exitosos = m["total_requests"] - m["errores"]
    print(f"\n{'=' * 60}")
    print(f"  RESULTADO — {m['n']} hilos  |  {m['total_requests']} requests totales")
    print(f"{'=' * 60}")
    print(f"  Hilos          : {m['n']}")
    if m["avg_paginas"] is not None:
        print(f"  Páginas/hilo   : ~{m['avg_paginas']} promedio")
    print(f"  Requests total : {m['total_requests']}")
    print(f"  Exitosos       : {exitosos}/{m['total_requests']}")
    print(f"  Errores        : {m['errores']}/{m['total_requests']}  ({m['error_rate'] * 100:.1f}%)")
    print(f"  ─────────────────────────────────────────")
    print(f"  Promedio       : {m['promedio_ms']} ms  (por página)")
    print(f"  Mediana        : {m['mediana_ms']} ms")
    print(f"  P95            : {m['p95_ms']} ms")
    print(f"  Mínimo         : {m['min_ms']} ms")
    print(f"  Máximo         : {m['max_ms']} ms")
    print(f"  Tiempo total   : {m['duracion_total_s']} s")
    print(f"  ─────────────────────────────────────────")
    print(f"  Códigos HTTP   : {dict(sorted(Counter(m['codigos']).items()))}")

    er  = m["error_rate"]
    avg = m["promedio_ms"]
    p95 = m["p95_ms"]

    if   er == 0 and avg < 200  and p95 < 400:
        rating = "Excelente  — latencia baja, sin errores"
    elif er == 0 and avg < 600  and p95 < 1000:
        rating = "Bueno      — sin errores, latencia aceptable"
    elif er == 0 and avg < 2000:
        rating = "Regular    — sin errores pero latencia alta, posible cuello de botella"
    elif er < 0.05:
        rating = "Degradado  — errores esporádicos, revisar DB o I/O"
    elif er < 0.15:
        rating = "Malo       — tasa de error significativa bajo esta carga"
    else:
        rating = "Crítico    — el backend no soporta esta concurrencia"

    print(f"\n  Evaluacion     : {rating}")
    print(f"{'=' * 60}")


FIELDNAMES = [
    "nivel", "hilos", "total_requests", "exitosos", "errores",
    "error_rate_%", "avg_paginas", "promedio_ms", "mediana_ms",
    "p95_ms", "min_ms", "max_ms", "duracion_total_s",
]


def metricas_a_fila(nivel: int, m: dict) -> dict:
    return {
        "nivel":           nivel,
        "hilos":           m["n"],
        "total_requests":  m["total_requests"],
        "exitosos":        m["total_requests"] - m["errores"],
        "errores":         m["errores"],
        "error_rate_%":    round(m["error_rate"] * 100, 1),
        "avg_paginas":     m["avg_paginas"],
        "promedio_ms":     m["promedio_ms"],
        "mediana_ms":      m["mediana_ms"],
        "p95_ms":          m["p95_ms"],
        "min_ms":          m["min_ms"],
        "max_ms":          m["max_ms"],
        "duracion_total_s": m["duracion_total_s"],
    }


FIELDNAMES_MIXTO = [
    "nivel", "hilos_total", "hilos_lectura", "hilos_escritura",
    "lec_requests", "lec_exitosos", "lec_errores", "lec_error_%", "lec_avg_paginas",
    "lec_promedio_ms", "lec_mediana_ms", "lec_p95_ms", "lec_min_ms", "lec_max_ms",
    "esc_requests", "esc_exitosos", "esc_errores", "esc_error_%",
    "esc_promedio_ms", "esc_mediana_ms", "esc_p95_ms", "esc_min_ms", "esc_max_ms",
    "duracion_total_s",
]


def metricas_a_fila_mixta(nivel: int, m: dict) -> dict:
    lec = m["lectura"]
    esc = m["escritura"]
    return {
        "nivel":           nivel,
        "hilos_total":     m["n"],
        "hilos_lectura":   m["n_lec"],
        "hilos_escritura": m["n_esc"],
        "lec_requests":    lec["total_requests"],
        "lec_exitosos":    lec["total_requests"] - lec["errores"],
        "lec_errores":     lec["errores"],
        "lec_error_%":     round(lec["error_rate"] * 100, 1),
        "lec_avg_paginas": lec["avg_paginas"] if lec["avg_paginas"] is not None else "",
        "lec_promedio_ms": lec["promedio_ms"],
        "lec_mediana_ms":  lec["mediana_ms"],
        "lec_p95_ms":      lec["p95_ms"],
        "lec_min_ms":      lec["min_ms"],
        "lec_max_ms":      lec["max_ms"],
        "esc_requests":    esc["total_requests"],
        "esc_exitosos":    esc["total_requests"] - esc["errores"],
        "esc_errores":     esc["errores"],
        "esc_error_%":     round(esc["error_rate"] * 100, 1),
        "esc_promedio_ms": esc["promedio_ms"],
        "esc_mediana_ms":  esc["mediana_ms"],
        "esc_p95_ms":      esc["p95_ms"],
        "esc_min_ms":      esc["min_ms"],
        "esc_max_ms":      esc["max_ms"],
        "duracion_total_s": m["duracion_total_s"],
    }


def guardar_csv(filas: list[dict], nombre: str, fieldnames: list[str] | None = None):
    if fieldnames is None:
        fieldnames = FIELDNAMES
    filename = f"{nombre}.csv" if not nombre.endswith(".csv") else nombre
    with open(filename, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(filas)
    print(f"  Resultados guardados en {filename}")


def modo_concurrente(s: requests.Session):
    while True:
        try:
            n = int(input("\nNivel máximo de hilos: ").strip())
            if n < 1:
                raise ValueError
        except ValueError:
            print("Ingresa un número entero positivo.")
            continue

        paso = max(1, n // 10)
        niveles = list(range(paso, n + 1, paso))
        if niveles[-1] != n:
            niveles.append(n)

        print(f"\nNiveles a ejecutar: {niveles}")
        todas_las_filas: list[dict] = []

        for i, nivel in enumerate(niveles, start=1):
            print(f"\n[{i}/{len(niveles)}] Lanzando {nivel} hilos ...")
            metricas = ejecutar_carga(s, nivel)
            mostrar_metricas(metricas)
            todas_las_filas.append(metricas_a_fila(i, metricas))

        print(f"\n{'=' * 60}")
        print(f"  RESUMEN — {len(niveles)} niveles completados")
        print(f"{'=' * 60}")
        print(f"  {'Nivel':<6} {'Hilos':<7} {'Requests':<10} {'Errores':<9} {'Err%':<7} {'Avg ms':<9} {'P95 ms'}")
        for fila in todas_las_filas:
            print(f"  {fila['nivel']:<6} {fila['hilos']:<7} {fila['total_requests']:<10} "
                  f"{fila['errores']:<9} {fila['error_rate_%']:<7} {fila['promedio_ms']:<9} {fila['p95_ms']}")
        print(f"{'=' * 60}")

        nombre = input("\nNombre del archivo CSV (Enter para omitir): ").strip()
        if nombre:
            guardar_csv(todas_las_filas, nombre)

        accion = input("\n[r] re-ejecutar  |  [q] volver al menú: ").strip().lower()
        if accion != "r":
            break


def modo_mixto(s: requests.Session):
    while True:
        try:
            n = int(input("\nNivel máximo de hilos (se dividirá en mitad lectura / mitad escritura): ").strip())
            if n < 2:
                raise ValueError
        except ValueError:
            print("Ingresa un número entero >= 2.")
            continue

        paso   = max(2, n // 10)
        niveles = list(range(paso, n + 1, paso))
        if niveles[-1] != n:
            niveles.append(n)

        print(f"\nNiveles a ejecutar: {niveles}")
        todas_las_filas: list[dict] = []

        for i, nivel in enumerate(niveles, start=1):
            n_lec = nivel // 2
            n_esc = nivel - n_lec
            print(f"\n[{i}/{len(niveles)}] Lanzando {nivel} hilos ({n_lec} lectura / {n_esc} escritura) ...")
            m = ejecutar_carga_mixta(s, nivel)
            mostrar_metricas_mixta(m)
            todas_las_filas.append(metricas_a_fila_mixta(i, m))

        print(f"\n{'=' * 60}")
        print(f"  RESUMEN MIXTO — {len(niveles)} niveles")
        print(f"{'=' * 60}")
        print(f"  {'Niv':<4} {'Hilos':<6} {'LecErr%':<9} {'LecAvgMs':<10} {'EscErr%':<9} {'EscAvgMs'}")
        for fila in todas_las_filas:
            print(f"  {fila['nivel']:<4} {fila['hilos_total']:<6} "
                  f"{fila['lec_error_%']:<9} {fila['lec_promedio_ms']:<10} "
                  f"{fila['esc_error_%']:<9} {fila['esc_promedio_ms']}")
        print(f"{'=' * 60}")

        nombre = input("\nNombre del archivo CSV (Enter para omitir): ").strip()
        if nombre:
            guardar_csv(todas_las_filas, nombre, fieldnames=FIELDNAMES_MIXTO)

        accion = input("\n[r] re-ejecutar  |  [q] volver al menú: ").strip().lower()
        if accion != "r":
            break


# ── Despachos por estado ─────────────────────────────────────────────────────

_ESTADOS_DESPACHO = {
    "1": "recibido",
    "2": "asignado",
    "3": "finalizado",
    "4": "cancelado",
    "5": "programado",
    "6": "emergencia",
}


def modo_despachos_estado(s: requests.Session):
    while True:
        print(f"\n{'=' * 60}")
        print("  DESPACHOS POR ESTADO")
        print("=" * 60)
        for k, v in _ESTADOS_DESPACHO.items():
            print(f"  [{k}] {v}")
        print("  [a] todos (sin filtro)")
        print("  [q] Volver al menú principal")
        opcion = input("\nEstado: ").strip().lower()

        if opcion == "q":
            break

        if opcion == "a":
            url: str | None = DESPACHOS_ALL_URL
        elif opcion in _ESTADOS_DESPACHO:
            url = f"{DESPACHOS_ALL_URL}?estado={_ESTADOS_DESPACHO[opcion]}"
        else:
            print("  Opción no válida.")
            continue

        page_num = 1
        while url:
            print(f"\n{'=' * 60}")
            print(f"  Página {page_num}  |  {url}")
            print("=" * 60)

            data = fetch_page(s, url)
            if data is None:
                break

            results = data.get("results", [])
            print(f"Resultados en esta página: {len(results)}")
            print(json.dumps(data, indent=2, ensure_ascii=False))

            next_url = data.get("next")
            print(f"\n  next     → {next_url}")
            print(f"  previous → {data.get('previous')}")

            if not next_url:
                print("\nFin de los resultados.")
                break

            action = input("\n[Enter] siguiente  |  [q] salir: ").strip().lower()
            if action == "q":
                break

            url = next_url
            page_num += 1


# ── Notificaciones ────────────────────────────────────────────────────────────

ESTADOS_AMBULANCIA = {
    "1": ("Disponible",        "Ambulancia prepara para ser usada"),
    "2": ("En preparacion",    "Ambulancia está realizando actividades previas para poder operar con normalidad"),
    "3": ("Trabajando",        "Ambulancia se encuentra operando"),
    "4": ("Mantención",        "Ambulancia se encuentra en mantención"),
    "5": ("Fuera de servicio", "Ambulancia fuera de Servicio"),
}


def _notif_result(r: requests.Response):
    ok = r.status_code < 400
    tag = "OK " if ok else "ERR"
    print(f"  [{tag}] HTTP {r.status_code}  →  {r.text[:300]}")
    if ok:
        print("  Notificacion enviada a Celery — revisa los logs del worker para confirmar entrega FCM.")


def _csrf_headers(s: requests.Session) -> dict:
    return {**HEADERS_BASE, "X-CSRFToken": s.cookies.get("csrftoken", "")}


def notif_emergencia(s: requests.Session):
    print("\n-- Notificacion: EMERGENCIA --")
    print("  Llama a /api/despachos/asignar/ con is_emergency=True.")
    try:
        amb_id      = int(input("  amb_id      : ").strip())
        despacho_id = int(input("  despacho_id : ").strip())
        grupo_id    = int(input("  grupo_id    : ").strip())
    except ValueError:
        print("  Valor inválido, cancelando.")
        return
    r = s.post(ASIGNAR_URL, json={
        "is_emergency": True,
        "amb_id": amb_id,
        "despacho_id": despacho_id,
        "grupo_id": grupo_id,
    }, headers=_csrf_headers(s))
    _notif_result(r)


def notif_programado(s: requests.Session):
    print("\n-- Notificacion: DESPACHO PROGRAMADO --")
    print("  Llama a /api/despachos/programar/.")
    print("  AVISO: existe un bug activo — views.py dispara type='DP' pero la tarea")
    print("  compara contra Despacho.PROGRAMADO='programado', por lo que la notificacion")
    print("  nunca llega a los dispositivos aunque el endpoint devuelva 200.")
    try:
        despacho_id      = int(input("  despacho_id      : ").strip())
        grupo_id         = int(input("  grupo_id         : ").strip())
        fecha_programada = input("  fecha_programada (YYYY-MM-DDTHH:MM:SS): ").strip()
    except ValueError:
        print("  Valor inválido, cancelando.")
        return
    r = s.post(PROGRAMAR_URL, json={
        "despacho_id": despacho_id,
        "grupo_id": grupo_id,
        "fecha_programada": fecha_programada,
    }, headers=_csrf_headers(s))
    _notif_result(r)


def notif_atencion_registrada(s: requests.Session):
    print("\n-- Notificacion: ATENCION REGISTRADA --")
    print("  Llama a /api/atenciones/add/ — también marca el despacho como finalizado.")
    try:
        despacho_id   = int(input("  despacho_id   : ").strip())
        ambulancia_id = int(input("  ambulancia_id : ").strip())
        rut_receptor  = input("  rut_receptor  : ").strip()
        hora_salida   = input("  hora_salida (YYYY-MM-DDTHH:MM:SS): ").strip()
    except ValueError:
        print("  Valor inválido, cancelando.")
        return
    payload = {
        "despacho": {
            "despacho_id": despacho_id,
            "ambulancia_id": ambulancia_id,
            "hora_salida": hora_salida,
        },
        "signos_vitales": [],
        "preinforme": {},
        "cronologia": {},
        "insumos_utilizados": [],
        "rut_receptor": rut_receptor,
    }
    r = s.post(ATENCION_URL, json=payload, headers=_csrf_headers(s))
    _notif_result(r)


def notif_estado_ambulancia(s: requests.Session):
    print("\n-- Notificacion: ESTADO AMBULANCIA --")
    print("  Llama a PATCH /api/ambulancias/estados/ — notifica al rol 'control'.")
    print("  Elige el estado:")
    for k, (label, _) in ESTADOS_AMBULANCIA.items():
        print(f"    [{k}] {label}")
    opcion = input("  Opción: ").strip()
    if opcion not in ESTADOS_AMBULANCIA:
        print("  Opción no válida.")
        return
    label, estado_valor = ESTADOS_AMBULANCIA[opcion]
    try:
        ambid = int(input("  ambid (ID ambulancia): ").strip())
        conid = int(input("  conid (ID personal)  : ").strip())
    except ValueError:
        print("  Valor inválido, cancelando.")
        return
    print(f"  Enviando estado: {label}")
    r = s.patch(ESTADOS_URL, params={"ambid": ambid, "conid": conid, "estado": estado_valor},
                headers=_csrf_headers(s))
    _notif_result(r)


def modo_notificaciones(s: requests.Session):
    while True:
        print(f"\n{'=' * 60}")
        print("  NOTIFICACIONES — elige cuál probar")
        print("=" * 60)
        print("  [1] Emergencia          → asignar despacho con is_emergency=True")
        print("  [2] Despacho programado → programar despacho (tiene bug activo)")
        print("  [3] Atencion registrada → registrar atención (también finaliza despacho)")
        print("  [4] Estado ambulancia   → cambiar estado (DISPONIBLE/TRABAJANDO/etc.)")
        print("  [q] Volver al menú principal")
        opcion = input("\nOpción: ").strip().lower()

        if   opcion == "1": notif_emergencia(s)
        elif opcion == "2": notif_programado(s)
        elif opcion == "3": notif_atencion_registrada(s)
        elif opcion == "4": notif_estado_ambulancia(s)
        elif opcion == "q": break
        else:               print("  Opción no válida.")


# ── Verificador de documentos ─────────────────────────────────────────────────

def modo_verificar_documento(s: requests.Session):
    while True:
        print(f"\n{'=' * 60}")
        print("  VERIFICAR DOCUMENTO")
        print("=" * 60)
        print("  Ingresa el hash SHA-256 del documento (64 caracteres hex).")
        print("  Opcionalmente ingresa la firma en base64 para validarla también.")
        print("  [q] Volver al menú principal")
        hash_input = input("\n  Hash: ").strip().lower()
        if hash_input == "q":
            break
        if len(hash_input) != 64 or not all(c in "0123456789abcdef" for c in hash_input):
            print("  Hash inválido — debe ser 64 caracteres hexadecimales.")
            continue

        firma_input = input("  Firma base64 (Enter para omitir): ").strip()

        params = {"hash": hash_input}
        if firma_input:
            params["firma"] = firma_input

        r = s.get(VERIFICAR_URL, params=params, headers=_csrf_headers(s))

        print(f"\n  HTTP {r.status_code}")
        if r.status_code != 200:
            print(f"  [ERR] {r.text[:300]}")
            continue

        data = r.json()
        print(f"\n  {'='*40}")
        valido = data.get("valido", False)
        print(f"  RESULTADO GLOBAL : {'VALIDO' if valido else 'INVALIDO'}")
        print(f"  {'='*40}")
        print(f"  Hash verificado  : {'OK' if data.get('hash_valido') else 'FALLO'}")
        print(f"  Firma S3 verificada : {'OK' if data.get('firma_s3_valida') else 'FALLO'}")
        if "firma_parametro_valida" in data:
            print(f"  Firma parametro  : {'OK' if data['firma_parametro_valida'] else 'FALLO'}")
        print(f"  Atencion ID      : {data.get('atencion_id')}")
        print(f"  Creado en        : {data.get('creado_en')}")
        print(f"  {'='*40}")

        accion = input("\n  [Enter] verificar otro  |  [q] volver: ").strip().lower()
        if accion == "q":
            break


# ── Registrar atención ────────────────────────────────────────────────────────

def _pedir_int_opcional(prompt: str) -> int | None:
    val = input(prompt).strip()
    if val == "":
        return None
    try:
        return int(val)
    except ValueError:
        print("  Valor inválido, se usará null.")
        return None


def _pedir_signos_vitales() -> list[dict]:
    signos: list[dict] = []
    print("\n  -- Signos vitales --")
    print("  Ingresa una medición por vez. Enter vacío en 'hora' para terminar.")
    while True:
        hora = input("  hora (HHMM, Enter para terminar): ").strip()
        if hora == "":
            break
        sv: dict = {
            "hora":               hora,
            "presion_sistolica":  _pedir_int_opcional("    presion_sistolica  (Enter=null): "),
            "presion_diastolica": _pedir_int_opcional("    presion_diastolica (Enter=null): "),
            "frecuencia_cardiaca":_pedir_int_opcional("    frecuencia_cardiaca(Enter=null): "),
            "saturacion_oxigeno": _pedir_int_opcional("    saturacion_oxigeno (Enter=null): "),
            "fr":                 _pedir_int_opcional("    fr                 (Enter=null): "),
            "fio2":               _pedir_int_opcional("    fio2               (Enter=null): "),
            "hgt":                _pedir_int_opcional("    hgt                (Enter=null): "),
            "gcs":                _pedir_int_opcional("    gcs                (Enter=null): "),
            "eva":                _pedir_int_opcional("    eva                (Enter=null): "),
            "temperatura":        input("    temperatura        (Enter=null): ").strip() or None,
            "observaciones":      input("    observaciones      : ").strip(),
        }
        # strip None temperatura if blank
        if sv["temperatura"] is not None:
            try:
                sv["temperatura"] = float(sv["temperatura"])
            except ValueError:
                print("    Temperatura inválida, se usará null.")
                sv["temperatura"] = None
        signos.append(sv)
    return signos


def _pedir_insumos() -> list[dict]:
    insumos: list[dict] = []
    print("\n  -- Insumos utilizados --")
    print("  Ingresa un insumo por vez. Enter vacío en 'presentacion_id' para terminar.")
    while True:
        pid = input("  presentacion_id (Enter para terminar): ").strip()
        if pid == "":
            break
        try:
            pid_int = int(pid)
        except ValueError:
            print("  ID inválido, saltando.")
            continue
        try:
            cantidad = int(input("  cantidad_usada: ").strip())
        except ValueError:
            print("  Cantidad inválida, saltando.")
            continue
        obs = input("  observaciones (Enter para omitir): ").strip()
        insumos.append({
            "presentacion_id": pid_int,
            "cantidad_usada":  cantidad,
            "observaciones":   obs,
        })
    return insumos


def modo_registrar_atencion(s: requests.Session):
    while True:
        print(f"\n{'=' * 60}")
        print("  REGISTRAR ATENCIÓN")
        print("=" * 60)
        print("  [q] Volver al menú principal")

        # ── despacho ────────────────────────────────────────────────
        try:
            despacho_id   = int(input("\n  despacho_id   : ").strip())
            ambulancia_id = int(input("  ambulancia_id : ").strip())
        except ValueError:
            print("  Valor inválido, cancelando.")
            accion = input("\n  [r] reintentar  |  [q] volver: ").strip().lower()
            if accion != "r":
                break
            continue

        hora_salida  = input("  hora_salida  (YYYY-MM-DDTHH:MM:SS): ").strip()
        hora_llegada = input("  hora_llegada (YYYY-MM-DDTHH:MM:SS, Enter para omitir): ").strip() or None
        rut_receptor = input("  rut_receptor : ").strip()

        # ── signos vitales ───────────────────────────────────────────
        signos = _pedir_signos_vitales()

        # ── preinforme ───────────────────────────────────────────────
        print("\n  -- Pre-informe --")
        preinforme = {
            "pre_informe":     input("  pre_informe     : ").strip(),
            "motivo_llamado":  input("  motivo_llamado  : ").strip(),
            "estado_paciente": input("  estado_paciente : ").strip(),
        }

        # ── cronología ───────────────────────────────────────────────
        print("\n  -- Cronología (HHMM, Enter=null) --")
        cronologia = {
            "hora_llamada":   input("  hora_llamada   : ").strip() or None,
            "despacho_movil": input("  despacho_movil : ").strip() or None,
            "llegada_qth1":   input("  llegada_qth1   : ").strip() or None,
            "salida_qth1":    input("  salida_qth1    : ").strip() or None,
            "llegada_qth2":   input("  llegada_qth2   : ").strip() or None,
            "salida_qth2":    input("  salida_qth2    : ").strip() or None,
            "categoria":      input("  categoria (ej. C1): ").strip(),
        }

        # ── insumos ──────────────────────────────────────────────────
        insumos = _pedir_insumos()

        # ── payload ──────────────────────────────────────────────────
        payload = {
            "despacho": {
                "despacho_id":   despacho_id,
                "ambulancia_id": ambulancia_id,
                "hora_salida":   hora_salida,
                **({"hora_llegada": hora_llegada} if hora_llegada else {}),
            },
            "signos_vitales":     signos,
            "preinforme":         preinforme,
            "cronologia":         cronologia,
            "insumos_utilizados": insumos,
            "rut_receptor":       rut_receptor,
        }

        print(f"\n  Payload:\n{json.dumps(payload, indent=2, ensure_ascii=False)}")
        confirmar = input("\n  ¿Enviar? [s/N]: ").strip().lower()
        if confirmar != "s":
            print("  Cancelado.")
        else:
            r = s.post(ATENCION_URL, json=payload, headers=_csrf_headers(s))
            _notif_result(r)
            if r.status_code < 400:
                try:
                    data = r.json()
                    print(f"  Hash del documento : {data.get('hash', 'N/A')}")
                except Exception:
                    pass

        accion = input("\n  [r] registrar otra  |  [q] volver: ").strip().lower()
        if accion != "r":
            break


# ── Atención rápida (payload predeterminado) ──────────────────────────────────

_DEFAULT_RUT_RECEPTOR = "0-0"

_DEFAULT_SIGNOS = [
    {
        "hora":               "0800",
        "presion_sistolica":  120,
        "presion_diastolica": 80,
        "frecuencia_cardiaca":72,
        "saturacion_oxigeno": 98,
        "fr":                 16,
        "fio2":               21,
        "hgt":                100,
        "gcs":                15,
        "eva":                2,
        "temperatura":        36.5,
        "observaciones":      "",
    }
]

_DEFAULT_PREINFORME = {
    "pre_informe":     "Paciente en buen estado general",
    "motivo_llamado":  "Evaluacion de rutina",
    "estado_paciente": "Estable",
}

_DEFAULT_CRONOLOGIA = {
    "hora_llamada":   "0750",
    "despacho_movil": "0800",
    "llegada_qth1":   "0810",
    "salida_qth1":    "0815",
    "llegada_qth2":   "0820",
    "salida_qth2":    "0825",
    "categoria":      "C1",
}


def _fetch_despacho(s: requests.Session, despacho_id: int) -> dict | None:
    """GET /api/despachos/all/{id}/ — returns the despacho dict or None on error."""
    r = s.get(
        f"{DESPACHOS_ALL_URL}{despacho_id}/",
        headers=_csrf_headers(s),
    )
    if r.status_code != 200:
        print(f"  [ERR] No se pudo obtener el despacho [{r.status_code}]: {r.text[:200]}")
        return None
    return r.json()


def _resultado_atencion(r: requests.Response):
    ok = r.status_code < 400
    tag = "OK " if ok else "ERR"
    print(f"  [{tag}] HTTP {r.status_code}")
    if ok:
        try:
            data = r.json()
            print(f"  Hash   : {data.get('hash', 'N/A')}")
            print(f"  Estado : Enviado correctamente")
        except Exception:
            print(f"  {r.text[:300]}")
    else:
        print(f"  {r.text[:300]}")


def _fetch_ambulancia_y_paciente(s, despacho_id):
    despacho = _fetch_despacho(s, despacho_id)
    if despacho is None:
        return None, None, None
    ambulancia_id = despacho.get("ambulancia_id")
    if not ambulancia_id:
        print("  [ERR] El despacho no tiene ambulancia asignada — ¿está en estado 'asignado'?")
        return None, None, None
    rut_paciente = (despacho.get("paciente") or {}).get("rut")
    if not rut_paciente:
        print("  [ERR] El despacho no tiene paciente asociado.")
        return None, None, None
    return ambulancia_id, rut_paciente, despacho


def modo_atencion_rapida(s: requests.Session):
    print(f"\n{'=' * 60}")
    print("  PAYLOAD PREDETERMINADO")
    print("=" * 60)
    print(f"  rut_receptor  : {_DEFAULT_RUT_RECEPTOR}")
    print(f"  signos_vitales: 1 entrada con valores típicos")
    print(f"  cronologia    : {_DEFAULT_CRONOLOGIA}")
    print(f"  insumos       : [] (vacío)")
    print(f"  paciente      : solo RUT (sin actualizar datos del paciente)")
    print(f"  hora_salida   : se genera al momento del envío")

    while True:
        print(f"\n{'─' * 60}")
        entrada = input("  despacho_id (o [q] para volver): ").strip().lower()
        if entrada == "q":
            break
        try:
            despacho_id = int(entrada)
        except ValueError:
            print("  ID inválido.")
            continue

        ambulancia_id, rut_paciente, _ = _fetch_ambulancia_y_paciente(s, despacho_id)
        if ambulancia_id is None:
            continue

        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        payload = {
            "despacho": {
                "despacho_id":   despacho_id,
                "ambulancia_id": ambulancia_id,
                "hora_salida":   now,
            },
            "paciente":           {"rut": rut_paciente},
            "signos_vitales":     _DEFAULT_SIGNOS,
            "preinforme":         _DEFAULT_PREINFORME,
            "cronologia":         _DEFAULT_CRONOLOGIA,
            "insumos_utilizados": [],
            "rut_receptor":       _DEFAULT_RUT_RECEPTOR,
        }

        print(f"\n  ambulancia_id : {ambulancia_id}")
        print(f"  rut_paciente  : {rut_paciente}")
        print(f"  hora_salida   : {now}")

        _resultado_atencion(s.post(ATENCION_URL, json=payload, headers=_csrf_headers(s)))


# ── Atención con datos de paciente ────────────────────────────────────────────

def modo_atencion_con_paciente(s: requests.Session):
    print(f"\n{'=' * 60}")
    print("  ATENCIÓN + DATOS DE PACIENTE")
    print("=" * 60)
    print("  Igual que atención rápida, pero permite enviar campos")
    print("  opcionales del paciente. Solo se actualizan los que")
    print("  reciban un valor — los vacíos se ignoran.")

    while True:
        print(f"\n{'─' * 60}")
        entrada = input("  despacho_id (o [q] para volver): ").strip().lower()
        if entrada == "q":
            break
        try:
            despacho_id = int(entrada)
        except ValueError:
            print("  ID inválido.")
            continue

        ambulancia_id, rut_paciente, _ = _fetch_ambulancia_y_paciente(s, despacho_id)
        if ambulancia_id is None:
            continue

        print(f"\n  rut_paciente  : {rut_paciente}")
        print("  -- Datos opcionales del paciente (Enter = no actualizar) --")
        fecha_nacimiento   = input("  fecha_nacimiento   (YYYY-MM-DD)  : ").strip() or None
        telefono           = input("  telefono                         : ").strip()
        condicion_paciente = input("  condicion_paciente               : ").strip()

        paciente_payload = {"rut": rut_paciente}
        if fecha_nacimiento:
            paciente_payload["fecha_nacimiento"] = fecha_nacimiento
        if telefono:
            paciente_payload["telefono"] = telefono
        if condicion_paciente:
            paciente_payload["condicion_paciente"] = condicion_paciente

        campos_a_actualizar = [k for k in paciente_payload if k != "rut"]
        if campos_a_actualizar:
            print(f"\n  Campos que se actualizarán: {', '.join(campos_a_actualizar)}")
        else:
            print("\n  Sin campos de paciente a actualizar.")

        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        payload = {
            "despacho": {
                "despacho_id":   despacho_id,
                "ambulancia_id": ambulancia_id,
                "hora_salida":   now,
            },
            "paciente":           paciente_payload,
            "signos_vitales":     _DEFAULT_SIGNOS,
            "preinforme":         _DEFAULT_PREINFORME,
            "cronologia":         _DEFAULT_CRONOLOGIA,
            "insumos_utilizados": [],
            "rut_receptor":       _DEFAULT_RUT_RECEPTOR,
        }

        _resultado_atencion(s.post(ATENCION_URL, json=payload, headers=_csrf_headers(s)))


# ── Señales ───────────────────────────────────────────────────────────────────

def senal_otro(s: requests.Session):
    print("\n-- Señal: OTRO --")
    print("  Envía un mensaje libre a todos los usuarios de control.")
    mensaje = input("  mensaje (max 500 chars): ").strip()
    if not mensaje:
        print("  Mensaje vacío, cancelando.")
        return
    r = s.post(SENALES_URL, params={"type": "senal_otro"},
               json={"mensaje": mensaje}, headers=_csrf_headers(s))
    _notif_result(r)


def senal_ambulancia(s: requests.Session):
    print("\n-- Señal: AMBULANCIA EN PREPARACIÓN --")
    print("  Marca la ambulancia como 'En preparación' y notifica a control.")
    patente = input("  patente: ").strip()
    if not patente:
        print("  Patente vacía, cancelando.")
        return
    r = s.post(SENALES_URL, params={"type": "senal_ambulancia"},
               json={"patente": patente}, headers=_csrf_headers(s))
    _notif_result(r)


def senal_ocupada(s: requests.Session):
    print("\n-- Señal: AMBULANCIA OCUPADA --")
    print("  Marca la ambulancia como 'Actualmente en despacho' y notifica a control.")
    patente = input("  patente: ").strip()
    if not patente:
        print("  Patente vacía, cancelando.")
        return
    r = s.post(SENALES_URL, params={"type": "senal_ocupada"},
               json={"patente": patente}, headers=_csrf_headers(s))
    _notif_result(r)


def senal_outofservice(s: requests.Session):
    print("\n-- Señal: FALLA MECÁNICA (FUERA DE SERVICIO) --")
    print("  Marca la ambulancia como 'Fuera de servicio' y notifica a control.")
    patente = input("  patente: ").strip()
    if not patente:
        print("  Patente vacía, cancelando.")
        return
    r = s.post(SENALES_URL, params={"type": "senal_outofservice"},
               json={"patente": patente}, headers=_csrf_headers(s))
    _notif_result(r)


def _senal_equipo_global(s: requests.Session, tipo: str, label: str):
    print(f"\n-- Señal global: {label} --")
    print("  El servidor resolverá el grupo del usuario autenticado automáticamente.")
    r = s.post(SENALES_URL, params={"type": tipo}, headers=_csrf_headers(s))
    _notif_result(r)


def _senal_equipo_despacho(s: requests.Session, tipo: str, label: str):
    print(f"\n-- Señal de despacho: {label} --")
    entrada = input("  despacho_id: ").strip()
    try:
        despacho_id = int(entrada)
    except ValueError:
        print("  ID inválido, cancelando.")
        return
    r = s.post(SENALES_URL, params={"type": tipo, "despacho_id": despacho_id}, headers=_csrf_headers(s))
    _notif_result(r)


def modo_senales(s: requests.Session):
    while True:
        print(f"\n{'=' * 60}")
        print("  SEÑALES — elige cuál probar")
        print("=" * 60)
        print("  -- Globales (sin despacho) --")
        print("  [1] Otro...           → mensaje libre a control")
        print("  [2] Falla ambulancia  → notifica a control (sin cambio de estado)")
        print("  [3] Ambulancia ocupada → notifica a control (sin cambio de estado)")
        print("  [4] Fuera de servicio → falla mecánica, notifica a control")
        print("  [5] Disponible        → equipo listo para nuevo despacho")
        print("  [6] Regresando        → equipo regresando a base")
        print("  -- Vinculadas a despacho (requieren despacho_id) --")
        print("  [7] En camino         → equipo en camino al destino del despacho")
        print("  [8] En destino        → equipo llegó al destino del despacho")
        print("  [9] Operando          → equipo comenzó a operar en el despacho")
        print("  [q] Volver al menú principal")
        opcion = input("\nOpción: ").strip().lower()

        if   opcion == "1": senal_otro(s)
        elif opcion == "2": senal_ambulancia(s)
        elif opcion == "3": senal_ocupada(s)
        elif opcion == "4": senal_outofservice(s)
        elif opcion == "5": _senal_equipo_global(s,   "senal_disponible", "DISPONIBLE")
        elif opcion == "6": _senal_equipo_global(s,   "senal_regresando", "REGRESANDO")
        elif opcion == "7": _senal_equipo_despacho(s, "senal_en_camino",  "EN CAMINO")
        elif opcion == "8": _senal_equipo_despacho(s, "senal_en_destino", "EN DESTINO")
        elif opcion == "9": _senal_equipo_despacho(s, "senal_operando",   "OPERANDO")
        elif opcion == "q": break
        else:               print("  Opción no válida.")


# ── Cancelar despacho ─────────────────────────────────────────────────────────

def modo_cancelar_despacho(s: requests.Session):
    while True:
        print(f"\n{'=' * 60}")
        print("  CANCELAR DESPACHO")
        print("=" * 60)
        print("  Solo control puede cancelar. Si el despacho tiene un grupo")
        print("  asignado, ese grupo recibirá una notificación FCM.")
        print("  [q] Volver al menú principal")

        entrada = input("\n  despacho_id: ").strip().lower()
        if entrada == "q":
            break
        try:
            despacho_id = int(entrada)
        except ValueError:
            print("  ID inválido.")
            continue

        despacho = _fetch_despacho(s, despacho_id)
        if despacho is None:
            continue

        print(f"\n  Estado actual : {despacho.get('estado')}")
        print(f"  Paciente      : {(despacho.get('paciente') or {}).get('nombre_completo', 'N/A')}")
        confirmar = input("  ¿Cancelar este despacho? [s/N]: ").strip().lower()
        if confirmar != "s":
            print("  Cancelado.")
            continue

        r = s.patch(CANCELAR_URL, params={"cancel": despacho_id}, headers=_csrf_headers(s))
        ok = r.status_code < 400
        tag = "OK " if ok else "ERR"
        print(f"  [{tag}] HTTP {r.status_code}  →  {r.text[:300]}")
        if ok:
            print("  Despacho cancelado. Si tenía grupo asignado, la notificación FCM fue encolada en Celery.")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    s = requests.Session()

    if not autenticar(s):
        print("Autenticación fallida, abortando.")
        return

    while True:
        print("\n  [1] Navegar páginas del paginator (logs)")
        print("  [2] Test de carga concurrente (solo lectura)")
        print("  [3] Test de carga mixto (lectura + escritura)")
        print("  [4] Probar notificaciones FCM")
        print("  [5] Verificar documento (hash + firma)")
        print("  [6] Despachos por estado (filtro ?estado=)")
        print("  [7] Registrar atención (flujo completo)")
        print("  [8] Atención rápida (payload predeterminado)")
        print("  [9] Atención con datos de paciente (fecha_nacimiento / telefono / condicion)")
        print("  [10] Señales (otro / ambulancia / ocupada / fuera de servicio)")
        print("  [11] Cancelar despacho")
        print("  [q] Salir")
        opcion = input("\nOpción: ").strip().lower()

        if   opcion == "1":
            modo_paginas(s)
        elif opcion == "2":
            modo_concurrente(s)
        elif opcion == "3":
            modo_mixto(s)
        elif opcion == "4":
            modo_notificaciones(s)
        elif opcion == "5":
            modo_verificar_documento(s)
        elif opcion == "6":
            modo_despachos_estado(s)
        elif opcion == "7":
            modo_registrar_atencion(s)
        elif opcion == "8":
            modo_atencion_rapida(s)
        elif opcion == "9":
            modo_atencion_con_paciente(s)
        elif opcion == "10":
            modo_senales(s)
        elif opcion == "11":
            modo_cancelar_despacho(s)
        elif opcion == "q":
            break
        else:
            print("Opción no válida.")


if __name__ == "__main__":
    main()
