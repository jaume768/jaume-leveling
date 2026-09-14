"""Criterios de ascenso de cada rango, en forma comprobable.

El campo `Rank.criterio_ascenso` es el texto del documento. Aqui esta el mismo
criterio partido en requisitos que el sistema puede medir contra los datos
reales, porque "el ascenso de rango se verifica con numeros, no con sensacion
de progreso" (docs/sistema-v2.md, §4).

Cada requisito es una tupla:

    (clave, texto, objetivo, medidor)

`medidor` es el nombre de una funcion de `core.services` que devuelve el valor
actual. Cuando es None el requisito no se puede medir con los datos que el
sistema guarda (un colchon en el banco, una SL constituida) y se marca a mano
desde el admin; hasta entonces cuenta como no cumplido, que es lo prudente.

Las cifras salen de `Rank.criterio_ascenso` tal y como esta sembrado.
"""

# Contactos por semana que cuentan como "pipeline activo" (docs §7.4).
CONTACTOS_PIPELINE_ACTIVO = 6

CRITERIOS = {
    # II · Operador -> III · Especialista
    2: (
        ("cobrado", "2.000 € cobrados", 2_000, "total_cobrado"),
        ("recurrente", "1 contrato recurrente firmado", 1, "contratos_recurrentes"),
        ("casos", "2 casos publicados", 2, "casos_publicados"),
        (
            "pipeline",
            f"4 semanas seguidas con {CONTACTOS_PIPELINE_ACTIVO} contactos",
            4,
            "semanas_seguidas_con_pipeline",
        ),
    ),
    # III · Especialista -> IV · Constructor de sistemas
    3: (
        ("media", "1.500 €/mes de media 3 meses seguidos", 1_500, "media_mensual_3m"),
        ("recurrente", "800 €/mes recurrentes", 800, "recurrente_mensual"),
        ("precio", "Precio mínimo 1.800 €", 1_800, "precio_minimo_aceptado"),
    ),
    # IV · Constructor -> V · Independiente
    4: (
        ("media", "2.500 €/mes", 2_500, "media_mensual_3m"),
        ("entrega", "Tiempo de entrega −40%", 40, None),
        ("automatizaciones", "2 automatizaciones internas midiendo horas", 2, None),
    ),
    # V · Independiente -> VI · Fundador
    5: (
        ("media", "6 meses con 1.320 €/mes netos", 1_320, "media_mensual_6m"),
        ("colchon", "Colchón de 20.000 €", 20_000, None),
        ("concentracion", "Ningún cliente por encima del 35%", 35, "concentracion_maxima"),
    ),
    # VI · Fundador: el ultimo rango no tiene ascenso.
    6: (
        ("media", "8.000 €/mes", 8_000, "media_mensual_3m"),
        ("equipo", "1-3 colaboradores", 1, None),
        ("sl", "SL constituida", 1, None),
        ("producto", "Línea de producto validada", 1, None),
    ),
}

# Requisitos como "concentracion_maxima" se cumplen por debajo del objetivo,
# no por encima. Aqui se listan los que van al reves.
MENOS_ES_MEJOR = {"concentracion"}
