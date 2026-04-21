import os
import re
import io
import requests
from datetime import datetime
from flask import Flask, request, jsonify, send_file, render_template

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, NextPageTemplate
)
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate

app = Flask(__name__)

DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
OPENROUTER_URL   = "https://openrouter.ai/api/v1/chat/completions"

# ─────────────────────────────────────────────
#  UTILIDADES
# ─────────────────────────────────────────────

def limpiar_sin_escape(texto):
    if not texto:
        return ""
    texto = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', texto)
    texto = texto.replace("INFORMÉ", "INFORME")
    texto = texto.replace("Conclusions", "CONCLUSIONES")
    texto = texto.replace("conclusions", "conclusiones")
    return texto.strip()

def escape_xml(texto):
    if not texto:
        return ""
    return texto.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

# ─────────────────────────────────────────────
#  API IA
# ─────────────────────────────────────────────

def llamar_ia(prompt):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://academic-report-pro.onrender.com",
        "X-Title": "Academic Report Pro"
    }
    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 6000,
        "temperature": 0.7
    }
    try:
        r = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=120)
        r.raise_for_status()
        return limpiar_sin_escape(r.json()["choices"][0]["message"]["content"])
    except Exception as e:
        return f"ERROR_IA: {e}"

# ─────────────────────────────────────────────
#  PROMPTS
# ─────────────────────────────────────────────

def construir_prompt(tipo, tema, modo, norma, texto_usuario=""):
    estructuras = {
        "laboratorio": f"""
**TITULO**
**1. INTRODUCCION**
**2. MATERIALES Y REACTIVOS**
**3. PROCEDIMIENTO**
**4. RESULTADOS** (tabla: Prueba | Muestra | Resultado | Observacion)
**5. DISCUSION**
**6. CONCLUSIONES** (5 puntos numerados)
**7. RECOMENDACIONES** (3-4 puntos)
**8. REFERENCIAS** (5-6 en formato {norma})""",
        "tesis": f"""
**RESUMEN**
**1. INTRODUCCION**
**2. PLANTEAMIENTO DEL PROBLEMA**
**3. OBJETIVOS** (1 general + 4 especificos)
**4. MARCO TEORICO**
**5. ESTADO DEL ARTE**
**6. METODOLOGIA**
**7. RESULTADOS Y ANALISIS** (tabla comparativa)
**8. DISCUSION**
**9. CONCLUSIONES** (5 puntos)
**10. RECOMENDACIONES** (3-4 puntos)
**11. REFERENCIAS** (10+ en formato {norma})""",
        "ejecutivo": f"""
**RESUMEN EJECUTIVO**
**1. ANTECEDENTES**
**2. SITUACION ACTUAL** (tabla de indicadores)
**3. HALLAZGOS PRINCIPALES**
**4. ANALISIS COSTO-BENEFICIO**
**5. ALTERNATIVAS DE SOLUCION**
**6. CONCLUSIONES** (5 puntos)
**7. RECOMENDACIONES ESTRATEGICAS** (3-4 puntos)
**8. REFERENCIAS** (3-4 en formato {norma})""",
        "academico": f"""
**INTRODUCCION**
**1. OBJETIVOS** (1 general + 4 especificos)
**2. MARCO TEORICO**
**3. METODOLOGIA**
**4. DESARROLLO** (analisis con tabla)
**5. CONCLUSIONES** (5 puntos numerados)
**6. RECOMENDACIONES** (3-4 puntos)
**7. REFERENCIAS** (5-6 en formato {norma})"""
    }
    est = estructuras.get(tipo, estructuras["academico"])

    if modo == "rapido":
        return f"""Eres un experto academico. Genera un informe completo sobre: "{tema}".
Norma: {norma}.
Usa EXACTAMENTE estos encabezados en negrita:
{est}

REGLAS IMPORTANTES:
- Espanol formal y academico
- Minimo 150 palabras por seccion
- CONCLUSIONES: exactamente 5 puntos numerados
- RECOMENDACIONES: 3-4 puntos numerados
- NO uses los caracteres especiales menor que, mayor que, ni ampersand en el texto
- Solo los encabezados van en negrita con asteriscos dobles
- El resto es texto plano sin markdown adicional"""

    elif modo == "automatico":
        return f"""Organiza este texto en un informe profesional:

{texto_usuario}

Tema: "{tema}" | Norma: {norma}
Estructura:
{est}

Conserva las ideas originales, mejora redaccion. Espanol formal. Sin caracteres especiales < > &."""

    else:
        return f"""Formatea este contenido como informe academico:

{texto_usuario}

Tema: "{tema}" | Norma: {norma}
Estructura:
{est}

Respeta el contenido, mejora coherencia. Espanol formal. Sin < > &."""


# ─────────────────────────────────────────────
#  PARSER
# ─────────────────────────────────────────────

def parsear(texto_ia):
    secs = {}
    mapa = {
        'resumen':        ['RESUMEN', 'ABSTRACT', 'RESUMEN EJECUTIVO'],
        'introduccion':   ['INTRODUCCION', 'INTRODUCCIÓN'],
        'objetivos':      ['OBJETIVOS', 'OBJETIVO'],
        'marco_teorico':  ['MARCO TEORICO', 'MARCO TEÓRICO'],
        'metodologia':    ['METODOLOGIA', 'METODOLOGÍA'],
        'desarrollo':     ['DESARROLLO'],
        'resultados':     ['RESULTADOS Y ANALISIS', 'RESULTADOS'],
        'discusion':      ['DISCUSION', 'DISCUSIÓN'],
        'conclusiones':   ['CONCLUSIONES'],
        'recomendaciones':['RECOMENDACIONES ESTRATEGICAS', 'RECOMENDACIONES'],
        'referencias':    ['REFERENCIAS'],
        'materiales':     ['MATERIALES Y REACTIVOS', 'MATERIALES'],
        'procedimiento':  ['PROCEDIMIENTO'],
        'planteamiento':  ['PLANTEAMIENTO DEL PROBLEMA'],
        'estado_arte':    ['ESTADO DEL ARTE'],
        'hallazgos':      ['HALLAZGOS PRINCIPALES'],
        'antecedentes':   ['ANTECEDENTES'],
        'analisis':       ['ANALISIS COSTO-BENEFICIO'],
        'alternativas':   ['ALTERNATIVAS DE SOLUCION'],
    }
    m = re.search(r'\*\*TITULO\*\*\s*:?\s*(.+?)(?=\n|\*\*)', texto_ia, re.IGNORECASE)
    if m:
        secs['titulo_ia'] = m.group(1).strip()

    for clave, variantes in mapa.items():
        for v in variantes:
            pat = r'\*\*(?:\d+[\.\s]*)?' + re.escape(v) + r'[^*]*\*\*\s*:?\s*(.*?)(?=\n\*\*|\Z)'
            match = re.search(pat, texto_ia, re.IGNORECASE | re.DOTALL)
            if match:
                c = limpiar_sin_escape(match.group(1)).strip()
                if c:
                    secs[clave] = c
                    break

    secs['_raw'] = limpiar_sin_escape(texto_ia)
    return secs


# ─────────────────────────────────────────────
#  CONSTANTES PDF
# ─────────────────────────────────────────────

NAVY   = colors.HexColor('#1a237e')
INDIGO = colors.HexColor('#3949ab')
CLARO  = colors.HexColor('#e8eaf6')
GRIS   = colors.HexColor('#757575')
TEXTO  = colors.HexColor('#212121')
BLANCO = colors.white
GOLD   = colors.HexColor('#7986cb')

W, H = A4
LEFT = RIGHT = 2 * cm
TOP = BOT = 2.5 * cm
CONTENT_W = W - LEFT - RIGHT
CONTENT_H = H - TOP - BOT


def estilos_doc():
    base = getSampleStyleSheet()
    def add(name, **kw):
        base.add(ParagraphStyle(name, parent=base['Normal'], **kw))
    add('PortadaBadge', fontSize=9, fontName='Helvetica',
        textColor=colors.HexColor('#c5cae9'), alignment=TA_CENTER, spaceAfter=6)
    add('PortadaTitulo', fontSize=20, fontName='Helvetica-Bold',
        textColor=BLANCO, alignment=TA_CENTER, spaceAfter=10, leading=26)
    add('PortadaInfo', fontSize=10, fontName='Helvetica-Bold',
        textColor=BLANCO, alignment=TA_CENTER, spaceAfter=4)
    add('PortadaSub', fontSize=9, fontName='Helvetica',
        textColor=colors.HexColor('#c5cae9'), alignment=TA_CENTER, spaceAfter=4)
    add('Seccion', fontSize=13, fontName='Helvetica-Bold',
        textColor=NAVY, spaceBefore=14, spaceAfter=6)
    add('Subseccion', fontSize=10, fontName='Helvetica-Bold',
        textColor=INDIGO, spaceBefore=8, spaceAfter=4)
    add('Cuerpo', fontSize=10, fontName='Helvetica', textColor=TEXTO,
        alignment=TA_JUSTIFY, spaceAfter=5, leading=16, firstLineIndent=14)
    add('Lista', fontSize=10, fontName='Helvetica', textColor=TEXTO,
        spaceAfter=3, leading=15, leftIndent=18)
    add('Ref', fontSize=9, fontName='Helvetica', textColor=TEXTO,
        spaceAfter=4, leading=14, leftIndent=22, firstLineIndent=-22)
    add('Indice', fontSize=10, fontName='Helvetica', textColor=TEXTO,
        spaceAfter=4, leading=16)
    return base


def on_portada(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFillColor(NAVY)
    canvas_obj.rect(0, 0, W, H, fill=1, stroke=0)
    canvas_obj.setFillColor(INDIGO)
    canvas_obj.rect(0, 0, W, 3.5*cm, fill=1, stroke=0)
    canvas_obj.setStrokeColor(GOLD)
    canvas_obj.setLineWidth(2)
    canvas_obj.line(2*cm, H - 2.8*cm, W - 2*cm, H - 2.8*cm)
    canvas_obj.restoreState()


def hacer_on_contenido(titulo_doc, institucion):
    tit = titulo_doc[:55] + '...' if len(titulo_doc) > 55 else titulo_doc
    ins = institucion[:45] + '...' if len(institucion) > 45 else institucion
    def _cb(canvas_obj, doc):
        canvas_obj.saveState()
        canvas_obj.setFont('Helvetica-Bold', 7)
        canvas_obj.setFillColor(NAVY)
        canvas_obj.drawString(LEFT, H - 1.2*cm, ins)
        canvas_obj.setFont('Helvetica', 7)
        canvas_obj.setFillColor(GRIS)
        canvas_obj.drawRightString(W - RIGHT, H - 1.2*cm, tit)
        canvas_obj.setStrokeColor(GOLD)
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(LEFT, H - 1.45*cm, W - RIGHT, H - 1.45*cm)
        canvas_obj.line(LEFT, 1.4*cm, W - RIGHT, 1.4*cm)
        canvas_obj.setFont('Helvetica', 7)
        canvas_obj.setFillColor(GRIS)
        canvas_obj.drawString(LEFT, 0.9*cm, 'Academic Report Pro')
        canvas_obj.drawRightString(W - RIGHT, 0.9*cm, f'Pagina {doc.page}')
        canvas_obj.restoreState()
    return _cb


def texto_a_elementos(texto, st):
    elems = []
    if not texto:
        return elems
    for linea in texto.split('\n'):
        l = linea.strip()
        if not l:
            continue
        if re.match(r'^#{1,3}\s', l) or (l.startswith('**') and l.endswith('**') and len(l) > 4):
            sub = re.sub(r'[#*]', '', l).strip()
            if sub:
                elems.append(Paragraph(escape_xml(sub), st['Subseccion']))
        elif re.match(r'^\d+[\.\)]\s', l):
            txt = re.sub(r'^\d+[\.\)]\s*', '', l)
            txt = re.sub(r'\*+', '', txt).strip()
            elems.append(Paragraph('- ' + escape_xml(txt), st['Lista']))
        elif re.match(r'^[-*]\s', l):
            txt = re.sub(r'^[-*]\s*', '', l)
            txt = re.sub(r'\*+', '', txt).strip()
            elems.append(Paragraph('- ' + escape_xml(txt), st['Lista']))
        else:
            txt = re.sub(r'\*+', '', l).strip()
            if txt:
                elems.append(Paragraph(escape_xml(txt), st['Cuerpo']))
    return elems


def tabla_desde_texto(texto):
    filas = []
    for linea in texto.split('\n'):
        if '|' in linea:
            celdas = [c.strip() for c in linea.split('|') if c.strip()]
            if celdas and not all(set(c) <= {'-', ' '} for c in celdas):
                filas.append(celdas)
    if len(filas) < 2:
        return None
    max_c = max(len(f) for f in filas)
    datos = [f + [''] * (max_c - len(f)) for f in filas]
    cw = CONTENT_W / max_c
    t = Table(datos, colWidths=[cw]*max_c, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,0), NAVY),
        ('TEXTCOLOR',     (0,0),(-1,0), BLANCO),
        ('FONTNAME',      (0,0),(-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0,0),(-1,-1), 8),
        ('FONTNAME',      (0,1),(-1,-1), 'Helvetica'),
        ('ALIGN',         (0,0),(-1,-1), 'CENTER'),
        ('VALIGN',        (0,0),(-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1), [BLANCO, CLARO]),
        ('GRID',          (0,0),(-1,-1), 0.4, INDIGO),
        ('TOPPADDING',    (0,0),(-1,-1), 4),
        ('BOTTOMPADDING', (0,0),(-1,-1), 4),
        ('LEFTPADDING',   (0,0),(-1,-1), 5),
        ('RIGHTPADDING',  (0,0),(-1,-1), 5),
    ]))
    return t


# ─────────────────────────────────────────────
#  GENERADOR DE PDF
# ─────────────────────────────────────────────

def generar_pdf(datos):
    titulo     = datos.get('titulo', 'Informe Academico')
    autores    = datos.get('autores', [{'nombre': 'Autor', 'cargo': ''}])
    asignatura = datos.get('asignatura', '')
    profesor   = datos.get('profesor', '')
    institucion= datos.get('institucion', 'Institucion Educativa')
    ciudad     = datos.get('ciudad', '')
    fecha_str  = datos.get('fecha', datetime.now().strftime('%d/%m/%Y'))
    norma      = datos.get('norma', 'APA 7')
    tipo       = datos.get('tipo_informe', 'academico')
    contenido  = datos.get('contenido_ia', '')

    st   = estilos_doc()
    secs = parsear(contenido)

    buf = io.BytesIO()

    frame_port = Frame(0, 0, W, H,
                       leftPadding=2.8*cm, rightPadding=2.8*cm,
                       topPadding=3.2*cm, bottomPadding=4*cm,
                       id='portada')
    frame_cont = Frame(LEFT, BOT, CONTENT_W, CONTENT_H, id='normal')

    cb = hacer_on_contenido(titulo, institucion)

    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=LEFT, rightMargin=RIGHT,
        topMargin=TOP, bottomMargin=BOT,
        title=titulo,
        author=', '.join(a.get('nombre', '') for a in autores)
    )
    doc.addPageTemplates([
        PageTemplate(id='portada',   frames=[frame_port], onPage=on_portada),
        PageTemplate(id='contenido', frames=[frame_cont], onPage=cb),
    ])

    story = []

    # ── PORTADA ──
    tipo_labels = {
        'academico':   'INFORME ACADEMICO GENERAL',
        'laboratorio': 'INFORME DE LABORATORIO',
        'ejecutivo':   'INFORME EJECUTIVO',
        'tesis':       'TRABAJO DE GRADO / TESIS',
    }
    story.append(Paragraph(tipo_labels.get(tipo, 'INFORME'), st['PortadaBadge']))
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(escape_xml(titulo.upper()), st['PortadaTitulo']))
    story.append(Spacer(1, 1.5*cm))

    sep = Table([['']], colWidths=[CONTENT_W - 2*cm])
    sep.setStyle(TableStyle([
        ('LINEABOVE',     (0,0),(-1,0), 1, GOLD),
        ('TOPPADDING',    (0,0),(-1,-1), 0),
        ('BOTTOMPADDING', (0,0),(-1,-1), 0),
    ]))
    story.append(sep)
    story.append(Spacer(1, 1.2*cm))

    for a in autores:
        if a.get('nombre'):
            story.append(Paragraph(escape_xml(a['nombre']), st['PortadaInfo']))
        if a.get('cargo'):
            story.append(Paragraph(escape_xml(a['cargo']), st['PortadaSub']))
    story.append(Spacer(1, .8*cm))
    if asignatura:
        story.append(Paragraph('Asignatura: ' + escape_xml(asignatura), st['PortadaInfo']))
    if profesor:
        story.append(Paragraph('Docente: ' + escape_xml(profesor), st['PortadaInfo']))
    story.append(Spacer(1, .4*cm))
    story.append(Paragraph(escape_xml(institucion), st['PortadaInfo']))
    if ciudad:
        story.append(Paragraph(escape_xml(ciudad), st['PortadaSub']))
    story.append(Paragraph(escape_xml(fecha_str), st['PortadaSub']))
    story.append(Paragraph('Norma: ' + escape_xml(norma), st['PortadaSub']))

    story.append(NextPageTemplate('contenido'))
    story.append(PageBreak())

    # ── ÍNDICE ──
    def sec_titulo(txt):
        story.append(Paragraph(escape_xml(txt), st['Seccion']))
        story.append(HRFlowable(width='100%', thickness=1, color=GOLD, spaceAfter=5))

    sec_titulo('TABLA DE CONTENIDO')
    indice_items = []
    if secs.get('resumen'):          indice_items.append('RESUMEN')
    indice_items.append('INTRODUCCION')
    if secs.get('planteamiento'):    indice_items.append('PLANTEAMIENTO DEL PROBLEMA')
    if secs.get('objetivos'):        indice_items.append('OBJETIVOS')
    if secs.get('marco_teorico'):    indice_items.append('MARCO TEORICO')
    if secs.get('estado_arte'):      indice_items.append('ESTADO DEL ARTE')
    if secs.get('materiales'):       indice_items.append('MATERIALES Y REACTIVOS')
    if secs.get('procedimiento'):    indice_items.append('PROCEDIMIENTO')
    if secs.get('metodologia'):      indice_items.append('METODOLOGIA')
    if secs.get('antecedentes'):     indice_items.append('ANTECEDENTES')
    if secs.get('hallazgos'):        indice_items.append('HALLAZGOS PRINCIPALES')
    if secs.get('analisis'):         indice_items.append('ANALISIS COSTO-BENEFICIO')
    if secs.get('alternativas'):     indice_items.append('ALTERNATIVAS DE SOLUCION')
    if secs.get('desarrollo') or secs.get('resultados'):
        indice_items.append('DESARROLLO / RESULTADOS')
    if secs.get('discusion'):        indice_items.append('DISCUSION')
    if secs.get('conclusiones'):     indice_items.append('CONCLUSIONES')
    if secs.get('recomendaciones'):  indice_items.append('RECOMENDACIONES')
    indice_items.append('REFERENCIAS')

    for item in indice_items:
        puntos = '.' * max(1, 58 - len(item))
        story.append(Paragraph(
            f"{escape_xml(item)} <font color='#9e9e9e'>{puntos}</font>",
            st['Indice']
        ))
    story.append(PageBreak())

    # ── HELPER sección ──
    def agregar(titulo_sec, clave):
        c = secs.get(clave, '')
        if not c:
            return
        sec_titulo(titulo_sec)
        story.extend(texto_a_elementos(c, st))
        story.append(Spacer(1, .3*cm))

    def agregar_con_tabla(titulo_sec, clave):
        c = secs.get(clave, '')
        if not c:
            return
        sec_titulo(titulo_sec)
        story.extend(texto_a_elementos(c, st))
        t = tabla_desde_texto(c)
        if t:
            story.append(Spacer(1, .3*cm))
            story.append(t)
        story.append(Spacer(1, .3*cm))

    # ── CUERPO ──
    if secs.get('resumen'):
        agregar('RESUMEN', 'resumen')
        story.append(PageBreak())

    agregar('INTRODUCCION', 'introduccion')
    agregar('PLANTEAMIENTO DEL PROBLEMA', 'planteamiento')
    agregar('OBJETIVOS', 'objetivos')

    if secs.get('marco_teorico'):
        story.append(PageBreak())
        agregar('MARCO TEORICO', 'marco_teorico')

    agregar('ESTADO DEL ARTE', 'estado_arte')
    agregar('MATERIALES Y REACTIVOS', 'materiales')
    agregar('PROCEDIMIENTO', 'procedimiento')
    agregar('METODOLOGIA', 'metodologia')
    agregar('ANTECEDENTES', 'antecedentes')
    agregar('HALLAZGOS PRINCIPALES', 'hallazgos')
    agregar('ANALISIS COSTO-BENEFICIO', 'analisis')
    agregar('ALTERNATIVAS DE SOLUCION', 'alternativas')

    dev_key = 'resultados' if tipo == 'laboratorio' else 'desarrollo'
    dev_tit = 'RESULTADOS' if tipo == 'laboratorio' else 'DESARROLLO'
    if secs.get(dev_key):
        story.append(PageBreak())
        agregar_con_tabla(dev_tit, dev_key)

    agregar('DISCUSION', 'discusion')

    if secs.get('conclusiones'):
        story.append(PageBreak())
        agregar('CONCLUSIONES', 'conclusiones')

    agregar('RECOMENDACIONES', 'recomendaciones')

    if secs.get('referencias'):
        story.append(PageBreak())
        sec_titulo('REFERENCIAS')
        for linea in secs['referencias'].split('\n'):
            l = linea.strip()
            if not l:
                continue
            l = re.sub(r'^[-*\d\.]+\s*', '', l)
            l = re.sub(r'\*+', '', l).strip()
            if l:
                story.append(Paragraph(escape_xml(l), st['Ref']))
                story.append(Spacer(1, 2))

    # Fallback
    if len(story) < 20 and secs.get('_raw'):
        sec_titulo('CONTENIDO DEL INFORME')
        story.extend(texto_a_elementos(secs['_raw'], st))

    doc.build(story)
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────
#  RUTAS FLASK
# ─────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/generar', methods=['POST'])
def generar():
    try:
        datos = request.get_json(force=True)
        if not datos:
            return jsonify({'error': 'No se recibieron datos'}), 400

        tema = limpiar_sin_escape(datos.get('tema', ''))
        if not tema:
            return jsonify({'error': 'El tema es requerido'}), 400

        modo          = datos.get('modo', 'rapido')
        tipo_informe  = datos.get('tipo_informe', 'academico')
        norma         = datos.get('norma', 'APA 7')
        texto_usuario = limpiar_sin_escape(datos.get('texto_usuario', ''))
        refs_modo     = datos.get('referencias_modo', 'automatico')
        refs_manuales = limpiar_sin_escape(datos.get('referencias_manuales', ''))

        prompt    = construir_prompt(tipo_informe, tema, modo, norma, texto_usuario)
        contenido = llamar_ia(prompt)

        if contenido.startswith('ERROR_IA'):
            return jsonify({'error': contenido}), 500

        if refs_modo == 'manual' and refs_manuales:
            contenido = re.sub(
                r'\*\*(?:\d+[\.\s]*)?REFERENCIAS?\*\*.*',
                f'**REFERENCIAS**\n{refs_manuales}',
                contenido, flags=re.DOTALL | re.IGNORECASE
            )
        elif refs_modo == 'mixto' and refs_manuales:
            contenido += f'\n\n**REFERENCIAS**\n{refs_manuales}'

        autores_raw = datos.get('autores') or [{'nombre': datos.get('autor_principal', 'Autor'), 'cargo': ''}]

        titulo_informe = datos.get('titulo') or tema
        m = re.search(r'\*\*TITULO\*\*\s*:?\s*(.+?)(?=\n|\*\*)', contenido, re.IGNORECASE)
        if m and not datos.get('titulo'):
            titulo_informe = limpiar_sin_escape(m.group(1)).strip()

        pdf_buf = generar_pdf({
            'titulo':       titulo_informe,
            'autores':      autores_raw,
            'asignatura':   limpiar_sin_escape(datos.get('asignatura', '')),
            'profesor':     limpiar_sin_escape(datos.get('profesor', '')),
            'institucion':  limpiar_sin_escape(datos.get('institucion', 'Institucion Educativa')),
            'ciudad':       limpiar_sin_escape(datos.get('ciudad', '')),
            'fecha':        datos.get('fecha', datetime.now().strftime('%d/%m/%Y')),
            'norma':        norma,
            'tipo_informe': tipo_informe,
            'contenido_ia': contenido,
        })

        nombre = re.sub(r'[^\w\s-]', '', tema)[:40].strip().replace(' ', '_')
        nombre = f"informe_{nombre}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        return send_file(pdf_buf, mimetype='application/pdf',
                         as_attachment=True, download_name=nombre)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error interno: {str(e)}'}), 500


@app.route('/preview', methods=['POST'])
def preview():
    try:
        datos         = request.get_json(force=True)
        tema          = limpiar_sin_escape(datos.get('tema', ''))
        modo          = datos.get('modo', 'rapido')
        tipo_informe  = datos.get('tipo_informe', 'academico')
        norma         = datos.get('norma', 'APA 7')
        texto_usuario = limpiar_sin_escape(datos.get('texto_usuario', ''))
        prompt        = construir_prompt(tipo_informe, tema, modo, norma, texto_usuario)
        contenido     = llamar_ia(prompt)
        return jsonify({'contenido': contenido})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'version': '2.0.0'})


if __name__ == '__main__':
    port  = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
