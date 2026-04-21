import os
import re
import io
import json
import requests
from datetime import datetime
from flask import Flask, request, jsonify, send_file, render_template

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate

app = Flask(__name__)

OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def limpiar_texto(texto):
    """Elimina caracteres no imprimibles y corrige errores comunes."""
    if not texto:
        return ""
    texto = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', texto)
    texto = texto.replace("INFORMÉ", "INFORME")
    texto = texto.replace("Conclusions", "CONCLUSIONES")
    texto = texto.replace("conclusions", "conclusiones")
    return texto.strip()


def llamar_openrouter(prompt, max_tokens=6000):
    """Llama a la API de OpenRouter y retorna el texto generado."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://academic-report-pro.onrender.com",
        "X-Title": "Academic Report Pro"
    }
    data = {
        "model": "meta-llama/llama-4-scout",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=120)
        resp.raise_for_status()
        resultado = resp.json()
        return limpiar_texto(resultado["choices"][0]["message"]["content"])
    except Exception as e:
        return f"Error al conectar con la IA: {str(e)}"


# ---------------------------------------------------------------------------
# Construcción de prompts
# ---------------------------------------------------------------------------

def construir_prompt(tipo_informe, tema, modo, norma, texto_usuario=""):
    norma_instruccion = f"Usa el formato de citas y referencias según la norma {norma}."

    if tipo_informe == "laboratorio":
        estructura = """
**TÍTULO**
**1. INTRODUCCIÓN** (objetivo del experimento y fundamento teórico)
**2. MATERIALES Y REACTIVOS** (lista detallada)
**3. PROCEDIMIENTO** (paso a paso numerado, incluye controles positivo y negativo)
**4. RESULTADOS** (incluye tabla con columnas: Prueba | Muestra | Resultado | Observación)
**5. DISCUSIÓN** (análisis crítico de resultados)
**6. CONCLUSIONES** (mínimo 5 puntos numerados)
**7. RECOMENDACIONES** (3-4 recomendaciones prácticas)
**8. REFERENCIAS** (5-6 referencias en formato {norma})
""".format(norma=norma)
    elif tipo_informe == "tesis":
        estructura = """
**RESUMEN / ABSTRACT**
**1. INTRODUCCIÓN** (contexto, problema, justificación)
**2. PLANTEAMIENTO DEL PROBLEMA**
**3. OBJETIVOS** (1 general + 4 específicos numerados)
**4. MARCO TEÓRICO** (fundamentos conceptuales ampliados)
**5. ESTADO DEL ARTE**
**6. METODOLOGÍA** (diseño, población, muestra, instrumentos)
**7. RESULTADOS Y ANÁLISIS** (incluye tabla comparativa)
**8. DISCUSIÓN**
**9. CONCLUSIONES** (mínimo 5 puntos)
**10. RECOMENDACIONES** (3-4 puntos)
**11. REFERENCIAS** (mínimo 10 en formato {norma})
""".format(norma=norma)
    elif tipo_informe == "ejecutivo":
        estructura = """
**RESUMEN EJECUTIVO**
**1. ANTECEDENTES**
**2. SITUACIÓN ACTUAL** (incluye tabla de indicadores clave)
**3. HALLAZGOS PRINCIPALES** (3-5 puntos clave)
**4. ANÁLISIS COSTO-BENEFICIO**
**5. ALTERNATIVAS DE SOLUCIÓN**
**6. CONCLUSIONES** (3-5 puntos concretos)
**7. RECOMENDACIONES ESTRATÉGICAS** (3-4 acciones)
**8. REFERENCIAS** (3-4 en formato {norma})
""".format(norma=norma)
    else:  # académico general
        estructura = """
**INTRODUCCIÓN**
**1. OBJETIVOS** (1 objetivo general + 4 específicos numerados)
**2. MARCO TEÓRICO** (fundamentos teóricos ampliados con subtítulos)
**3. METODOLOGÍA** (enfoque, tipo de investigación, técnicas)
**4. DESARROLLO** (análisis completo con tabla de datos o comparativa)
**5. CONCLUSIONES** (mínimo 5 puntos numerados)
**6. RECOMENDACIONES** (3-4 puntos)
**7. REFERENCIAS** (5-6 en formato {norma})
""".format(norma=norma)

    if modo == "rapido":
        return f"""Eres un experto académico. Genera un informe académico profesional y completo sobre el siguiente tema: "{tema}".

{norma_instruccion}

Estructura el informe con las siguientes secciones (usa exactamente estos encabezados en negrita):
{estructura}

INSTRUCCIONES IMPORTANTES:
- Escribe en español formal y académico
- Cada sección debe tener contenido sustancial (mínimo 150 palabras por sección principal)
- En las CONCLUSIONES escribe exactamente 5 puntos numerados
- En RECOMENDACIONES escribe 3-4 puntos numerados  
- En REFERENCIAS incluye las fuentes solicitadas con el formato correcto de {norma}
- NO uses markdown excesivo, solo los encabezados en **negrita**
- El contenido debe ser preciso, bien fundamentado y coherente
- Incluye datos específicos, conceptos técnicos y ejemplos cuando sea pertinente"""

    elif modo == "automatico":
        return f"""Eres un experto académico. El usuario ha proporcionado el siguiente texto para organizar en un informe académico profesional:

--- TEXTO DEL USUARIO ---
{texto_usuario}
--- FIN DEL TEXTO ---

Tema del informe: "{tema}"
{norma_instruccion}

Reorganiza y amplía el contenido del usuario con la siguiente estructura:
{estructura}

INSTRUCCIONES:
- Mantén las ideas originales del usuario pero mejora la redacción y organización
- Amplía con información relevante donde sea necesario
- Escribe en español formal y académico
- Cada sección debe ser sustancial (mínimo 100 palabras)
- Usa exactamente los encabezados indicados en negrita"""

    else:  # manual - solo organiza y formatea
        return f"""Eres un experto académico. Formatea el siguiente contenido como un informe académico profesional:

{texto_usuario}

Tema: "{tema}"
{norma_instruccion}

Organiza el contenido con la estructura:
{estructura}

INSTRUCCIONES:
- Respeta el contenido original del usuario
- Mejora la redacción y coherencia
- Escribe en español formal
- Usa exactamente los encabezados indicados en negrita"""


# ---------------------------------------------------------------------------
# Generación de contenido con IA
# ---------------------------------------------------------------------------

def generar_contenido_ia(tipo_informe, tema, modo, norma, texto_usuario="", referencias_modo="automatico", referencias_manuales=""):
    prompt = construir_prompt(tipo_informe, tema, modo, norma, texto_usuario)
    contenido = llamar_openrouter(prompt)

    # Si referencias son manuales, reemplazar la sección de referencias
    if referencias_modo == "manual" and referencias_manuales.strip():
        # Buscar y reemplazar la sección de referencias
        patron = r'(\*\*[78910]?\.*\s*REFERENCIAS?\*\*.*?)(?=\*\*|\Z)'
        refs_formateadas = f"**REFERENCIAS**\n{referencias_manuales}"
        contenido_nuevo = re.sub(patron, refs_formateadas, contenido, flags=re.DOTALL | re.IGNORECASE)
        if contenido_nuevo != contenido:
            contenido = contenido_nuevo

    elif referencias_modo == "mixto" and referencias_manuales.strip():
        # Agregar referencias manuales a las generadas por IA
        if referencias_manuales.strip():
            contenido += f"\n\nReferencias adicionales proporcionadas:\n{referencias_manuales}"

    return contenido


# ---------------------------------------------------------------------------
# Parser del contenido generado
# ---------------------------------------------------------------------------

def parsear_secciones(texto_ia):
    """Extrae secciones del texto generado por la IA."""
    secciones = {}

    # Extraer título si existe
    titulo_match = re.search(r'\*\*TÍTULO\*\*\s*:?\s*(.+?)(?=\*\*|\n\n)', texto_ia, re.IGNORECASE | re.DOTALL)
    if titulo_match:
        secciones['titulo_ia'] = limpiar_texto(titulo_match.group(1)).strip()

    # Patrones para secciones comunes
    patrones = {
        'resumen': r'\*\*(?:RESUMEN|ABSTRACT|RESUMEN EJECUTIVO)\*\*\s*:?\s*(.*?)(?=\*\*\d|\*\*[A-ZÁÉÍÓÚ]|\Z)',
        'introduccion': r'\*\*(?:\d+\.\s*)?INTRODUCCIÓN?\*\*\s*:?\s*(.*?)(?=\*\*\d|\*\*[A-ZÁÉÍÓÚ]|\Z)',
        'objetivos': r'\*\*(?:\d+\.\s*)?OBJETIVOS?\*\*\s*:?\s*(.*?)(?=\*\*\d|\*\*[A-ZÁÉÍÓÚ]|\Z)',
        'marco_teorico': r'\*\*(?:\d+\.\s*)?MARCO\s+TEÓRICO?\*\*\s*:?\s*(.*?)(?=\*\*\d|\*\*[A-ZÁÉÍÓÚ]|\Z)',
        'metodologia': r'\*\*(?:\d+\.\s*)?METODOLOGÍA?\*\*\s*:?\s*(.*?)(?=\*\*\d|\*\*[A-ZÁÉÍÓÚ]|\Z)',
        'desarrollo': r'\*\*(?:\d+\.\s*)?DESARROLLO?\*\*\s*:?\s*(.*?)(?=\*\*\d|\*\*[A-ZÁÉÍÓÚ]|\Z)',
        'resultados': r'\*\*(?:\d+\.\s*)?RESULTADOS?\*\*\s*:?\s*(.*?)(?=\*\*\d|\*\*[A-ZÁÉÍÓÚ]|\Z)',
        'discusion': r'\*\*(?:\d+\.\s*)?DISCUSIÓN?\*\*\s*:?\s*(.*?)(?=\*\*\d|\*\*[A-ZÁÉÍÓÚ]|\Z)',
        'conclusiones': r'\*\*(?:\d+\.\s*)?CONCLUSIONES?\*\*\s*:?\s*(.*?)(?=\*\*\d|\*\*[A-ZÁÉÍÓÚ]|\Z)',
        'recomendaciones': r'\*\*(?:\d+\.\s*)?RECOMENDACIONES?\*\*\s*:?\s*(.*?)(?=\*\*\d|\*\*[A-ZÁÉÍÓÚ]|\Z)',
        'referencias': r'\*\*(?:\d+\.\s*)?REFERENCIAS?\*\*\s*:?\s*(.*?)(?=\*\*\d|\*\*[A-ZÁÉÍÓÚ]|\Z)',
        'materiales': r'\*\*(?:\d+\.\s*)?MATERIALES?\s*(?:Y\s*REACTIVOS?)?\*\*\s*:?\s*(.*?)(?=\*\*\d|\*\*[A-ZÁÉÍÓÚ]|\Z)',
        'procedimiento': r'\*\*(?:\d+\.\s*)?PROCEDIMIENTO?\*\*\s*:?\s*(.*?)(?=\*\*\d|\*\*[A-ZÁÉÍÓÚ]|\Z)',
    }

    for nombre, patron in patrones.items():
        match = re.search(patron, texto_ia, re.IGNORECASE | re.DOTALL)
        if match:
            contenido = limpiar_texto(match.group(1)).strip()
            if contenido:
                secciones[nombre] = contenido

    # Texto completo como fallback
    secciones['texto_completo'] = limpiar_texto(texto_ia)
    return secciones


def extraer_tabla_resultados(texto):
    """Extrae datos tabulares del texto para crear tabla en PDF."""
    filas = []
    lineas = texto.split('\n')
    for linea in lineas:
        if '|' in linea:
            celdas = [c.strip() for c in linea.split('|') if c.strip()]
            if celdas and not all(c.replace('-', '').replace(' ', '') == '' for c in celdas):
                filas.append(celdas)
    return filas if len(filas) >= 2 else None


# ---------------------------------------------------------------------------
# Generación del PDF
# ---------------------------------------------------------------------------

COLORES = {
    'primario': colors.HexColor('#1a237e'),
    'secundario': colors.HexColor('#283593'),
    'acento': colors.HexColor('#3949ab'),
    'claro': colors.HexColor('#e8eaf6'),
    'texto': colors.HexColor('#212121'),
    'gris': colors.HexColor('#757575'),
    'blanco': colors.white,
    'linea': colors.HexColor('#3949ab'),
}


class PaginadorConNumeros:
    """Agrega encabezado y pie de página a cada hoja."""
    def __init__(self, titulo_doc, institucion):
        self.titulo = titulo_doc[:60] + "..." if len(titulo_doc) > 60 else titulo_doc
        self.institucion = institucion

    def __call__(self, canvas_obj, doc):
        canvas_obj.saveState()
        w, h = A4

        # Encabezado
        canvas_obj.setFillColor(COLORES['primario'])
        canvas_obj.setFont("Helvetica-Bold", 8)
        canvas_obj.drawString(2 * cm, h - 1.2 * cm, self.institucion[:50])
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.setFillColor(COLORES['gris'])
        canvas_obj.drawRightString(w - 2 * cm, h - 1.2 * cm, self.titulo)

        # Línea encabezado
        canvas_obj.setStrokeColor(COLORES['linea'])
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(2 * cm, h - 1.5 * cm, w - 2 * cm, h - 1.5 * cm)

        # Pie de página
        canvas_obj.line(2 * cm, 1.5 * cm, w - 2 * cm, 1.5 * cm)
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.setFillColor(COLORES['gris'])
        canvas_obj.drawString(2 * cm, 1 * cm, "Academic Report Pro")
        canvas_obj.drawRightString(w - 2 * cm, 1 * cm, f"Página {doc.page}")

        canvas_obj.restoreState()


def crear_estilos():
    """Crea y retorna los estilos del documento."""
    estilos = getSampleStyleSheet()

    estilos.add(ParagraphStyle(
        'TituloPortada',
        parent=estilos['Normal'],
        fontSize=22,
        fontName='Helvetica-Bold',
        textColor=COLORES['blanco'],
        alignment=TA_CENTER,
        spaceAfter=12,
        leading=28,
    ))
    estilos.add(ParagraphStyle(
        'SubtituloPortada',
        parent=estilos['Normal'],
        fontSize=12,
        fontName='Helvetica',
        textColor=colors.HexColor('#c5cae9'),
        alignment=TA_CENTER,
        spaceAfter=8,
    ))
    estilos.add(ParagraphStyle(
        'InfoPortada',
        parent=estilos['Normal'],
        fontSize=10,
        fontName='Helvetica',
        textColor=COLORES['blanco'],
        alignment=TA_CENTER,
        spaceAfter=5,
    ))
    estilos.add(ParagraphStyle(
        'SeccionTitulo',
        parent=estilos['Normal'],
        fontSize=14,
        fontName='Helvetica-Bold',
        textColor=COLORES['primario'],
        spaceBefore=18,
        spaceAfter=8,
        borderPad=4,
    ))
    estilos.add(ParagraphStyle(
        'SubseccionTitulo',
        parent=estilos['Normal'],
        fontSize=11,
        fontName='Helvetica-Bold',
        textColor=COLORES['secundario'],
        spaceBefore=10,
        spaceAfter=5,
    ))
    estilos.add(ParagraphStyle(
        'CuerpoTexto',
        parent=estilos['Normal'],
        fontSize=10,
        fontName='Helvetica',
        textColor=COLORES['texto'],
        alignment=TA_JUSTIFY,
        spaceAfter=6,
        leading=16,
        firstLineIndent=18,
    ))
    estilos.add(ParagraphStyle(
        'ListaItem',
        parent=estilos['Normal'],
        fontSize=10,
        fontName='Helvetica',
        textColor=COLORES['texto'],
        spaceAfter=4,
        leading=15,
        leftIndent=20,
        bulletIndent=10,
    ))
    estilos.add(ParagraphStyle(
        'Referencia',
        parent=estilos['Normal'],
        fontSize=9,
        fontName='Helvetica',
        textColor=COLORES['texto'],
        spaceAfter=5,
        leading=14,
        leftIndent=25,
        firstLineIndent=-25,
    ))
    estilos.add(ParagraphStyle(
        'IndiceItem',
        parent=estilos['Normal'],
        fontSize=10,
        fontName='Helvetica',
        textColor=COLORES['texto'],
        spaceAfter=4,
        leading=16,
    ))
    return estilos


def texto_a_parrafos(texto, estilo_cuerpo, estilo_lista, estilo_subseccion):
    """Convierte texto crudo a elementos Paragraph para ReportLab."""
    elementos = []
    if not texto:
        return elementos

    lineas = texto.split('\n')
    i = 0
    while i < len(lineas):
        linea = lineas[i].strip()
        if not linea:
            i += 1
            continue

        # Subtítulo (### o **)
        if linea.startswith('###') or (linea.startswith('**') and linea.endswith('**') and len(linea) > 4):
            sub = re.sub(r'\*+', '', linea).replace('#', '').strip()
            if sub:
                elementos.append(Paragraph(sub, estilo_subseccion))
        # Lista numerada
        elif re.match(r'^\d+[\.\)]\s', linea):
            limpia = re.sub(r'\*+', '', linea).strip()
            elementos.append(Paragraph(f"• {limpia}", estilo_lista))
        # Lista con guión o asterisco
        elif re.match(r'^[-•*]\s', linea):
            limpia = re.sub(r'^\s*[-•*]\s*', '', linea)
            limpia = re.sub(r'\*+', '', limpia).strip()
            elementos.append(Paragraph(f"• {limpia}", estilo_lista))
        # Párrafo normal
        else:
            limpia = re.sub(r'\*+', '', linea).strip()
            if limpia:
                elementos.append(Paragraph(limpia, estilo_cuerpo))
        i += 1

    return elementos


def crear_tabla_pdf(filas_datos, estilo_tabla_header=None):
    """Crea una tabla ReportLab desde lista de filas."""
    if not filas_datos or len(filas_datos) < 2:
        return None

    # Normalizar columnas
    max_cols = max(len(f) for f in filas_datos)
    datos_norm = []
    for fila in filas_datos:
        while len(fila) < max_cols:
            fila.append("")
        datos_norm.append(fila[:max_cols])

    ancho_col = (A4[0] - 4 * cm) / max_cols

    tabla = Table(datos_norm, colWidths=[ancho_col] * max_cols, repeatRows=1)
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLORES['primario']),
        ('TEXTCOLOR', (0, 0), (-1, 0), COLORES['blanco']),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COLORES['blanco'], COLORES['claro']]),
        ('GRID', (0, 0), (-1, -1), 0.5, COLORES['acento']),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    return tabla


def generar_pdf(datos):
    """Genera el PDF completo y retorna bytes."""
    titulo = limpiar_texto(datos.get('titulo', 'Informe Académico'))
    autores = datos.get('autores', [{'nombre': 'Autor', 'cargo': ''}])
    asignatura = limpiar_texto(datos.get('asignatura', ''))
    profesor = limpiar_texto(datos.get('profesor', ''))
    institucion = limpiar_texto(datos.get('institucion', 'Institución Educativa'))
    ciudad = limpiar_texto(datos.get('ciudad', ''))
    fecha_str = datos.get('fecha', datetime.now().strftime('%d/%m/%Y'))
    norma = datos.get('norma', 'APA 7')
    tipo_informe = datos.get('tipo_informe', 'academico')
    contenido_ia = datos.get('contenido_ia', '')

    secciones = parsear_secciones(contenido_ia)
    estilos = crear_estilos()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
        title=titulo,
        author=', '.join(a['nombre'] for a in autores),
    )

    paginador = PaginadorConNumeros(titulo, institucion)
    elementos = []

    # -------------------------
    # PORTADA
    # -------------------------
    w, h = A4

    def dibujar_portada(canvas_obj, doc_obj):
        canvas_obj.saveState()
        # Fondo degradado simulado con rectángulos
        canvas_obj.setFillColor(COLORES['primario'])
        canvas_obj.rect(0, 0, w, h, fill=1, stroke=0)
        # Banda decorativa inferior
        canvas_obj.setFillColor(COLORES['acento'])
        canvas_obj.rect(0, 0, w, 4 * cm, fill=1, stroke=0)
        # Línea decorativa
        canvas_obj.setStrokeColor(colors.HexColor('#7986cb'))
        canvas_obj.setLineWidth(3)
        canvas_obj.line(2 * cm, h - 3 * cm, w - 2 * cm, h - 3 * cm)
        canvas_obj.restoreState()

    # Frame para portada
    frame_portada = Frame(0, 0, w, h, leftPadding=2.5*cm, rightPadding=2.5*cm,
                          topPadding=3.5*cm, bottomPadding=4.5*cm)

    elem_portada = []
    # Logo/icono de Academic Report Pro
    elem_portada.append(Spacer(1, 0.5*cm))

    # Tipo de informe badge
    tipo_labels = {
        'academico': 'INFORME ACADÉMICO GENERAL',
        'laboratorio': 'INFORME DE LABORATORIO',
        'ejecutivo': 'INFORME EJECUTIVO',
        'tesis': 'TRABAJO DE GRADO / TESIS',
    }
    tipo_label = tipo_labels.get(tipo_informe, 'INFORME ACADÉMICO')
    elem_portada.append(Paragraph(tipo_label, estilos['SubtituloPortada']))
    elem_portada.append(Spacer(1, 1.2*cm))

    # Título principal
    elem_portada.append(Paragraph(titulo.upper(), estilos['TituloPortada']))
    elem_portada.append(Spacer(1, 2*cm))

    # Línea divisoria
    hr_data = [['']]
    hr_tabla = Table(hr_data, colWidths=[w - 5*cm])
    hr_tabla.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor('#7986cb')),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elem_portada.append(hr_tabla)
    elem_portada.append(Spacer(1, 1.5*cm))

    # Autores
    for autor in autores:
        nombre_autor = limpiar_texto(autor.get('nombre', ''))
        cargo_autor = limpiar_texto(autor.get('cargo', ''))
        if nombre_autor:
            elem_portada.append(Paragraph(f"<b>{nombre_autor}</b>", estilos['InfoPortada']))
        if cargo_autor:
            elem_portada.append(Paragraph(cargo_autor, estilos['SubtituloPortada']))
    elem_portada.append(Spacer(1, 1*cm))

    if asignatura:
        elem_portada.append(Paragraph(f"Asignatura: {asignatura}", estilos['InfoPortada']))
    if profesor:
        elem_portada.append(Paragraph(f"Docente: {profesor}", estilos['InfoPortada']))
    elem_portada.append(Spacer(1, 0.5*cm))
    elem_portada.append(Paragraph(institucion, estilos['InfoPortada']))
    if ciudad:
        elem_portada.append(Paragraph(ciudad, estilos['SubtituloPortada']))
    elem_portada.append(Paragraph(fecha_str, estilos['SubtituloPortada']))
    elem_portada.append(Spacer(1, 0.5*cm))
    elem_portada.append(Paragraph(f"Norma: {norma}", estilos['SubtituloPortada']))

    doc.build(
        elementos,
        onFirstPage=lambda c, d: None,
        onLaterPages=paginador,
    )

    # Reconstruir con portada real
    buffer = io.BytesIO()

    class DocConPortada(BaseDocTemplate):
        def __init__(self, *args, **kwargs):
            BaseDocTemplate.__init__(self, *args, **kwargs)
            frame_normal = Frame(
                doc.leftMargin, doc.bottomMargin,
                w - doc.leftMargin - doc.rightMargin,
                h - doc.topMargin - doc.bottomMargin,
                id='normal'
            )
            frame_port = Frame(0, 0, w, h,
                               leftPadding=2.5*cm, rightPadding=2.5*cm,
                               topPadding=3.5*cm, bottomPadding=4.5*cm,
                               id='portada')
            self.addPageTemplates([
                PageTemplate(id='portada', frames=[frame_port], onPage=dibujar_portada),
                PageTemplate(id='contenido', frames=[frame_normal], onPage=paginador),
            ])

    doc2 = DocConPortada(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2.5*cm,
        bottomMargin=2.5*cm,
        title=titulo,
    )

    from reportlab.platypus import NextPageTemplate, CondPageBreak

    todos = []
    # Portada
    todos.extend(elem_portada)
    todos.append(NextPageTemplate('contenido'))
    todos.append(PageBreak())

    # -------------------------
    # ÍNDICE
    # -------------------------
    todos.append(Paragraph("TABLA DE CONTENIDO", estilos['SeccionTitulo']))
    todos.append(HRFlowable(width="100%", thickness=1.5, color=COLORES['linea'], spaceAfter=12))

    secciones_indice = []
    num = 1
    if secciones.get('resumen'): secciones_indice.append(("RESUMEN", ""))
    secciones_indice.append(("INTRODUCCIÓN", str(num))); num += 1
    if secciones.get('objetivos'): secciones_indice.append(("OBJETIVOS", str(num))); num += 1
    if secciones.get('marco_teorico'): secciones_indice.append(("MARCO TEÓRICO", str(num))); num += 1
    if secciones.get('materiales'): secciones_indice.append(("MATERIALES Y REACTIVOS", str(num))); num += 1
    if secciones.get('procedimiento'): secciones_indice.append(("PROCEDIMIENTO", str(num))); num += 1
    if secciones.get('metodologia'): secciones_indice.append(("METODOLOGÍA", str(num))); num += 1
    if secciones.get('desarrollo') or secciones.get('resultados'): secciones_indice.append(("DESARROLLO / RESULTADOS", str(num))); num += 1
    if secciones.get('discusion'): secciones_indice.append(("DISCUSIÓN", str(num))); num += 1
    if secciones.get('conclusiones'): secciones_indice.append(("CONCLUSIONES", str(num))); num += 1
    if secciones.get('recomendaciones'): secciones_indice.append(("RECOMENDACIONES", str(num))); num += 1
    secciones_indice.append(("REFERENCIAS", str(num)))

    for nombre_sec, _ in secciones_indice:
        puntos = "." * max(1, 60 - len(nombre_sec))
        todos.append(Paragraph(f"{nombre_sec} <font color='#9e9e9e'>{puntos}</font>",
                                estilos['IndiceItem']))

    todos.append(PageBreak())

    # -------------------------
    # CUERPO DEL DOCUMENTO
    # -------------------------
    def agregar_seccion(titulo_sec, contenido_sec):
        if not contenido_sec:
            return
        todos.append(Paragraph(titulo_sec.upper(), estilos['SeccionTitulo']))
        todos.append(HRFlowable(width="100%", thickness=1, color=COLORES['linea'], spaceAfter=6))
        parrafos = texto_a_parrafos(
            contenido_sec, estilos['CuerpoTexto'],
            estilos['ListaItem'], estilos['SubseccionTitulo']
        )
        todos.extend(parrafos)
        todos.append(Spacer(1, 0.3*cm))

    if secciones.get('resumen'):
        agregar_seccion("RESUMEN", secciones['resumen'])
        todos.append(PageBreak())

    agregar_seccion("INTRODUCCIÓN", secciones.get('introduccion', ''))

    if secciones.get('objetivos'):
        agregar_seccion("OBJETIVOS", secciones['objetivos'])

    if secciones.get('marco_teorico'):
        todos.append(PageBreak())
        agregar_seccion("MARCO TEÓRICO", secciones['marco_teorico'])

    if secciones.get('materiales'):
        agregar_seccion("MATERIALES Y REACTIVOS", secciones['materiales'])

    if secciones.get('procedimiento'):
        agregar_seccion("PROCEDIMIENTO", secciones['procedimiento'])

    if secciones.get('metodologia'):
        agregar_seccion("METODOLOGÍA", secciones['metodologia'])

    # Desarrollo/Resultados con tabla
    contenido_desarrollo = secciones.get('desarrollo') or secciones.get('resultados', '')
    if contenido_desarrollo:
        todos.append(PageBreak())
        titulo_sec_dev = "RESULTADOS" if tipo_informe == "laboratorio" else "DESARROLLO"
        agregar_seccion(titulo_sec_dev, contenido_desarrollo)

        # Intentar extraer tabla del texto
        filas_tabla = extraer_tabla_resultados(contenido_desarrollo)
        if filas_tabla:
            todos.append(Spacer(1, 0.3*cm))
            tabla_obj = crear_tabla_pdf(filas_tabla)
            if tabla_obj:
                todos.append(tabla_obj)
                todos.append(Spacer(1, 0.3*cm))

    if secciones.get('discusion'):
        agregar_seccion("DISCUSIÓN", secciones['discusion'])

    # Conclusiones
    if secciones.get('conclusiones'):
        todos.append(PageBreak())
        agregar_seccion("CONCLUSIONES", secciones['conclusiones'])

    if secciones.get('recomendaciones'):
        agregar_seccion("RECOMENDACIONES", secciones['recomendaciones'])

    # Referencias
    referencias_contenido = secciones.get('referencias', '')
    if referencias_contenido:
        todos.append(PageBreak())
        todos.append(Paragraph("REFERENCIAS", estilos['SeccionTitulo']))
        todos.append(HRFlowable(width="100%", thickness=1, color=COLORES['linea'], spaceAfter=6))
        for linea in referencias_contenido.split('\n'):
            linea = linea.strip()
            if linea:
                limpia = re.sub(r'^[-•*\d\.]+\s*', '', linea)
                limpia = re.sub(r'\*+', '', limpia).strip()
                if limpia:
                    todos.append(Paragraph(limpia, estilos['Referencia']))
                    todos.append(Spacer(1, 2))

    # Si no se parsearon secciones, usar texto completo
    if len(todos) < 15 and secciones.get('texto_completo'):
        todos.append(PageBreak())
        agregar_seccion("CONTENIDO DEL INFORME", secciones['texto_completo'])

    doc2.build(todos)
    buffer.seek(0)
    return buffer


# ---------------------------------------------------------------------------
# Rutas Flask
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/generar', methods=['POST'])
def generar():
    try:
        datos = request.get_json()
        if not datos:
            return jsonify({'error': 'No se recibieron datos'}), 400

        tema = limpiar_texto(datos.get('tema', ''))
        if not tema:
            return jsonify({'error': 'El tema es requerido'}), 400

        modo = datos.get('modo', 'rapido')
        tipo_informe = datos.get('tipo_informe', 'academico')
        norma = datos.get('norma', 'APA 7')
        texto_usuario = limpiar_texto(datos.get('texto_usuario', ''))
        referencias_modo = datos.get('referencias_modo', 'automatico')
        referencias_manuales = limpiar_texto(datos.get('referencias_manuales', ''))

        # Generar contenido con IA
        contenido_ia = generar_contenido_ia(
            tipo_informe, tema, modo, norma,
            texto_usuario, referencias_modo, referencias_manuales
        )

        if contenido_ia.startswith("Error"):
            return jsonify({'error': contenido_ia}), 500

        # Preparar datos para PDF
        autores_raw = datos.get('autores', [])
        if not autores_raw:
            autores_raw = [{'nombre': datos.get('autor_principal', 'Autor'), 'cargo': ''}]

        titulo_informe = datos.get('titulo') or tema
        # Intentar extraer título generado por IA
        titulo_ia_match = re.search(r'\*\*TÍTULO\*\*\s*:?\s*(.+?)(?=\n|\*\*)', contenido_ia, re.IGNORECASE)
        if titulo_ia_match and not datos.get('titulo'):
            titulo_informe = limpiar_texto(titulo_ia_match.group(1)).strip()

        pdf_datos = {
            'titulo': titulo_informe,
            'autores': autores_raw,
            'asignatura': limpiar_texto(datos.get('asignatura', '')),
            'profesor': limpiar_texto(datos.get('profesor', '')),
            'institucion': limpiar_texto(datos.get('institucion', 'Institución Educativa')),
            'ciudad': limpiar_texto(datos.get('ciudad', '')),
            'fecha': datos.get('fecha', datetime.now().strftime('%d/%m/%Y')),
            'norma': norma,
            'tipo_informe': tipo_informe,
            'contenido_ia': contenido_ia,
        }

        pdf_buffer = generar_pdf(pdf_datos)

        nombre_archivo = re.sub(r'[^\w\s-]', '', tema)[:40].strip().replace(' ', '_')
        nombre_archivo = f"informe_{nombre_archivo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=nombre_archivo
        )

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({'error': f'Error interno: {str(e)}'}), 500


@app.route('/preview', methods=['POST'])
def preview():
    """Retorna el contenido generado por IA sin PDF (para previsualización)."""
    try:
        datos = request.get_json()
        tema = limpiar_texto(datos.get('tema', ''))
        modo = datos.get('modo', 'rapido')
        tipo_informe = datos.get('tipo_informe', 'academico')
        norma = datos.get('norma', 'APA 7')
        texto_usuario = limpiar_texto(datos.get('texto_usuario', ''))
        referencias_modo = datos.get('referencias_modo', 'automatico')
        referencias_manuales = limpiar_texto(datos.get('referencias_manuales', ''))

        contenido = generar_contenido_ia(
            tipo_informe, tema, modo, norma,
            texto_usuario, referencias_modo, referencias_manuales
        )
        return jsonify({'contenido': contenido})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'version': '1.0.0'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
