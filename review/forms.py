"""Formulario de la revisión semanal."""
from django import forms

from business.forms import CLASES_INPUT

from .models import WeeklyReview

# Métricas que el sistema calcula solo: llegan rellenadas y en solo lectura.
CALCULADAS = [
    "m1_eur_cobrados", "m2_eur_recurrentes", "m3_eur_vencidos",
    "m4_contactos_nuevos", "m5_conversaciones", "m5_propuestas",
    "m6_precio_medio", "m7_tarifa_efectiva", "m8_wip_abierto", "xp_semana",
]

# Lo que el sistema no puede saber.
MANUALES = ["m9_entrenos", "m9_peso_medio", "m10_bloques_intactos", "m8_revision_hecha"]


class WeeklyReviewForm(forms.ModelForm):
    class Meta:
        model = WeeklyReview
        fields = [
            "anio", "semana_iso", "fecha",
            *CALCULADAS, *MANUALES,
            "funciono", "no_funciono", "decision",
            "objetivo_1", "objetivo_2", "objetivo_3",
        ]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "funciono": forms.Textarea(attrs={"rows": 2, "placeholder": "Qué funcionó"}),
            "no_funciono": forms.Textarea(attrs={"rows": 2, "placeholder": "Qué no funcionó"}),
            "decision": forms.Textarea(
                attrs={"rows": 2, "placeholder": "Una decisión para la semana que viene"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, campo in self.fields.items():
            widget = campo.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "h-4 w-4 rounded border-slate-600 bg-slate-950")
            else:
                widget.attrs.setdefault("class", CLASES_INPUT)
            # Las calculadas se muestran, pero no se editan a mano.
            if nombre in CALCULADAS:
                widget.attrs["readonly"] = True
                widget.attrs["tabindex"] = "-1"
        self.fields["anio"].widget = forms.HiddenInput()
        self.fields["semana_iso"].widget = forms.HiddenInput()

    def clean(self):
        datos = super().clean()
        if datos.get("m8_revision_hecha") and not (datos.get("decision") or "").strip():
            self.add_error(
                "decision",
                "Una revisión sin decisión es un informe. Escribe la decisión de la semana.",
            )
        return datos
