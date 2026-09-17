"""Formularios de la app business.

El formulario de proyecto no bloquea un precio por debajo del suelo: lo encarece.
"""
from django import forms

from .models import Client, Deal, Invoice, Project
from .services import suelo_precio

CLASES_INPUT = (
    "w-full rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm "
    "text-slate-100 placeholder:text-slate-600 focus:border-slate-500 focus:outline-none"
)


class DealFilaForm(forms.ModelForm):
    """Edicion en linea del pipeline: estado, proximo paso y, si se pierde, el motivo."""

    class Meta:
        model = Deal
        fields = [
            "estado", "proximo_paso", "fecha_proximo_paso",
            "motivo_perdida", "rechazado_por_precio",
        ]
        widgets = {
            "estado": forms.Select(attrs={"class": CLASES_INPUT, "x-model": "estado"}),
            "proximo_paso": forms.TextInput(
                attrs={"class": CLASES_INPUT, "placeholder": "Qué toca hacer"}
            ),
            "fecha_proximo_paso": forms.DateInput(
                attrs={"class": CLASES_INPUT, "type": "date"}, format="%Y-%m-%d"
            ),
            "motivo_perdida": forms.Textarea(
                attrs={"class": CLASES_INPUT, "rows": 2, "placeholder": "Por qué se ha perdido"}
            ),
            "rechazado_por_precio": forms.CheckboxInput(
                attrs={"class": "h-4 w-4 rounded border-slate-600 bg-slate-950"}
            ),
        }

    def clean(self):
        datos = super().clean()
        estado = datos.get("estado")
        motivo = (datos.get("motivo_perdida") or "").strip()
        if estado == Deal.Estado.PERDIDO and not motivo:
            # Un "no" explicado vale mas que diez conversaciones agradables.
            self.add_error(
                "motivo_perdida",
                "Anota el motivo de pérdida: un “no” sin explicar no enseña nada.",
            )
        datos["motivo_perdida"] = motivo
        return datos


class DealForm(forms.ModelForm):
    class Meta:
        model = Deal
        fields = [
            "negocio", "contacto", "canal", "sector", "estado", "valor_potencial",
            "fecha_primer_contacto", "ultimo_toque", "proximo_paso",
            "fecha_proximo_paso", "motivo_perdida", "client",
        ]
        widgets = {
            "fecha_primer_contacto": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "ultimo_toque": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_proximo_paso": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "motivo_perdida": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilar(self)


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["client", "concepto", "importe", "fecha_emision", "vencimiento", "notas"]
        widgets = {
            "fecha_emision": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "vencimiento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notas": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilar(self)


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["nombre", "slug", "sector", "url", "estado", "mrr", "fecha_alta", "notas"]
        widgets = {
            "fecha_alta": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notas": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilar(self)


class ProjectForm(forms.ModelForm):
    """Proyecto con suelo de precio.

    Por debajo de 1.500 € el formulario no se bloquea, pero exige marcar la
    excepción y escribir el motivo. Al guardarlo se registra la penalización
    de -250 XP que manda el documento.
    """

    excepcion_justificada = forms.BooleanField(
        label="Excepción justificada",
        required=False,
        help_text="Marca esta casilla solo si aceptar por debajo del suelo tiene una razón real.",
    )
    motivo_excepcion = forms.CharField(
        label="Motivo de la excepción",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Por qué era una excepción real"}),
    )

    class Meta:
        model = Project
        fields = [
            "client", "nombre", "precio", "horas_estimadas", "horas_reales",
            "estado", "fecha_inicio", "fecha_entrega",
        ]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_entrega": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _estilar(self)

    @property
    def precio_bajo(self) -> bool:
        """True si el precio introducido queda por debajo del suelo."""
        precio = self.data.get("precio") if self.is_bound else None
        if precio in (None, ""):
            precio = self.initial.get("precio") or getattr(self.instance, "precio", None)
        try:
            return precio is not None and float(precio) < float(suelo_precio())
        except (TypeError, ValueError):
            return False

    def clean(self):
        datos = super().clean()
        precio = datos.get("precio")
        suelo = suelo_precio()
        if precio is None or precio >= suelo:
            return datos

        if not datos.get("excepcion_justificada"):
            self.add_error(
                "excepcion_justificada",
                f"{precio:.0f} € está por debajo del suelo de {suelo:.0f} €. "
                "Si aun así lo aceptas, márcalo como excepción: cuesta 250 XP.",
            )
        motivo = (datos.get("motivo_excepcion") or "").strip()
        if datos.get("excepcion_justificada") and not motivo:
            self.add_error(
                "motivo_excepcion",
                "Escribe por qué era una excepción real. Sin motivo escrito no se guarda.",
            )
        return datos

    @property
    def hay_excepcion(self) -> bool:
        return bool(self.cleaned_data.get("excepcion_justificada")) and (
            self.cleaned_data.get("precio") is not None
            and self.cleaned_data["precio"] < suelo_precio()
        )


def _estilar(form: forms.Form) -> None:
    """Aplica las clases de Tailwind a todos los campos del formulario."""
    for campo in form.fields.values():
        widget = campo.widget
        if isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault("class", "h-4 w-4 rounded border-slate-600 bg-slate-950")
        else:
            widget.attrs.setdefault("class", CLASES_INPUT)
