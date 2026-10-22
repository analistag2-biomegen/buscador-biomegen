import base64
import io
import json
import os
import re
import unicodedata
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Image as ReportlabImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
import streamlit as st

st.set_page_config(
    page_title="Buscador de Catálogo de Laboratorio", page_icon="🔬", layout="wide"
)

# ------------------------------------------------------------------------------
# SISTEMA DE SEGURIDAD / CONTRASEÑA
# ------------------------------------------------------------------------------

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

def verificar_acceso():
    if not st.session_state.autenticado:
        st.markdown("<h2 style='color: #094A73;'>🔒 Acceso Restringido - BIOMEGEN</h2>", unsafe_allow_html=True)
        st.write("Por favor ingresa la contraseña corporativa para acceder al buscador:")

        # Cadena encriptada en Base64 de "Biomegen2026" (invisible en texto plano)
        CLAVE_ENCRIPTADA = "QmlvbWVnZW4yMDI2"

        with st.form("login_form", clear_on_submit=False):
            input_password = st.text_input("Contraseña:", type="password")
            submit_button = st.form_submit_button("Ingresar", type="primary")

            if submit_button:
                # Codificamos lo que ingresa el usuario a Base64 y comparamos
                input_b64 = base64.b64encode(input_password.strip().encode("utf-8")).decode("utf-8")

                if input_b64 == CLAVE_ENCRIPTADA:
                    st.session_state.autenticado = True
                    st.success("¡Acceso concedido!")
                    st.rerun()
                else:
                    st.error("❌ Contraseña incorrecta. Inténtalo de nuevo.")

        st.stop()

verificar_acceso()
# -------------------------------------------------------------
# ESTILOS CSS PERSONALIZADOS
# -------------------------------------------------------------
st.markdown(
    """
    <style>
    .stApp {
        background-color: #ffffff !important;
    }
    
    [data-testid="stSidebar"] {
        background-color: #8CA7B8 !important;
    }
    
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] span {
        color: #042234 !important;
    }

    [data-testid="stSidebar"] input {
        background-color: #ffffff !important;
        color: #042234 !important;
        border: none !important;
        border-radius: 6px !important;
    }
    
    div[data-baseweb="input"] > div {
        background-color: #7D888C !important;
        border-radius: 8px !important;
        color: #ffffff !important;
    }
    
    div[data-baseweb="input"] input {
        color: #ffffff !important;
    }
    
    button[data-baseweb="tab"] {
        font-weight: bold !important;
        color: #094A73 !important;
    }
    
    button[aria-selected="true"] {
        border-bottom-color: #de6519 !important;
        color: #de6519 !important;
    }
    
    .stExpander {
        border: 1.5px solid #094A73 !important;
        border-radius: 8px !important;
        background-color: #ffffff !important;
        margin-bottom: 12px !important;
        overflow: hidden !important;
    }
    
    .stExpander summary {
        background-color: #658DA6 !important;
        border-radius: 6px 6px 0px 0px !important;
    }
    
    .stExpander summary p, .stExpander summary span, .stExpander summary div {
        color: #ffffff !important;
        font-weight: bold !important;
    }
    
    div.stButton > button {
        background-color: #658DA6 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: bold !important;
    }
    
    div.stButton > button:hover {
        background-color: #094A73 !important;
        color: #ffffff !important;
    }

    [data-testid="stSidebar"] button[kind="primary"],
    [data-testid="stSidebar"] [data-testid="stBaseButton-primary"],
    [data-testid="stSidebar"] div.stDownloadButton button {
        background-color: #de6519 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 6px !important;
        font-size: 15px !important;
        font-weight: bold !important;
    }

    [data-testid="stSidebar"] button[kind="primary"]:hover,
    [data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:hover,
    [data-testid="stSidebar"] div.stDownloadButton button:hover {
        background-color: #c45412 !important;
        color: #ffffff !important;
    }

    [data-testid="stSidebar"] button[kind="secondary"],
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
        background-color: #ffffff !important;
        color: #de6519 !important;
        border: 1px solid #cccccc !important;
        border-radius: 6px !important;
        font-weight: bold !important;
    }

    div.stAlert,
    div[data-testid="stNotification"] {
        background-color: #C2E0C6 !important;
        border-radius: 8px !important;
        border: none !important;
    }

    div.stAlert p, div.stAlert span, div.stAlert div {
        color: #1e4620 !important;
        font-weight: bold !important;
    }

    .titulo-azul {
        color: #094A73 !important;
        font-weight: 800 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

SINONIMOS_ABREVIATURAS = {
    "bh": "biometria hematica",
    "bhc": "biometria hematica",
    "ego": "examen general de orina",
    "qs": "quimica sanguinea",
    "pfh": "pruebas de funcion hepatica",
    "e2": "estradiol",
    "cpk": "creatinfosfoquinasa",
    "ldl": "colesterol ldl",
    "bun": "nitrogeno ureico",
}

STOP_WORDS = {
    "de", "del", "la", "el", "los", "las", "en", "para", "con", "sin", "un", "una", "y"
}


# Equivalencias de las Químicas Sanguíneas (QS3, QS4, ...) y otras abreviaturas.
# Antes se reconstruía este diccionario en cada búsqueda; ahora se crea una sola vez.
NUMEROS_QS = [3, 4, 5, 6, 12, 14, 19, 24, 27, 28, 30, 32, 36, 38, 44]
MAPA_ALIAS_QS = {
    f"qs{n}": [f"qs{n}", f"quimica sanguinea {n}", f"quimica sanguinea de {n}"]
    for n in NUMEROS_QS
}
MAPA_ALIAS_QS["bh"] = ["bh", "biometria hematica"]
MAPA_ALIAS_QS["ego"] = ["ego", "examen general de orina"]


# Las funciones de normalización se ejecutan miles de veces con los mismos textos
# (los nombres del catálogo no cambian), así que se guardan sus resultados en memoria.
@lru_cache(maxsize=None)
def normalizar(texto):
    if not texto:
        return ""
    texto_str = str(texto).lower()
    nfkd = unicodedata.normalize("NFKD", texto_str)
    texto_sin_acentos = "".join([c for c in nfkd if not unicodedata.combining(c)])
    texto_limpio = texto_sin_acentos.replace("-", " ")
    return re.sub(r"[^\w\s]", " ", texto_limpio).strip()


@lru_cache(maxsize=None)
def normalizar_sin_espacios(texto):
    return normalizar(texto).replace(" ", "")


@lru_cache(maxsize=None)
def obtener_palabras_clave(texto):
    norm = normalizar(texto)
    palabras = norm.split()
    return tuple(p for p in palabras if p not in STOP_WORDS and len(p) > 1)

def separar_terminos_respetando_parentesis(texto):
    """Separa por comas pero ignora las comas que estén dentro de paréntesis (...)"""
    partes = []
    actual = []
    nivel_parentesis = 0

    for char in texto:
        if char == "(":
            nivel_parentesis += 1
            actual.append(char)
        elif char == ")":
            if nivel_parentesis > 0:
                nivel_parentesis -= 1
            actual.append(char)
        elif char == "," and nivel_parentesis == 0:
            partes.append("".join(actual).strip())
            actual = []
        else:
            actual.append(char)

    if actual:
        partes.append("".join(actual).strip())

    return [p for p in partes if p]

@lru_cache(maxsize=None)
def _tokens_objetivo(texto):
    return frozenset(obtener_palabras_clave(texto))

def coincide_busqueda(termino_buscado, texto_objetivo):
    t_clean = normalizar_sin_espacios(termino_buscado)
    obj_clean = normalizar_sin_espacios(texto_objetivo)

    if not t_clean or not obj_clean:
        return False

    # Evitar que 'CA 27-29' haga match con 'QS27' o 'Química 27'
    if "ca27" in t_clean and "qs" in obj_clean:
        return False
    if "qs" in t_clean and "ca27" in obj_clean:
        return False

    if t_clean in obj_clean or obj_clean in t_clean:
        return True

    t_norm = normalizar(termino_buscado)
    t_expandido = SINONIMOS_ABREVIATURAS.get(t_norm, t_norm)
    if normalizar_sin_espacios(t_expandido) in obj_clean:
        return True

    tokens_buscados = obtener_palabras_clave(t_expandido)
    tokens_objetivo = _tokens_objetivo(texto_objetivo)

    if tokens_buscados:
        coincidencias = sum(
            1 for tok in tokens_buscados
            if tok in tokens_objetivo or any(tok in obj_tok for obj_tok in tokens_objetivo)
        )
        if coincidencias / len(tokens_buscados) >= 0.5:
            return True

    return False

def desduplicar_paquetes(lista_paquetes):
    paquetes_unicos = []
    nombres_vistos = set()
    for pkg in lista_paquetes:
        if isinstance(pkg, dict):
            nombre = pkg.get("nombre", "").strip()
            clave = normalizar(nombre)
            if clave and clave not in nombres_vistos:
                nombres_vistos.add(clave)
                paquetes_unicos.append(pkg)
    return paquetes_unicos


def obtener_precio_paquete(pkg):
    if isinstance(pkg, dict):
        return pkg.get("precio", 0.0)
    return 0.0


RUTAS_POSIBLES_LOGO = ["LOGO BIOMEGEN SF.png", "LOGO BIOMEGEN.png", "LOGO BIOMEGEN_2.png"]


def buscar_logo():
    for ruta in RUTAS_POSIBLES_LOGO:
        if os.path.exists(ruta):
            return ruta
    return None


_SIN_RESULTADO = object()


class Catalogo:
    """Guarda el catálogo ya indexado para no recorrer `datos.json` completo
    en cada clic. Se construye una sola vez (ver `cargar_catalogo`) y es de solo lectura."""

    def __init__(self, datos):
        self.datos = datos
        self.paquetes = {}  # nombre -> paquete (primera aparición)
        self.singles = {}  # nombre normalizado -> single
        self._analitos_por_paquete = {}  # nombre paquete -> analitos que lo listan
        self._cache_precio = {}
        self._cache_analitos = {}
        self._cache_match_analito = {}

        for item in datos:
            tipo_item = item.get("tipo")
            if tipo_item == "paquete" or "paquetes" in item:
                for pkg in item.get("paquetes", []):
                    if isinstance(pkg, dict):
                        nom_p = pkg.get("nombre")
                        if nom_p and nom_p not in self.paquetes:
                            self.paquetes[nom_p] = pkg
            elif tipo_item in ["single", "individual"]:
                nom_s = item.get("analito", item.get("nombre"))
                if nom_s:
                    self.singles[normalizar(nom_s)] = item

        # Índice inverso: paquete -> analitos (se usa cuando el paquete no trae
        # su lista `analitos_incluidos`). Antes se buscaba recorriendo todo el catálogo.
        for item in datos:
            for pkg in item.get("paquetes", []):
                self._analitos_por_paquete.setdefault(pkg.get("nombre"), []).append(item.get("analito"))

        # Texto (nombre + analitos) de cada paquete, ya normalizado, para la búsqueda cruzada.
        self.texto_paquete = {
            nombre: normalizar(nombre + " " + " ".join(pkg.get("analitos_incluidos", [])))
            for nombre, pkg in self.paquetes.items()
        }

    # ---------- Analitos de un paquete ----------
    def analitos_de_paquete(self, nombre):
        res = self._cache_analitos.get(nombre)
        if res is None:
            propios = self.paquetes[nombre].get("analitos_incluidos", [])
            res = list(propios) if propios else list(self._analitos_por_paquete.get(nombre, []))
            self._cache_analitos[nombre] = res
        return res

    # ---------- Precio de un estudio faltante ----------
    def buscar_precio_estudio_o_single(self, nombre_analito):
        res = self._cache_precio.get(nombre_analito, _SIN_RESULTADO)
        if res is _SIN_RESULTADO:
            res = self._buscar_precio(nombre_analito)
            self._cache_precio[nombre_analito] = res
        return res

    def _buscar_precio(self, nombre_analito):
        norm_a = normalizar(nombre_analito)
        if norm_a in self.singles:
            return self.singles[norm_a]
        for item in self.datos:
            if coincide_busqueda(nombre_analito, item.get("analito", "")):
                if item.get("tipo") in ["single", "individual"]:
                    return item
                elif item.get("paquetes"):
                    pkgs_ord = sorted(item["paquetes"], key=lambda x: x.get("precio", 0.0))
                    if pkgs_ord:
                        return pkgs_ord[0]
        return None

    # ---------- Pestaña 1: paquetes integrales ----------
    def _paquetes_de_analitos_que_coinciden(self, termino):
        """Nombres de paquetes que contienen algún analito que coincide con el término."""
        res = self._cache_match_analito.get(termino)
        if res is None:
            res = set()
            for item_d in self.datos:
                # Omitir si es un estudio de tipo Single puro
                if item_d.get("tipo") in ["single", "individual"]:
                    continue
                if coincide_busqueda(termino, item_d.get("analito", "")):
                    for p_asoc in item_d.get("paquetes", []):
                        nom_p = p_asoc.get("nombre", "")
                        if nom_p and normalizar(nom_p) not in ["single", "individual"]:
                            res.add(nom_p)
            self._cache_match_analito[termino] = res
        return res

    def paquetes_integrales(self, terminos_raw):
        # Si la lista de términos viene de un string directo, usar el separador inteligente
        if isinstance(terminos_raw, str):
            terminos_raw = separar_terminos_respetando_parentesis(terminos_raw)

        if len(terminos_raw) < 2:
            return []

        por_analito = {t: self._paquetes_de_analitos_que_coinciden(t) for t in terminos_raw}
        variantes_por_termino = {
            t: MAPA_ALIAS_QS.get(normalizar(t), [normalizar(t)]) for t in terminos_raw
        }

        coincidencias = []
        for nombre_pkg, pkg_info in self.paquetes.items():
            texto = self.texto_paquete[nombre_pkg]
            encontrados = {}
            for t_raw in terminos_raw:
                hallado = any(
                    var in texto or coincide_busqueda(var, texto)
                    for var in variantes_por_termino[t_raw]
                )
                if not hallado and nombre_pkg in por_analito[t_raw]:
                    hallado = True
                if hallado:
                    encontrados[t_raw] = None

            if encontrados:
                coincidencias.append({"datos_paquete": pkg_info, "terminos_encontrados": encontrados})

        coincidencias.sort(
            key=lambda x: (-len(x["terminos_encontrados"]), x["datos_paquete"].get("precio", 0.0))
        )
        return coincidencias

    # ---------- Pestaña 2: paquete máster ----------
    def candidatos_master(self, paquetes_seleccionados):
        analitos_totales_map = {}
        suma_precios = 0.0

        for p_nom in paquetes_seleccionados:
            suma_precios += self.paquetes[p_nom].get("precio", 0.0)
            for a in self.analitos_de_paquete(p_nom):
                if a:
                    clave = normalizar(a)
                    if clave and clave not in analitos_totales_map:
                        analitos_totales_map[clave] = a

        analitos_totales_keys = set(analitos_totales_map.keys())

        if not analitos_totales_keys:
            for p_nom in paquetes_seleccionados:
                analitos_totales_map[normalizar(p_nom)] = p_nom
            analitos_totales_keys = set(analitos_totales_map.keys())

        candidatos = []
        for p_nom, p_data in self.paquetes.items():
            if p_nom in paquetes_seleccionados:
                continue

            claves_cand = {normalizar(a) for a in self.analitos_de_paquete(p_nom) if a}
            if not claves_cand:
                continue

            cubiertos = analitos_totales_keys & claves_cand
            faltantes = analitos_totales_keys - claves_cand
            pct = (len(cubiertos) / len(analitos_totales_keys)) * 100.0

            if pct >= 35.0:
                faltantes_nombres = [analitos_totales_map[k] for k in faltantes if k in analitos_totales_map]

                costo_faltantes = 0.0
                detalle = []
                for f_nom in faltantes_nombres:
                    item_f = self.buscar_precio_estudio_o_single(f_nom)
                    if item_f:
                        p_f = item_f.get("precio", 0.0)
                        if p_f == 0.0 and item_f.get("paquetes"):
                            p_f = item_f["paquetes"][0].get("precio", 0.0)
                        costo_faltantes += p_f
                        detalle.append((f_nom, item_f, p_f))
                    else:
                        detalle.append((f_nom, None, 0.0))

                candidatos.append({
                    "paquete": p_data,
                    "pct": pct,
                    "cubiertos_count": len(cubiertos),
                    "total_requerido": len(analitos_totales_keys),
                    "faltantes_count": len(faltantes),
                    "faltantes_nombres": sorted(faltantes_nombres),
                    "items_faltantes_detalle": detalle,
                    "costo_faltantes": costo_faltantes,
                    "costo_combo_total": p_data.get("precio", 0.0) + costo_faltantes,
                })

        candidatos.sort(key=lambda x: (-x["pct"], x["costo_combo_total"]))
        return {
            "total_analitos": len(analitos_totales_keys),
            "suma_precios": suma_precios,
            "candidatos": candidatos,
        }


def generar_pdf_binario(carrito, nombre_paciente, desc_general_pct, vigencia_texto, fecha_txt):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    style_normal = styles["Normal"]

    style_header_right = ParagraphStyle(
        "HeaderRight",
        parent=style_normal,
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        alignment=2,
        textColor=colors.HexColor("#334155"),
    )

    style_banner = ParagraphStyle(
        "Banner",
        parent=style_normal,
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        alignment=1,
        textColor=colors.HexColor("#0f172a"),
    )

    style_cell = ParagraphStyle(
        "Cell",
        parent=style_normal,
        fontName="Helvetica",
        fontSize=8.5,
        leading=10.5,
    )

    style_cell_bold = ParagraphStyle(
        "CellBold",
        parent=style_normal,
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=10.5,
    )

    style_cell_right = ParagraphStyle(
        "CellRight",
        parent=style_normal,
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=10.5,
        alignment=2,
    )

    style_leyenda = ParagraphStyle(
        "LeyendaDH",
        parent=style_normal,
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#475569"),
    )

    story = []
    ahora = fecha_txt

    ruta_logo_final = buscar_logo()

    if ruta_logo_final:
        p_logo = ReportlabImage(ruta_logo_final, width=180, height=45)
    else:
        p_logo = Paragraph("<b>BIOMEGEN</b><br/><font size=8 color='#094A73'>LAB GENÓMICO</font>", style_cell_bold)

    p_addr = Paragraph(
        "HOSPITAL SAN JOSÉ, PROLONGACIÓN CONSTITUYENTES NO. EXT. 302 NO. INT. TORRE 3, PISO 17 COL. EL JACAL,<br/>QUERÉTARO, QUERÉTARO",
        style_header_right,
    )
    t_header = Table([[p_logo, p_addr]], colWidths=[200, 340])
    t_header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story.append(t_header)
    story.append(Spacer(1, 10))

    subtotal_bruto = 0.0
    desc_items_acumulado = 0.0

    table_data = [[
        Paragraph("<b>ESTUDIO</b>", style_cell_bold),
        Paragraph("<b>TOTAL</b>", style_cell_right),
        Paragraph("<b>TIEMPO ENTREGA</b>", style_banner),
    ]]

    indicaciones_paciente = []

    for nombre, item in carrito.items():
        precio_u = item["datos"].get("precio", 0.0)
        cant = item["cantidad"]
        pct_d = item.get("descuento_pct", 0)

        base_item = precio_u * cant
        monto_d_item = base_item * (pct_d / 100.0)
        precio_item_final = base_item - monto_d_item

        subtotal_bruto += base_item
        desc_items_acumulado += monto_d_item

        tiempo = item["datos"].get("tiempo_entrega", "Mismo día")
        indicacion = item["datos"].get("indicaciones", "Sin indicaciones especiales.")

        nombre_fmt = nombre.upper()
        if cant > 1:
            nombre_fmt += f" (x{cant})"
        if pct_d > 0:
            nombre_fmt += f" [-{pct_d}% desc.]"

        # Mostrar el precio propio del estudio en la fila (sin aplicar el descuento general)
        table_data.append([
            Paragraph(nombre_fmt, style_cell),
            Paragraph(f"${precio_item_final:,.2f}", style_cell_right),
            Paragraph(tiempo, style_cell),
        ])

        indicaciones_paciente.append((nombre_fmt, indicacion))

    subtotal_despues_items = subtotal_bruto - desc_items_acumulado
    monto_desc_general = subtotal_despues_items * (desc_general_pct / 100.0)
    descuento_total_acumulado = desc_items_acumulado + monto_desc_general
    total_final = subtotal_bruto - descuento_total_acumulado

    has_discount = descuento_total_acumulado > 0
    desc_label = "Con Descuento" if has_discount else "Sin Descuento"
    paciente_texto = nombre_paciente.strip() if nombre_paciente.strip() else "Paciente General"
    vigencia_val = vigencia_texto.strip() if vigencia_texto.strip() else "30 días hábiles"

    p_meta_left = Paragraph(f"<b>Atención a:</b> {paciente_texto}<br/><b>Médico:</b> A quien corresponda", style_cell)
    p_meta_right = Paragraph(
        f"<b>Presupuesto:</b> {desc_label}<br/><b>Fecha Impresión:</b> {ahora}<br/><b>Vigencia:</b> {vigencia_val}",
        style_cell_right,
    )
    t_meta = Table([[p_meta_left, p_meta_right]], colWidths=[270, 270])
    t_meta.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("PADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(t_meta)
    story.append(Spacer(1, 10))

    story.append(Paragraph("PRESUPUESTO DE ESTUDIOS", style_banner))
    story.append(Spacer(1, 4))

    t_estudios = Table(table_data, colWidths=[280, 130, 130])
    t_estudios.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#000000")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    story.append(t_estudios)
    story.append(Spacer(1, 8))

    # El Descuento General aparece como deducción en el bloque de totales final
    totales_data = [
        [Paragraph("Subtotal:", style_cell_right), Paragraph(f"${subtotal_bruto:,.2f}", style_cell_right)],
    ]
    if descuento_total_acumulado > 0:
        totales_data.append([
            Paragraph("Descuento:", style_cell_right),
            Paragraph(f"-${descuento_total_acumulado:,.2f}", style_cell_right),
        ])
    totales_data.append([
        Paragraph("<b>Total:</b>", style_cell_right),
        Paragraph(f"<b>${total_final:,.2f} MXN</b>", style_cell_right),
    ])

    t_totales = Table(totales_data, colWidths=[100, 120])
    t_totales.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "RIGHT"), ("PADDING", (0, 0), (-1, -1), 3)]))

    t_totales_wrapper = Table([["", t_totales]], colWidths=[320, 220])
    t_totales_wrapper.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(t_totales_wrapper)
    story.append(Spacer(1, 10))

    story.append(Paragraph("INDICACIONES PARA EL PACIENTE", style_banner))
    story.append(Spacer(1, 4))

    ind_data = [[Paragraph("<b>NOMBRE COMPLETO</b>", style_cell_bold), Paragraph("<b>INDICACIONES</b>", style_cell_bold)]]

    for est_nom, est_ind in indicaciones_paciente:
        ind_data.append([Paragraph(est_nom, style_cell), Paragraph(est_ind, style_cell)])

    t_indicaciones = Table(ind_data, colWidths=[200, 340])
    t_indicaciones.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#000000")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )
    story.append(t_indicaciones)

    story.append(Spacer(1, 10))
    story.append(Paragraph("* D.H. = Día Hábil", style_leyenda))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# -------------------------------------------------------------
# MEMORIA DE SESIÓN
# -------------------------------------------------------------
if "carrito" not in st.session_state:
    st.session_state.carrito = {}

if "descuento_general_pct" not in st.session_state:
    st.session_state.descuento_general_pct = 0


def agregar_al_carrito(paquete):
    nombre = paquete.get("nombre", paquete.get("analito", "Estudio Sin Nombre"))
    if nombre in st.session_state.carrito:
        st.session_state.carrito[nombre]["cantidad"] += 1
        st.toast(f"➕ Se añadió otro **{nombre}** (Total: {st.session_state.carrito[nombre]['cantidad']})", icon="🛒")
    else:
        st.session_state.carrito[nombre] = {
            "datos": paquete,
            "cantidad": 1,
            "descuento_pct": 0,
        }
        st.toast(f"✅ ¡{nombre} agregado a la cotización!", icon="🛒")


def modificar_cantidad(nombre, cambio):
    if nombre in st.session_state.carrito:
        st.session_state.carrito[nombre]["cantidad"] += cambio
        if st.session_state.carrito[nombre]["cantidad"] <= 0:
            del st.session_state.carrito[nombre]
            st.toast(f"🗑️ Se eliminó {nombre}", icon="🧹")


def vaciar_carrito():
    st.session_state.carrito = {}
    st.session_state.descuento_general_pct = 0
    st.toast("🧹 Cotización vaciada con éxito", icon="✨")


@st.cache_data
def logo_en_base64(ruta):
    with open(ruta, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode()


@st.cache_data(show_spinner=False)
def generar_pdf_en_cache(carrito, nombre_paciente, desc_general_pct, vigencia_texto, fecha_txt):
    """El PDF solo se vuelve a generar si cambia algo de la cotización
    (antes se regeneraba en cada clic de la página)."""
    return generar_pdf_binario(carrito, nombre_paciente, desc_general_pct, vigencia_texto, fecha_txt)


# -------------------------------------------------------------
# SIDEBAR
# -------------------------------------------------------------
with st.sidebar:
    ruta_logo_final = buscar_logo()

    if ruta_logo_final:
        encoded_string = logo_en_base64(ruta_logo_final)

        st.markdown(
            f"""
            <div style="text-align: center; margin-bottom: 20px;">
                <img src="data:image/png;base64,{encoded_string}" 
                     style="width: 100%; max-width: 240px; mix-blend-mode: multiply; filter: contrast(120%);" />
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.header("📋 Cotización")

    if st.session_state.carrito:
        nombre_paciente_input = st.text_input(
            "👤 Nombre del Paciente (Atención a):",
            placeholder="Ej. María Fernanda Gómez",
            key="input_paciente",
        )

        vigencia_input = st.text_input(
            "🗓️ Vigencia de la Cotización:",
            value="30 días hábiles",
            placeholder="Ej. 15 días, Hasta agotar existencias...",
            key="input_vigencia",
        )

        st.divider()

        subtotal_base_acumulado = 0.0
        monto_desc_items_total = 0.0

        for nombre, item in list(st.session_state.carrito.items()):
            precio = item["datos"].get("precio", 0.0)
            cantidad = item["cantidad"]
            desc_pct = item.get("descuento_pct", 0)

            precio_base = precio * cantidad
            monto_desc_item = precio_base * (desc_pct / 100.0)
            subtotal_item = precio_base - monto_desc_item

            subtotal_base_acumulado += precio_base
            monto_desc_items_total += monto_desc_item

            st.markdown(f"**{nombre}**")
            st.write(f"Precio c/u: ${precio:,.2f} MXN")

            col_minus, col_cant, col_plus, col_del = st.columns([0.8, 1.2, 0.8, 1])
            with col_minus:
                if st.button("➖", key=f"sub_{nombre}"):
                    modificar_cantidad(nombre, -1)
                    st.rerun()
            with col_cant:
                st.markdown(
                    f"<div style='text-align: center; font-weight: bold; font-size: 18px;'>{cantidad}</div>",
                    unsafe_allow_html=True,
                )
            with col_plus:
                if st.button("➕", key=f"add_{nombre}"):
                    modificar_cantidad(nombre, 1)
                    st.rerun()
            with col_del:
                if st.button("🗑️", key=f"del_{nombre}"):
                    del st.session_state.carrito[nombre]
                    st.toast(f"🗑️ Se eliminó {nombre}", icon="🧹")
                    st.rerun()

            nuevo_desc = st.number_input(
                "Descuento estudio (%):",
                min_value=0,
                max_value=100,
                value=int(desc_pct),
                step=5,
                key=f"desc_{nombre}",
            )
            if nuevo_desc != desc_pct:
                st.session_state.carrito[nombre]["descuento_pct"] = nuevo_desc
                st.rerun()

            if desc_pct > 0:
                st.write(f"Subtotal: ~${precio_base:,.2f}~ **${subtotal_item:,.2f} MXN** *(-{desc_pct}%)*")
            else:
                st.write(f"Subtotal: **${subtotal_item:,.2f} MXN**")

            st.divider()

        st.markdown("### 🔖 Descuento General")
        nuevo_desc_gen = st.number_input(
            "Descuento al Total (%):",
            min_value=0,
            max_value=100,
            value=int(st.session_state.descuento_general_pct),
            step=5,
            key="input_desc_general",
        )
        if nuevo_desc_gen != st.session_state.descuento_general_pct:
            st.session_state.descuento_general_pct = nuevo_desc_gen
            st.rerun()

        subtotal_parcial = subtotal_base_acumulado - monto_desc_items_total
        monto_desc_general = subtotal_parcial * (st.session_state.descuento_general_pct / 100.0)
        total_descuentos = monto_desc_items_total + monto_desc_general
        total_final_cotizacion = subtotal_base_acumulado - total_descuentos

        st.divider()
        st.write(f"Subtotal Bruto: **${subtotal_base_acumulado:,.2f} MXN**")

        if total_descuentos > 0:
            st.write(f"Descuento Total: **-${total_descuentos:,.2f} MXN**")

        st.markdown(f"### 💵 Total: **${total_final_cotizacion:,.2f} MXN**")

        pdf_bytes = generar_pdf_en_cache(
            st.session_state.carrito,
            nombre_paciente_input,
            st.session_state.descuento_general_pct,
            vigencia_input,
            datetime.now().strftime("%d/%m/%Y"),
        )
        st.download_button(
            label="📄 Descargar Presupuesto PDF",
            data=pdf_bytes,
            file_name=f"presupuesto_estudios_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary",
        )

        if st.button("🧹 Vaciar Cotización", use_container_width=True, type="secondary"):
            vaciar_carrito()
            st.rerun()
    else:
        st.info("La cotización está vacía. Agrega paquetes para cotizar.")


# -------------------------------------------------------------
# CONTENIDO PRINCIPAL
# -------------------------------------------------------------
st.markdown("<h1 class='titulo-azul'>🔬 Buscador de Analitos y Paquetes de Laboratorio</h1>", unsafe_allow_html=True)


@st.dialog("🫆 Detalles del Estudio")
def mostrar_modal_detalles(estudio):
    nombre = estudio.get("nombre", estudio.get("analito", "Estudio"))
    st.markdown(f"<h3 class='titulo-azul'>🫆 Detalles del Estudio</h3>", unsafe_allow_html=True)
    st.markdown(f"🧪 **{nombre}**")
    st.markdown(f"💰 **Precio:** ${estudio.get('precio', 0):,.2f} MXN")
    st.markdown(f"💉 **Tipo de muestra:** {estudio.get('tipo_muestra', 'No especificada')}")
    st.markdown(f"⏳ **Tiempo de entrega:** {estudio.get('tiempo_entrega', 'N/A')}")

    st.divider()

    st.markdown("💡 **Definición del Estudio**")
    st.info(estudio.get("definicion", "Sin definición disponible para este estudio."))

    st.markdown("🔬 **Lo que se analiza en este estudio:**")
    
    # 1. Obtener analitos tal cual están guardados
    analitos_raw = estudio.get("analitos_incluidos", estudio.get("analitos", []))
    
    # 2. Si viene vacía la lista, rastrear en la base global
    if not analitos_raw:
        nom_norm = normalizar(nombre)
        analitos_hallados = []
        for item_d in datos:
            a_nom = item_d.get("analito")
            if a_nom:
                for pkg_d in item_d.get("paquetes", []):
                    pkg_nom_norm = normalizar(pkg_d.get("nombre", ""))
                    if nom_norm in pkg_nom_norm or pkg_nom_norm in nom_norm:
                        if a_nom not in analitos_hallados:
                            analitos_hallados.append(a_nom)
        analitos_raw = analitos_hallados

    # 3. Mostrar TODOS los analitos y etiquetas (incluyendo QS6, QS12, etc.) sin omitir ninguna
    if analitos_raw:
        for a in analitos_raw:
            st.markdown(f"• {a}")
    else:
        st.markdown(f"• {nombre}")

    st.divider()
    st.markdown(f"📜 **Indicaciones:** {estudio.get('indicaciones', 'N/A')}")

    if st.button("➕ Agregar este estudio a la cotización", key=f"modal_add_{nombre}", use_container_width=True):
        agregar_al_carrito(estudio)
        st.rerun()

@st.cache_resource
def cargar_catalogo(fecha_modificacion):
    """Lee e indexa datos.json una sola vez. Si cambias el archivo (nueva fecha de
    modificación) se vuelve a cargar solo; antes se releía cada segundo (ttl=1)."""
    with open("datos.json", "r", encoding="utf-8") as f:
        return Catalogo(json.load(f))


CATALOGO = cargar_catalogo(os.path.getmtime("datos.json"))
datos = CATALOGO.datos
TODOS_LOS_PAQUETES = CATALOGO.paquetes


def renderizar_tarjeta_paquete(pkg, key_prefix, idx, es_expandido=False):
    nombre = pkg.get("nombre", "Paquete")
    precio = pkg.get("precio", 0)
    indicaciones = pkg.get("indicaciones", "Sin indicaciones.")
    tiempo = pkg.get("tiempo_entrega", "No especificado")
    muestra = pkg.get("tipo_muestra", "No especificada")

    with st.expander(f"📦 **{nombre}** — 💰 **${precio:,.2f} MXN**", expanded=es_expandido):
        col_info, col_add, col_det = st.columns([2.5, 1, 1])

        with col_info:
            st.markdown(f"💉 **Tipo de muestra:** {muestra}")
            st.markdown(f"📜 **Indicaciones:** {indicaciones}")
            st.markdown(f"⏳ **Tiempo de entrega:** {tiempo}")

        with col_add:
            if st.button("➕ Agregar", key=f"btn_add_{key_prefix}_{idx}_{nombre}", use_container_width=True):
                agregar_al_carrito(pkg)
                st.rerun()

        with col_det:
            if st.button("🫆 Detalles", key=f"btn_det_{key_prefix}_{idx}_{nombre}", use_container_width=True):
                mostrar_modal_detalles(pkg)


# -------------------------------------------------------------
# MODALIDAD DE BÚSQUEDA MEDIANTE 3 PESTAÑAS SUPERIORES
# -------------------------------------------------------------
tab_modo_1, tab_modo_2, tab_modo_3 = st.tabs([
    "🔎 Buscador de Analitos y Paquetes",
    "🧩 Encontrar Paquete Máster (Combinar Paquetes)",
    "⚗️ Buscador de Pruebas Individuales / Singles",
])

# -------------------------------------------------------------
# PESTAÑA 1: BUSCADOR DE ANALITOS Y PAQUETES (CON EQUIVALENCIAS QS)
# -------------------------------------------------------------
with tab_modo_1:
    st.write("Ingresa uno o varios analitos o paquetes **separados por comas** (ej: *Glucosa, QS3, Antidoping*).")

    busqueda_input = st.text_input(
        "🔎 Escribe aquí las pruebas o analitos (separados por comas):",
        placeholder="Ej. Glucosa, QS3, Antidoping...",
        key="input_busqueda_principal",
    )

    if busqueda_input:
        terminos_raw = separar_terminos_respetando_parentesis(busqueda_input)

        paquetes_coincidencias = CATALOGO.paquetes_integrales(terminos_raw)

        nombres_tabs = []
        if paquetes_coincidencias:
            nombres_tabs.append("🌟 Paquetes Integrales")

        for t in terminos_raw:
            nombres_tabs.append(f"🧪 {t.title()}")

        tabs_creadas = st.tabs(nombres_tabs)
        tab_index = 0

        # RENDERIZAR PESTAÑA 🌟 PAQUETES INTEGRALES
        if paquetes_coincidencias:
            with tabs_creadas[tab_index]:
                st.success("🌟 **Paquetes integrales sugeridos que contienen los analitos o QS buscados:**")

                top_cross = paquetes_coincidencias[:3]
                resto_cross = paquetes_coincidencias[3:]

                for idx, match in enumerate(top_cross):
                    pkg = match["datos_paquete"]
                    cant = len(match["terminos_encontrados"])
                    total_b = len(terminos_raw)
                    lista_enc = ", ".join([t.title() for t in match["terminos_encontrados"]])

                    st.markdown(
                        f"<h4 class='titulo-azul'>{pkg.get('nombre')} — <i>(Incluye {cant} de {total_b}: {lista_enc})</i></h4>",
                        unsafe_allow_html=True,
                    )
                    renderizar_tarjeta_paquete(pkg, "top_cross", idx, es_expandido=(idx == 0))

                if resto_cross:
                    with st.expander(f"✨ **Ver {len(resto_cross)} opciones integrales más...**"):
                        for idx, match in enumerate(resto_cross):
                            pkg = match["datos_paquete"]
                            cant = len(match["terminos_encontrados"])
                            total_b = len(terminos_raw)
                            lista_enc = ", ".join([t.title() for t in match["terminos_encontrados"]])

                            st.markdown(f"**{pkg.get('nombre')}** — *(Incluye {cant} de {total_b}: {lista_enc})*")
                            renderizar_tarjeta_paquete(pkg, "resto_cross", idx, es_expandido=False)

            tab_index += 1

        # RENDERIZAR PESTAÑAS INDIVIDUALES POR CADA TÉRMINO
        for termino_raw in terminos_raw:
            with tabs_creadas[tab_index]:
                t_norm_buscado = normalizar(termino_raw)
                
                # 1. BÚSQUEDA DIRECTA COMO PAQUETE (EJ: PERFIL HEPÁTICO, CHECK-UP, QS28)
                paquetes_directos_exactos = []
                for nom_pkg, pkg_obj in TODOS_LOS_PAQUETES.items():
                    nom_pkg_norm = normalizar(nom_pkg)
                    if t_norm_buscado == nom_pkg_norm or t_norm_buscado in nom_pkg_norm or nom_pkg_norm in t_norm_buscado:
                        paquetes_directos_exactos.append(pkg_obj)

                paquetes_directos_exactos = desduplicar_paquetes(paquetes_directos_exactos)

                if paquetes_directos_exactos:
                    st.markdown(
                        f"<h3 class='titulo-azul'>📦 Paquetes encontrados para: \"{termino_raw.title()}\"</h3>",
                        unsafe_allow_html=True,
                    )
                    paquetes_ordenados = sorted(paquetes_directos_exactos, key=obtener_precio_paquete)
                    top_pkg = paquetes_ordenados[:3]
                    resto_pkg = paquetes_ordenados[3:]

                    for idx, pkg in enumerate(top_pkg):
                        renderizar_tarjeta_paquete(pkg, f"top_dir_{termino_raw}", idx, es_expandido=(idx == 0))

                    if resto_pkg:
                        with st.expander(f"✨ **Ver {len(resto_pkg)} paquetes más relacionados con {termino_raw.title()}...**"):
                            for idx, pkg in enumerate(resto_pkg):
                                renderizar_tarjeta_paquete(pkg, f"resto_dir_{termino_raw}", idx, es_expandido=False)

                else:
                    # 2. BÚSQUEDA EXCLUSIVA DEL ANALITO/ESTUDIO INGRESADO (CON FILTRADO DE RELEVANCIA)
                    coincidencias = []
                    nombres_vistos = set()

                    # Palabras genéricas y prefijos que no definen la prueba específica por sí solos
                    words_ignoradas = {
                        "cultivo", "cultivos", "exudado", "exudados", "antigeno", "antigenos", 
                        "anticuerpo", "anticuerpos", "serica", "serico", "suero", "ca", "y", "de", "del", "la", "el"
                    }
                    words_clave_buscadas = [w for w in t_norm_buscado.split() if w not in words_ignoradas and len(w) > 1]

                    for item in datos:
                        nom_item = item.get("analito", "")
                        nom_item_norm = normalizar(nom_item)

                        match_estricto = False
                        prioridad = 1
                        
                        # 1. Match si la frase completa o el número/sigla exacta coincide
                        if t_norm_buscado in nom_item_norm or nom_item_norm in t_norm_buscado:
                            match_estricto = True
                            prioridad = 100  # Máxima prioridad
                        elif words_clave_buscadas and all(w in nom_item_norm.split() for w in words_clave_buscadas):
                            match_estricto = True
                            prioridad = len(words_clave_buscadas)

                        if match_estricto:
                            clave_u = nom_item
                            if clave_u and clave_u not in nombres_vistos:
                                nombres_vistos.add(clave_u)
                                coincidencias.append((item, prioridad))

                    if coincidencias:
                        # Ordenar por relevancia para que el estudio exacto quede arriba
                        coincidencias_ordenadas = [c[0] for c in sorted(coincidencias, key=lambda x: -x[1])]

                        lista_singles = [res for res in coincidencias_ordenadas if res.get("tipo") in ["single", "individual"]]
                        
                        lista_paquetes_analito = []
                        for res in coincidencias_ordenadas:
                            if res.get("tipo") not in ["single", "individual"] and res.get("paquetes"):
                                pkgs_reales = [
                                    p for p in res.get("paquetes", [])
                                    if p.get("nombre") and normalizar(p.get("nombre")) not in ["single", "individual"]
                                ]
                                if pkgs_reales:
                                    res_copy = dict(res)
                                    res_copy["paquetes"] = pkgs_reales
                                    lista_paquetes_analito.append(res_copy)

                        # A) Mostrar Paquetes Reales solo si el analito pertenece a alguno
                        if lista_paquetes_analito:
                            for res in lista_paquetes_analito:
                                paquetes_asociados = desduplicar_paquetes(res.get("paquetes", []))
                                if paquetes_asociados:
                                    cat_txt = f" — <i>({res.get('categoria', '')})</i>" if res.get('categoria') else ""
                                    st.markdown(
                                        f"<h4 class='titulo-azul'>✨ Paquetes con {res['analito']}{cat_txt}</h4>",
                                        unsafe_allow_html=True,
                                    )

                                    paquetes_ordenados = sorted(paquetes_asociados, key=obtener_precio_paquete)
                                    top_pkg = paquetes_ordenados[:3]
                                    resto_pkg = paquetes_ordenados[3:]

                                    for idx, pkg in enumerate(top_pkg):
                                        renderizar_tarjeta_paquete(pkg, f"top_ind_{res['analito']}_{termino_raw}", idx, es_expandido=(idx == 0))

                                    if resto_pkg:
                                        with st.expander(f"✨ **Ver {len(resto_pkg)} paquetes más que incluyen {res['analito']}...**"):
                                            for idx, pkg in enumerate(resto_pkg):
                                                renderizar_tarjeta_paquete(pkg, f"resto_ind_{res['analito']}_{termino_raw}", idx, es_expandido=False)

                        # B) Mostrar Estudio Individual (Single) con Leyenda Informativa
                        if lista_singles or not lista_paquetes_analito:
                            if lista_paquetes_analito:
                                st.markdown("---")
                                st.markdown("<h3 class='titulo-azul'>🏺 Estudios Individuales (Singles)</h3>", unsafe_allow_html=True)

                                top_singles_p1 = coincidencias_ordenadas[:3]
                                resto_singles_p1 = coincidencias_ordenadas[3:]

                                for res in top_singles_p1:
                                    nom_s = res.get("analito", res.get("nombre", "Estudio Individual"))
                                    with st.expander(f"📦 **{nom_s}** — 💰 **${res.get('precio', 0.0):,.2f} MXN**", expanded=True):
                                        col_info, col_add, col_det = st.columns([2.5, 1, 1])

                                        with col_info:
                                            st.markdown(f"💉 **Tipo de muestra:** {res.get('tipo_muestra', 'N/A')}")
                                            st.markdown(f"📜 **Indicaciones:** {res.get('indicaciones', 'N/A')}")
                                            st.markdown(f"⏳ **Tiempo de entrega:** {res.get('tiempo_entrega', 'N/A')}")

                                        with col_add:
                                            if st.button("➕ Agregar", key=f"btn_add_single_{nom_s}_{termino_raw}", use_container_width=True):
                                                agregar_al_carrito(res)
                                                st.rerun()

                                        with col_det:
                                            if st.button("🫆 Detalles", key=f"btn_det_single_{nom_s}_{termino_raw}", use_container_width=True):
                                                mostrar_modal_detalles(res)

                                if resto_singles_p1:
                                    with st.expander(f"✨ **Ver {len(resto_singles_p1)} estudios individuales más...**"):
                                        for res in resto_singles_p1:
                                            nom_s = res.get("analito", res.get("nombre", "Estudio Individual"))
                                            st.markdown(f"**{nom_s}** — 💰 **${res.get('precio', 0.0):,.2f} MXN**")
                                            col_info, col_add, col_det = st.columns([2.5, 1, 1])

                                            with col_info:
                                                st.markdown(f"💉 **Tipo de muestra:** {res.get('tipo_muestra', 'N/A')}")
                                                st.markdown(f"📜 **Indicaciones:** {res.get('indicaciones', 'N/A')}")
                                                st.markdown(f"⏳ **Tiempo de entrega:** {res.get('tiempo_entrega', 'N/A')}")

                                            with col_add:
                                                if st.button("➕ Agregar", key=f"btn_add_single_resto_{nom_s}_{termino_raw}", use_container_width=True):
                                                    agregar_al_carrito(res)
                                                    st.rerun()

                                            with col_det:
                                                if st.button("🫆 Detalles", key=f"btn_det_single_resto_{nom_s}_{termino_raw}", use_container_width=True):
                                                    mostrar_modal_detalles(res)
                                            st.divider()
                            else:
                                # MOSTRAR ÚNICAMENTE LA NOTA SI NO HAY PAQUETES
                                st.info(
                                    f"💡 **Nota:** *\"{termino_raw.title()}\"* es una prueba individual (Single) que no forma parte de ningún paquete. "
                                    f"Puedes consultarla y cotizarla directamente en la pestaña **⚗️ Buscador de Pruebas Individuales / Singles**."
                                )
                    else:
                        st.error(f"❌ No se encontraron coincidencias para: \"{termino_raw}\"")

            tab_index += 1
# -------------------------------------------------------------
# PESTAÑA 2: BUSCADOR DE PAQUETE MÁSTER (TEXTO Y PRECIO CORREGIDOS)
# -------------------------------------------------------------
with tab_modo_2:
    st.write(
        "Selecciona 2 o más paquetes de la lista para verificar si existe un **Paquete Máster** más completo o si conviene armar una combinación con estudios faltantes."
    )

    lista_nombres_paquetes = sorted(list(TODOS_LOS_PAQUETES.keys()))

    paquetes_seleccionados = st.multiselect(
        "📦 Selecciona los paquetes a combinar:",
        options=lista_nombres_paquetes,
        placeholder="Ej. Selecciona Perfil Hepático, Check-up 44...",
        key="select_paquetes_master",
    )

    if len(paquetes_seleccionados) >= 2:
        resultado_master = CATALOGO.candidatos_master(paquetes_seleccionados)
        suma_precios_individuales = resultado_master["suma_precios"]
        candidatos_master = resultado_master["candidatos"]

        st.info(
            f"💡 **Resumen de la combinación:** Los {len(paquetes_seleccionados)} paquetes seleccionados reúnen un total de **{resultado_master['total_analitos']} analitos requeridos**. (Suma vendiendo por separado: **${suma_precios_individuales:,.2f} MXN**)."
        )

        coincidencias_100 = [c for c in candidatos_master if c["pct"] >= 99.0]

        st.markdown("---")
        st.markdown(
            "<h3 class='titulo-azul'>📊 Análisis de Estrategia y Combinaciones Sugeridas</h3>",
            unsafe_allow_html=True,
        )

        if candidatos_master:
            top_cand = candidatos_master[0]
            pkg_top = top_cand["paquete"]
            costo_top_base = pkg_top.get("precio", 0.0)
            costo_combo = top_cand["costo_combo_total"]
            ahorro_combo = suma_precios_individuales - costo_combo

            # 1. Definir texto de faltantes antes de usarlo en el banner
            if top_cand['costo_faltantes'] > 0:
                texto_faltantes = f"junto con los **{top_cand['faltantes_count']} analitos faltantes** (~${top_cand['costo_faltantes']:,.2f} MXN)."
            else:
                texto_faltantes = "que cubre el **100% de los analitos requeridos** directamente."

            # 2. Imprimir recomendación estratégica con formato limpio
            if ahorro_combo > 0:
                st.success(
                    f"✨ **ESTRATEGIA MÁS ECONÓMICA RECOMENDADA:**\n\n"
                    f"Conviene ofrecer el paquete **{pkg_top.get('nombre')}** (${costo_top_base:,.2f} MXN) {texto_faltantes}\n\n"
                    f"🪄 **Total Combo Sugerido:** **${costo_combo:,.2f} MXN** — 💰 **¡El paciente se ahorra ${ahorro_combo:,.2f} MXN!**"
                )
            else:
                st.warning(
                    f"🏷️ **RECOMENDACIÓN DE PRECIO:**\n\n"
                    f"El paquete Máster / Combo más cercano ({pkg_top.get('nombre')}) tiene un costo de **${costo_combo:,.2f} MXN**.\n\n"
                    f"🪄 **Conviene más cotizar los paquetes seleccionados por separado por ${suma_precios_individuales:,.2f} MXN.**"
                )

            st.divider()

            if coincidencias_100:
                st.success(
                    f"🏆 **Se encontraron {len(coincidencias_100)} paquete(s) Máster con coincidencia total (100%):**"
                )
                for idx, item_m in enumerate(coincidencias_100):
                    pkg = item_m["paquete"]
                    precio_m = pkg.get("precio", 0.0)
                    ahorro = suma_precios_individuales - precio_m

                    st.markdown(
                        f"<h4 class='titulo-azul'>🌟 {pkg.get('nombre')} — 💰 ${precio_m:,.2f} MXN</h4>",
                        unsafe_allow_html=True,
                    )
                    if ahorro > 0:
                        st.write(
                            f"💰 **¡Conviene este Paquete Máster!** Te ahorras **${ahorro:,.2f} MXN** comparado con vender los paquetes por separado."
                        )
                    else:
                        st.write(
                            f"🪄 *Suma por separado: ${suma_precios_individuales:,.2f} MXN vs Paquete Máster: ${precio_m:,.2f} MXN (Sale más barato cotizar por separado).* "
                        )

                    renderizar_tarjeta_paquete(pkg, "master_100", idx, es_expandido=(idx == 0))

                st.markdown("### 🥈 Otras Opciones Cercanas Evaluadas")
                resto_cand = [c for c in candidatos_master if c["pct"] < 99.0]
                for idx, item_m in enumerate(resto_cand[:5]):
                    pkg = item_m["paquete"]
                    pct_fmt = f"{item_m['pct']:.0f}%"

                    st.markdown(
                        f"**{pkg.get('nombre')}** — Coincidencia del **{pct_fmt}** ({item_m['cubiertos_count']} de {item_m['total_requerido']} analitos)"
                    )

                    if item_m["faltantes_nombres"]:
                        faltantes_str = ", ".join(item_m["faltantes_nombres"])
                        st.caption(
                            f"⚠️ **Faltantes ({item_m['faltantes_count']}):** {faltantes_str} *(Costo de faltantes: ~${item_m['costo_faltantes']:,.2f} MXN)*"
                        )

                    renderizar_tarjeta_paquete(
                        pkg, "master_parcial", idx, es_expandido=False
                    )
            else:
                col_btn_combo, _ = st.columns([2, 1])
                with col_btn_combo:
                    if st.button(
                        f"🛒 Agregar Combo Sugerido ({pkg_top.get('nombre')} + Faltantes)",
                        type="primary",
                        use_container_width=True,
                        key="btn_add_combo_master",
                    ):
                        agregar_al_carrito(pkg_top)
                        for f_nom, f_obj, p_f in top_cand["items_faltantes_detalle"]:
                            if f_obj:
                                if f_obj.get("tipo") in ["single", "individual"]:
                                    agregar_al_carrito(f_obj)
                                elif f_obj.get("paquetes"):
                                    agregar_al_carrito(f_obj["paquetes"][0])
                        st.rerun()

                st.markdown("### 🥈 Opciones Cercanas Evaluadas")

                for idx, item_m in enumerate(candidatos_master[:5]):
                    pkg = item_m["paquete"]
                    pct_fmt = f"{item_m['pct']:.0f}%"

                    st.markdown(
                        f"**{pkg.get('nombre')}** — Coincidencia del **{pct_fmt}** ({item_m['cubiertos_count']} de {item_m['total_requerido']} analitos)"
                    )

                    if item_m["faltantes_nombres"]:
                        faltantes_str = ", ".join(item_m["faltantes_nombres"])
                        st.caption(
                            f"⚠️ **Faltantes ({item_m['faltantes_count']}):** {faltantes_str} *(Costo de faltantes: ~${item_m['costo_faltantes']:,.2f} MXN)*"
                        )

                    renderizar_tarjeta_paquete(
                        pkg, "master_parcial", idx, es_expandido=(idx == 0)
                    )

        else:
            st.warning(
                "⚠️ No se encontró ningún paquete máster cercano para esta combinación. Es mejor cotizar los paquetes por separado."
            )

    elif len(paquetes_seleccionados) == 1:
        st.info("Selecciona al menos **1 paquete más** para calcular las mejores estrategias.")

# -------------------------------------------------------------
# PESTAÑA 3: BUSCADOR DE PRUEBAS INDIVIDUALES / SINGLES (LIMITADO A TOP 3 + EXPANDER)
# -------------------------------------------------------------
with tab_modo_3:
    st.markdown("<h3 class='titulo-azul'>🧪 Buscador de Pruebas Individuales (Singles)</h3>", unsafe_allow_html=True)
    st.write("Consulta precios, muestras e indicaciones de todas las pruebas que se venden por pieza.")

    busqueda_ind_input = st.text_input(
        "🔎 Escribe la prueba individual o single que buscas (separadas por comas):",
        placeholder="Ej. Glucosa sérica, Curva de tolerancia, Antidoping...",
        key="input_busqueda_individual",
    )

    WORDS_GENERICAS = {
        "humana", "humano", "serica", "serico", "suero", "libre", "fraccion",
        "total", "totales", "prueba", "perfil", "cuantitativa", "cualitativa",
        "y", "de", "del", "la", "el", "los", "las", "en", "para", "con"
    }

    if busqueda_ind_input:
        terminos_ind = separar_terminos_respetando_parentesis(busqueda_ind_input)

        for t_ind in terminos_ind:
            hallados_ind = []
            t_norm_buscado = normalizar(t_ind)
            
            words_especificas = [
                w for w in t_norm_buscado.split() 
                if w not in WORDS_GENERICAS and len(w) > 1
            ]

            for item in datos:
                if item.get("tipo") in ["single", "individual"]:
                    nom_test = item.get("analito", item.get("nombre", ""))
                    nom_test_norm = normalizar(nom_test)
                    words_estudio = [w for w in nom_test_norm.split() if w not in STOP_WORDS]

                    # 1. Coincidencia exacta o frase contenida
                    if t_norm_buscado in nom_test_norm or nom_test_norm in t_norm_buscado:
                        hallados_ind.append((item, 100))  # Máxima prioridad
                    else:
                        # 2. Coincidencia por palabras clave
                        if words_especificas and any(w in words_estudio for w in words_especificas):
                            coincidencias_cnt = sum(1 for w in words_especificas if w in words_estudio)
                            hallados_ind.append((item, coincidencias_cnt))

            if hallados_ind:
                # ORDENAR PRIMERO POR RELEVANCIA Y LUEGO POR PRECIO
                hallados_ind_ordenados = sorted(
                    hallados_ind, 
                    key=lambda x: (-x[1], float(x[0].get("precio", 0.0)))
                )

                st.markdown(f"#### ✨ Resultados para: \"{t_ind.title()}\"")

                # SEPARAR EN TOP 3 Y RESTO DE RESULTADOS
                top_singles = hallados_ind_ordenados[:3]
                resto_singles = hallados_ind_ordenados[3:]

                # 1. Renderizar los primeros 3 resultados
                for idx, res_tuple in enumerate(top_singles):
                    res_i = res_tuple[0]
                    n_i = res_i.get("analito", res_i.get("nombre", "Prueba"))
                    p_i = res_i.get("precio", 0.0)

                    with st.expander(f"🧪 **{n_i}** — 💰 **${p_i:,.2f} MXN**", expanded=True):
                        col_info, col_add, col_det = st.columns([2.5, 1, 1])

                        with col_info:
                            st.markdown(f"💉 **Tipo de muestra:** {res_i.get('tipo_muestra', 'N/A')}")
                            st.markdown(f"📜 **Indicaciones:** {res_i.get('indicaciones', 'N/A')}")
                            st.markdown(f"⏳ **Tiempo de entrega:** {res_i.get('tiempo_entrega', 'N/A')}")

                        with col_add:
                            if st.button("➕ Agregar", key=f"btn_add_p3_{n_i}_{t_ind}_{idx}", use_container_width=True):
                                agregar_al_carrito(res_i)
                                st.rerun()

                        with col_det:
                            if st.button("🫆 Detalles", key=f"btn_det_p3_{n_i}_{t_ind}_{idx}", use_container_width=True):
                                mostrar_modal_detalles(res_i)

                # 2. Renderizar el resto dentro de un expander si hay más de 3
                if resto_singles:
                    with st.expander(f"✨ **Ver {len(resto_singles)} resultados individuales más relacionados...**"):
                        for idx, res_tuple in enumerate(resto_singles):
                            res_i = res_tuple[0]
                            n_i = res_i.get("analito", res_i.get("nombre", "Prueba"))
                            p_i = res_i.get("precio", 0.0)

                            st.markdown(f"**{n_i}** — 💰 **${p_i:,.2f} MXN**")
                            col_info, col_add, col_det = st.columns([2.5, 1, 1])

                            with col_info:
                                st.markdown(f"💉 **Tipo de muestra:** {res_i.get('tipo_muestra', 'N/A')}")
                                st.markdown(f"📜 **Indicaciones:** {res_i.get('indicaciones', 'N/A')}")
                                st.markdown(f"⏳ **Tiempo de entrega:** {res_i.get('tiempo_entrega', 'N/A')}")

                            with col_add:
                                if st.button("➕ Agregar", key=f"btn_add_resto_{n_i}_{t_ind}_{idx}", use_container_width=True):
                                    agregar_al_carrito(res_i)
                                    st.rerun()

                            with col_det:
                                if st.button("🫆 Detalles", key=f"btn_det_resto_{n_i}_{t_ind}_{idx}", use_container_width=True):
                                    mostrar_modal_detalles(res_i)
                            st.divider()

            else:
                st.warning(f"⚠️ No se encontró la prueba \"{t_ind}\" en la lista de Pruebas Individuales / Singles.")
