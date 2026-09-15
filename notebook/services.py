"""Logica de negocio de la app notebook.

El cuaderno junta dos cosas que se escriben por separado: las notas sueltas,
que no cuelgan de nada, y lo apuntado al cerrar una mision. Se muestran juntas
porque cuando buscas algo que escribiste no te acuerdas de donde lo escribiste.
"""
from __future__ import annotations

import datetime as dt

from django.db.models import Q
from django.utils import timezone

from .models import Note

# Cuantos dias de historial se pintan de golpe.
DIAS_POR_PAGINA = 30


def notas_sueltas(busqueda: str = ""):
    consulta = Note.objects.all()
    if busqueda:
        consulta = consulta.filter(
            Q(titulo__icontains=busqueda) | Q(contenido__icontains=busqueda)
        )
    return consulta


def notas_de_misiones(busqueda: str = ""):
    """Lo apuntado al cerrar misiones, en solo lectura desde aqui."""
    from missions.models import MissionLog

    consulta = MissionLog.objects.exclude(notas="").select_related("mission")
    if busqueda:
        consulta = consulta.filter(
            Q(notas__icontains=busqueda) | Q(mission__titulo__icontains=busqueda)
        )
    return consulta.order_by("-fecha")


def _entrada_de_nota(nota: Note) -> dict:
    return {
        "tipo": "nota",
        "fecha": nota.fecha,
        "orden": nota.creada,
        "nota": nota,
        "titulo": nota.encabezado,
        "contenido": nota.contenido,
        "fijada": nota.fijada,
    }


def _entrada_de_mision(registro) -> dict:
    from missions.services import partir_titulo

    _codigo, titulo = partir_titulo(registro.mission.titulo)
    return {
        "tipo": "mision",
        "fecha": registro.fecha,
        "orden": registro.fecha,
        "registro": registro,
        "titulo": titulo,
        "contenido": registro.notas,
        "fijada": False,
    }


def cuaderno(busqueda: str = "", limite_dias: int = DIAS_POR_PAGINA) -> dict:
    """Todo lo escrito, agrupado por dia y con las fijadas arriba."""
    busqueda = (busqueda or "").strip()

    fijadas = [
        _entrada_de_nota(n)
        for n in notas_sueltas(busqueda).filter(fijada=True).order_by("-fecha", "-creada")
    ]

    entradas = [
        _entrada_de_nota(n) for n in notas_sueltas(busqueda).filter(fijada=False)
    ]
    entradas += [_entrada_de_mision(r) for r in notas_de_misiones(busqueda)]

    # Un dia con varias entradas se ordena por lo mas reciente dentro del dia.
    entradas.sort(key=lambda e: (e["fecha"], str(e["orden"])), reverse=True)

    dias: list[dict] = []
    for entrada in entradas:
        if not dias or dias[-1]["fecha"] != entrada["fecha"]:
            if len(dias) >= limite_dias:
                break
            dias.append({"fecha": entrada["fecha"], "entradas": []})
        dias[-1]["entradas"].append(entrada)

    return {
        "fijadas": fijadas,
        "dias": dias,
        "busqueda": busqueda,
        "total_notas": notas_sueltas().count(),
        "hoy": timezone.localdate(),
    }


def crear_nota(contenido: str, titulo: str = "", fecha: dt.date | None = None) -> Note | None:
    """Crea una nota. Devuelve None si no hay nada que guardar."""
    contenido = (contenido or "").strip()
    if not contenido:
        return None
    return Note.objects.create(
        titulo=(titulo or "").strip(),
        contenido=contenido,
        fecha=fecha or timezone.localdate(),
    )


def actualizar_nota(nota: Note, contenido: str, titulo: str = "") -> Note:
    nota.titulo = (titulo or "").strip()
    nota.contenido = (contenido or "").strip()
    nota.save(update_fields=["titulo", "contenido", "actualizada"])
    return nota


def alternar_fijada(nota: Note) -> Note:
    nota.fijada = not nota.fijada
    nota.save(update_fields=["fijada", "actualizada"])
    return nota


def borrar_nota(nota: Note) -> None:
    nota.delete()
