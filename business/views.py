from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import services
from .forms import (
    ClientForm,
    DealDatosForm,
    DealFilaForm,
    DealForm,
    InvoiceForm,
    ProjectForm,
)
from .models import Client, Deal, Invoice, Project


# --- Pipeline ---------------------------------------------------------------


def pipeline(request):
    """Tabla del pipeline, filtrable por estado."""
    estado = request.GET.get("estado", "")
    contexto = services.resumen_pipeline(estado)
    contexto["seccion"] = "pipeline"
    plantilla = (
        "business/_pipeline_tabla.html" if request.htmx else "business/pipeline.html"
    )
    return render(request, plantilla, contexto)


def _fila(request, deal, form=None):
    """Devuelve una sola fila del pipeline, ya actualizada."""
    dias = deal.dias_sin_toque
    return render(
        request,
        "business/_pipeline_fila.html",
        {
            "fila": {"deal": deal, "dias": dias, "alerta": services.nivel_alerta(dias)},
            "form": form,
            "editando": form is not None,
        },
    )


def deal_fila(request, pk):
    """Fila en modo lectura."""
    return _fila(request, get_object_or_404(Deal, pk=pk))


def deal_editar(request, pk):
    """Fila en modo edicion: estado y proximo paso."""
    deal = get_object_or_404(Deal, pk=pk)
    return _fila(request, deal, form=DealFilaForm(instance=deal))


@require_POST
def deal_guardar(request, pk):
    """Guarda la edicion en linea y devuelve la fila."""
    deal = get_object_or_404(Deal, pk=pk)
    estado_anterior = deal.estado
    form = DealFilaForm(request.POST, instance=deal)
    if form.is_valid():
        form.save()
        # El hecho comercial concede su XP aqui, no en una mision inventada.
        for evento in services.puntuar_deal(deal, estado_anterior):
            messages.success(request, f"{evento.descripcion}: +{evento.xp_neto} XP.")
        return _fila(request, deal)
    return _fila(request, deal, form=form)


@require_POST
def deal_toque(request, pk):
    """Toque rapido: ultimo_toque a hoy y XP de accion comercial."""
    deal = get_object_or_404(Deal, pk=pk)
    services.toque_rapido(deal)
    return _fila(request, deal)


def deal_nuevo(request):
    form = DealForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Oportunidad añadida al pipeline.")
        return redirect("business:pipeline")
    return render(
        request,
        "business/formulario.html",
        {"form": form, "titulo": "Nueva oportunidad", "volver": reverse("business:pipeline")},
    )


def deal_datos(request, pk):
    """Corrige los datos de una oportunidad ya creada."""
    deal = get_object_or_404(Deal, pk=pk)
    form = DealDatosForm(request.POST or None, instance=deal)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Oportunidad corregida.")
        return redirect("business:pipeline")
    return render(
        request,
        "business/formulario.html",
        {
            "form": form,
            "titulo": "Editar oportunidad",
            "volver": reverse("business:pipeline"),
            "eliminar": reverse("business:deal_eliminar", args=[deal.pk]),
        },
    )


def deal_eliminar(request, pk):
    """Pregunta y, con el POST, borra la linea del pipeline."""
    deal = get_object_or_404(Deal, pk=pk)
    if request.method == "POST":
        services.eliminar_deal(deal)
        messages.success(request, f"{deal.negocio} eliminado del pipeline.")
        return redirect("business:pipeline")
    return render(
        request,
        "business/confirmar_eliminar.html",
        {
            "titulo": "Eliminar oportunidad",
            "nombre": deal.negocio,
            "aviso": "La línea desaparece del pipeline. La XP que ya haya dado no se retira.",
            "volver": reverse("business:deal_datos", args=[deal.pk]),
        },
    )


# --- Facturas ---------------------------------------------------------------


def facturas(request):
    contexto = services.resumen_facturas()
    contexto["seccion"] = "facturas"
    plantilla = (
        "business/_facturas_bloque.html" if request.htmx else "business/facturas.html"
    )
    return render(request, plantilla, contexto)


def confirmar_cobro(request, pk):
    """Pregunta antes de dar una factura por cobrada.

    Marcarla es irreversible desde la interfaz y concede XP en el acto, asi
    que un toque accidental en el movil no deberia bastar.
    """
    factura = get_object_or_404(Invoice, pk=pk)
    return render(
        request,
        "business/_modal_cobro.html",
        {"factura": factura, "xp": int(factura.importe / services.XP_POR_EURO_COBRADO)},
    )


@require_POST
def factura_cobrar(request, pk):
    """Marca la factura como cobrada y concede 1 XP por cada 10 EUR."""
    services.marcar_cobrada(get_object_or_404(Invoice, pk=pk))
    contexto = services.resumen_facturas()
    contexto["seccion"] = "facturas"
    return render(request, "business/_facturas_bloque.html", contexto)


def factura_nueva(request):
    form = InvoiceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Factura emitida. Vigila el vencimiento.")
        return redirect("business:facturas")
    return render(
        request,
        "business/formulario.html",
        {"form": form, "titulo": "Nueva factura", "volver": reverse("business:facturas")},
    )


# --- Clientes ---------------------------------------------------------------


def clientes(request):
    contexto = services.resumen_clientes()
    contexto["seccion"] = "clientes"
    return render(request, "business/clientes.html", contexto)


def cliente_nuevo(request):
    form = ClientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cliente = form.save()
        messages.success(request, "Cliente creado.")
        for evento in services.puntuar_recurrente(cliente, 0):
            messages.success(request, f"{evento.descripcion}: +{evento.xp_neto} XP.")
        return redirect("business:clientes")
    return render(
        request,
        "business/formulario.html",
        {"form": form, "titulo": "Nuevo cliente", "volver": reverse("business:clientes")},
    )


def cliente_editar(request, pk):
    cliente = get_object_or_404(Client, pk=pk)
    mrr_anterior = cliente.mrr
    form = ClientForm(request.POST or None, instance=cliente)
    if request.method == "POST" and form.is_valid():
        cliente = form.save()
        messages.success(request, "Cliente actualizado.")
        for evento in services.puntuar_recurrente(cliente, mrr_anterior):
            messages.success(request, f"{evento.descripcion}: +{evento.xp_neto} XP.")
        return redirect("business:clientes")
    return render(
        request,
        "business/formulario.html",
        {
            "form": form,
            "titulo": "Editar cliente",
            "volver": reverse("business:clientes"),
            "eliminar": reverse("business:cliente_eliminar", args=[cliente.pk]),
        },
    )


def cliente_eliminar(request, pk):
    """Pregunta y, con el POST, borra el cliente si no tiene historia."""
    cliente = get_object_or_404(Client, pk=pk)
    if request.method == "POST":
        if services.eliminar_cliente(cliente):
            messages.success(request, f"{cliente.nombre} eliminado.")
        else:
            messages.error(
                request,
                f"{cliente.nombre} tiene facturas o proyectos y no se borra. "
                "Márcalo como inactivo o perdido.",
            )
        return redirect("business:clientes")

    ataduras = services.ataduras_de_cliente(cliente)
    return render(
        request,
        "business/confirmar_eliminar.html",
        {
            "titulo": "Eliminar cliente",
            "nombre": cliente.nombre,
            "aviso": "Sus oportunidades del pipeline se quedan, ya sin cliente asignado.",
            "bloqueo": (
                f"Tiene {ataduras['facturas']} facturas y {ataduras['proyectos']} proyectos. "
                "Un cliente con historia no se borra: márcalo como inactivo o perdido."
                if any(ataduras.values())
                else ""
            ),
            "volver": reverse("business:cliente_editar", args=[cliente.pk]),
        },
    )


# --- Proyectos --------------------------------------------------------------


def proyectos(request):
    contexto = services.resumen_proyectos()
    contexto["seccion"] = "proyectos"
    tarifa = services.tarifa_efectiva_mes()
    contexto["tarifa_efectiva"] = tarifa
    contexto["hay_horas"] = tarifa is not None
    return render(request, "business/proyectos.html", contexto)


def proyecto_form(request, pk=None):
    """Alta y edicion de proyecto, con el aviso del suelo de precio.

    Un POST sin el boton "guardar" es una revalidacion en vivo del precio: se
    repinta el formulario con el aviso del suelo, pero sin marcar errores de
    campos que el usuario todavia no ha rellenado.
    """
    proyecto = get_object_or_404(Project, pk=pk) if pk else None
    estado_anterior = proyecto.estado if proyecto else ""
    guardando = request.method == "POST" and "guardar" in request.POST

    if request.method == "POST" and not guardando:
        form = ProjectForm(initial=request.POST.dict(), instance=proyecto)
    else:
        form = ProjectForm(request.POST or None, instance=proyecto)

    if guardando and form.is_valid():
        guardado = form.save()
        if form.hay_excepcion:
            services.registrar_excepcion_de_suelo(
                guardado, form.cleaned_data["motivo_excepcion"].strip()
            )
            messages.warning(
                request,
                "Excepción registrada: −250 XP y motivo documentado. Que sea la última.",
            )
        else:
            messages.success(request, "Proyecto guardado.")
        for evento in services.puntuar_proyecto(guardado, estado_anterior):
            messages.success(request, f"{evento.descripcion}: +{evento.xp_neto} XP.")
        return redirect("business:proyectos")

    contexto = {
        "form": form,
        "titulo": "Editar proyecto" if proyecto else "Nuevo proyecto",
        "volver": reverse("business:proyectos"),
        "suelo": services.suelo_precio(),
    }
    plantilla = (
        "business/_proyecto_form.html" if request.htmx else "business/proyecto_form.html"
    )
    return render(request, plantilla, contexto)


def index(request):
    """Gremio: el resumen del negocio. Las cifras que mandan y el ejercito."""
    from core import services as core_services

    return render(request, "business/gremio.html", core_services.contexto_gremio())
