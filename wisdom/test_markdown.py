"""El markdown del consejero se convierte a HTML sin dejar pasar etiquetas."""
from wisdom.templatetags.wisdom_extras import markdown


def test_titulos_y_parrafos():
    html = markdown("## Qué hacer\n\nLlama a tres clientes.")
    assert "<h3>Qué hacer</h3>" in html
    assert "<p>Llama a tres clientes.</p>" in html


def test_listas_y_numeradas():
    html = markdown("- uno\n- dos\n\n1. primero\n2. segundo")
    assert html.count("<li>") == 4
    assert "<ul>" in html and "<ol>" in html


def test_negrita_cursiva_y_codigo():
    html = markdown("**1.500 €** es el *suelo*, usa `manage.py`.")
    assert "<strong>1.500 €</strong>" in html
    assert "<em>suelo</em>" in html
    assert "<code>manage.py</code>" in html


def test_cita_regla_y_bloque_de_codigo():
    html = markdown("> El cobro manda\n\n---\n\n```\npython x\n```")
    assert "<blockquote>" in html
    assert "<hr>" in html
    assert "<pre><code>python x</code></pre>" in html


def test_el_html_de_entrada_se_escapa():
    html = markdown("<script>alert(1)</script>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_texto_vacio():
    assert markdown("") == ""
