from datetime import datetime
import io
import json
import os
import re
import unicodedata
from difflib import SequenceMatcher

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Image,
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

# -------------------------------------------------------------
# SISTEMA DE SEGURIDAD / CONTRASEÑA
# -------------------------------------------------------------
CONTRASEÑA_CORRECTA = "Biomegen_P.Catalogo"  # 👈 ¡AQUÍ PUEDES CAMBIAR TU CONTRASEÑA!


def verificar_contraseña():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False

    if not st.session_state.autenticado:
        st.markdown(
            "<h2 style='color: #094A73;'>🔒 Acceso Restringido - BIOMEGEN</h2>",
            unsafe_allow_html=True,
        )
        st.write("Por favor ingresa la contraseña para acceder al buscador:")

        input_password = st.text_input(
            "Contraseña:", type="password", key="login_pass"
        )

        if st.button("Ingresar", type="primary"):
            if input_password == CONTRASEÑA_CORRECTA:
                st.session_state.autenticado = True
                st.success("¡Acceso concedido!")
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta. Inténtalo de nuevo.")

        st.stop()  # Detiene la ejecución para que no se cargue nada de la app si no ponen la clave


# Ejecutar la verificación antes de cargar el resto de la app
verificar_contraseña()

def quitar_fondo_blanco(ruta_imagen):
    """Abre la imagen y convierte de forma agresiva cualquier tono claro de fondo en 100% transparente."""
    img = PILImage.open(ruta_imagen).convert("RGBA")
    datas = img.getdata()

    newData = []
    for item in datas:
        r, g, b, a = item
        # Si el píxel es claro (no es una letra o icono oscuro del logo), hacerlo transparente
        if r > 170 and g > 170 and b > 170:
            newData.append((255, 255, 255, 0))
        else:
            newData.append((r, g, b, a))

    img.putdata(newData)
    return img

# -------------------------------------------------------------
# ESTILOS CSS PERSONALIZADOS (ÚNICAMENTE SIDEBAR EN #8CA7B8)
# -------------------------------------------------------------
st.markdown(
    """
    <style>
/* Fondo principal de la app */
.stApp {
    background-color: #ffffff !important;
}

/* Barra Lateral (Sidebar) en #8CA7B8 */
[data-testid="stSidebar"] {
    background-color: #8CA7B8 !important;
    color: #042234 !important;
}

[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, 
[data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] span {
    color: #042234 !important;
}

/* Quitar marquito o fondo blanco de imágenes en Sidebar */
    [data-testid="stSidebar"] [data-testid="stImage"] img {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
}

/* Inputs dentro del Sidebar */
[data-testid="stSidebar"] input {
    background-color: #ffffff !important;
    color: #042234 !important;
    border: none !important;
    border-radius: 6px !important;
}

/* Input de Búsqueda Principal */
div[data-baseweb="input"] > div {
    background-color: #7D888C !important;
    border-radius: 8px !important;
    color: #ffffff !important;
}

div[data-baseweb="input"] input {
    color: #ffffff !important;
}

/* Pestañas (Tabs) */
button[data-baseweb="tab"] {
    font-weight: bold !important;
    color: #094A73 !important;
}

button[aria-selected="true"] {
    border-bottom-color: #de6519 !important;
    color: #de6519 !important;
}

/* Tarjetas Acordeón (Expanders) */
.stExpander {
    border: 1.5px solid #094A73 !important;
    border-radius: 8px !important;
    background-color: #ffffff !important;
    margin-bottom: 12px !important;
    overflow: hidden !important;
}

.stExpander summary {
    background-color: #658DA6 !important;
    color: #ffffff !important;
    border-radius: 6px 6px 0px 0px !important;
    font-weight: bold !important;
}

.stExpander summary p, .stExpander summary span, .stExpander summary div {
    color: #ffffff !important;
}

/* Botones generales de las tarjetas (Agregar / Detalles) */
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

/* BOTÓN NARANJA 'Descargar Presupuesto PDF' (Primary en Sidebar) */
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

    [data-testid="stSidebar"] button[kind="primary"] p,
    [data-testid="stSidebar"] [data-testid="stBaseButton-primary"] p,
    [data-testid="stSidebar"] div.stDownloadButton button p,
    [data-testid="stSidebar"] button[kind="primary"] span,
    [data-testid="stSidebar"] [data-testid="stBaseButton-primary"] span,
    [data-testid="stSidebar"] div.stDownloadButton button span {
        color: #ffffff !important;
    }
    
    [data-testid="stSidebar"] button[kind="primary"]:hover,
    [data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:hover,
    [data-testid="stSidebar"] div.stDownloadButton button:hover {
        background-color: #c45412 !important;
        color: #ffffff !important;
    }

    /* BOTÓN BLANCO 'Vaciar Cotización' (Secondary en Sidebar) */
    [data-testid="stSidebar"] button[kind="secondary"],
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
        background-color: #ffffff !important;
        color: #de6519 !important;
        border: 1px solid #cccccc !important;
        border-radius: 6px !important;
        font-weight: bold !important;
    }

    [data-testid="stSidebar"] button[kind="secondary"] p,
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] p,
    [data-testid="stSidebar"] button[kind="secondary"] span,
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] span {
        color: #de6519 !important;
    }

/* ALERTA VERDE (Sugerencia Crossmatch) */
div[data-testid="stNotificationContentSuccess"], 
div.stAlert:has(div[data-testid="stNotificationContentSuccess"]) {
    background-color: #C2E0C6 !important;
    color: #1e4620 !important;
    border-radius: 8px !important;
    border: none !important;
}

/* ALERTA ROJITA DE NO COINCIDENCIAS (Para st.warning y st.error) */
div[data-testid="stNotificationContentWarning"],
div[data-testid="stNotificationContentError"],
div.stAlert:has(div[data-testid="stNotificationContentWarning"]),
div.stAlert:has(div[data-testid="stNotificationContentError"]) {
    background-color: #F8B1A8 !important;
    color: #5c1812 !important;
    border-radius: 8px !important;
    border: none !important;
}

div[data-testid="stNotificationContentWarning"] p,
div[data-testid="stNotificationContentError"] p,
div[data-testid="stNotificationContentWarning"] span,
div[data-testid="stNotificationContentError"] span,
div[data-testid="stNotificationContentWarning"] div,
div[data-testid="stNotificationContentError"] div {
    color: #5c1812 !important;
    font-weight: bold !important;
}

/* Estilos de títulos en Azul Corporativo */
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
}

STOP_WORDS = {
    "de",
    "del",
    "la",
    "el",
    "los",
    "las",
    "en",
    "para",
    "con",
    "sin",
    "un",
    "una",
    "y",
}


def normalizar(texto):
    if not texto:
        return ""
    texto_str = str(texto).lower()
    nfkd = unicodedata.normalize("NFKD", texto_str)
    texto_sin_acentos = "".join(
        [c for c in nfkd if not unicodedata.combining(c)]
    )
    texto_limpio = texto_sin_acentos.replace("-", " ")
    return re.sub(r"[^\w\s]", " ", texto_limpio).strip()


def normalizar_sin_espacios(texto):
    return normalizar(texto).replace(" ", "")


def obtener_palabras_clave(texto):
    norm = normalizar(texto)
    palabras = norm.split()
    return [p for p in palabras if p not in STOP_WORDS and len(p) > 1]


def coincide_busqueda(termino_buscado, texto_objetivo):
    t_clean = normalizar_sin_espacios(termino_buscado)
    obj_clean = normalizar_sin_espacios(texto_objetivo)

    if not t_clean or not obj_clean:
        return False

    if t_clean in obj_clean or obj_clean in t_clean:
        return True

    t_norm = normalizar(termino_buscado)
    t_expandido = SINONIMOS_ABREVIATURAS.get(t_norm, t_norm)
    if normalizar_sin_espacios(t_expandido) in obj_clean:
        return True

    tokens_buscados = obtener_palabras_clave(t_expandido)
    tokens_objetivo = set(obtener_palabras_clave(texto_objetivo))

    if tokens_buscados:
        coincidencias = sum(
            1
            for tok in tokens_buscados
            if tok in tokens_objetivo
            or any(tok in obj_tok for obj_tok in tokens_objetivo)
        )
        if coincidencias / len(tokens_buscados) >= 0.7:
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


def generar_pdf_binario(nombre_paciente, desc_general_pct, vigencia_texto):
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

    story = []
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")

    # Búsqueda flexible de la imagen del logo en la carpeta
    rutas_posibles_logo = ["LOGO BIOMEGEN.png", "LOGO BIOMEGEN_2.png"]
    ruta_logo_final = None
    for r in rutas_posibles_logo:
        if os.path.exists(r):
            ruta_logo_final = r
            break

    if ruta_logo_final:
        p_logo = Image(ruta_logo_final, width=180, height=45)
    else:
        p_logo = Paragraph(
            "<b>BIOMEGEN</b><br/><font size=8 color='#0284c7'>LAB GENÓMICO</font>",
            style_cell_bold,
        )

    p_addr = Paragraph(
        "HOSPITAL SAN JOSÉ, PROLONGACIÓN CONSTITUYENTES NO. EXT. 302 NO. INT. TORRE 3, PISO 17 COL. EL JACAL,<br/>QUERÉTARO, QUERÉTARO",
        style_header_right,
    )
    t_header = Table([[p_logo, p_addr]], colWidths=[200, 340])
    t_header.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(t_header)
    story.append(Spacer(1, 10))

    subtotal_bruto = 0.0
    desc_items_acumulado = 0.0

    for nombre, item in st.session_state.carrito.items():
        precio_u = item["datos"].get("precio", 0.0)
        cant = item["cantidad"]
        pct_d = item.get("descuento_pct", 0)

        base_item = precio_u * cant
        monto_d_item = base_item * (pct_d / 100.0)

        subtotal_bruto += base_item
        desc_items_acumulado += monto_d_item

    subtotal_despues_items = subtotal_bruto - desc_items_acumulado
    monto_desc_general = subtotal_despues_items * (desc_general_pct / 100.0)
    descuento_total_acumulado = desc_items_acumulado + monto_desc_general
    total_final = subtotal_bruto - descuento_total_acumulado

    has_discount = descuento_total_acumulado > 0
    desc_label = "Con Descuento" if has_discount else "Sin Descuento"
    paciente_texto = (
        nombre_paciente.strip()
        if nombre_paciente.strip()
        else "Paciente General"
    )
    vigencia_val = (
        vigencia_texto.strip()
        if vigencia_texto.strip()
        else "30 días hábiles"
    )

    p_meta_left = Paragraph(
        f"<b>Atención a:</b> {paciente_texto}<br/><b>Médico:</b> A quien corresponda",
        style_cell,
    )
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

    table_data = [[
        Paragraph("<b>ESTUDIO</b>", style_cell_bold),
        Paragraph("<b>TOTAL</b>", style_cell_right),
        Paragraph("<b>TIEMPO ENTREGA</b>", style_banner),
    ]]

    indicaciones_paciente = []
    factor_desc_general = 1.0 - (desc_general_pct / 100.0)

    for nombre, item in st.session_state.carrito.items():
        precio_u = item["datos"].get("precio", 0.0)
        cant = item["cantidad"]
        pct_d = item.get("descuento_pct", 0)

        base_item = precio_u * cant
        precio_con_desc_item = (
            base_item * (1.0 - (pct_d / 100.0))
        ) * factor_desc_general

        tiempo = item["datos"].get("tiempo_entrega", "Mismo día")
        indicacion = item["datos"].get(
            "indicaciones", "Sin indicaciones especiales."
        )

        nombre_fmt = nombre.upper()
        if cant > 1:
            nombre_fmt += f" (x{cant})"
        if pct_d > 0:
            nombre_fmt += f" [-{pct_d}% desc.]"

        table_data.append([
            Paragraph(nombre_fmt, style_cell),
            Paragraph(f"${precio_con_desc_item:,.2f}", style_cell_right),
            Paragraph(tiempo, style_cell),
        ])

        indicaciones_paciente.append((nombre_fmt, indicacion))

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

    totales_data = [
        [
            Paragraph("Subtotal:", style_cell_right),
            Paragraph(f"${subtotal_bruto:,.2f}", style_cell_right),
        ],
        [
            Paragraph("Descuento:", style_cell_right),
            Paragraph(
                f"${descuento_total_acumulado:,.2f}", style_cell_right
            ),
        ],
        [
            Paragraph("<b>Total:</b>", style_cell_right),
            Paragraph(
                f"<b>${total_final:,.2f} MXN</b>", style_cell_right
            ),
        ],
    ]
    t_totales = Table(totales_data, colWidths=[100, 120])
    t_totales.setStyle(
        TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("PADDING", (0, 0), (-1, -1), 3),
        ])
    )

    t_totales_wrapper = Table([["", t_totales]], colWidths=[320, 220])
    t_totales_wrapper.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    story.append(t_totales_wrapper)
    story.append(Spacer(1, 10))

    story.append(Paragraph("INDICACIONES PARA EL PACIENTE", style_banner))
    story.append(Spacer(1, 4))

    ind_data = [[
        Paragraph("<b>NOMBRE COMPLETO</b>", style_cell_bold),
        Paragraph("<b>INDICACIONES</b>", style_cell_bold),
    ]]

    for est_nom, est_ind in indicaciones_paciente:
        ind_data.append([
            Paragraph(est_nom, style_cell),
            Paragraph(est_ind, style_cell),
        ])

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
        st.toast(
            f"➕ Se añadió otro **{nombre}** (Total: {st.session_state.carrito[nombre]['cantidad']})",
            icon="🛒",
        )
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


# -------------------------------------------------------------
# SIDEBAR - CON LOGO DE BIOMEGEN Y COTIZACIÓN
# -------------------------------------------------------------
with st.sidebar:
    rutas_posibles_logo = [
        "LOGO BIOMEGEN SF.png",
        "LOGO BIOMEGEN.png",
        "LOGO BIOMEGEN_2.png",
    ]
    ruta_logo_final = None
    for r in rutas_posibles_logo:
        if os.path.exists(r):
            ruta_logo_final = r
            break

    if ruta_logo_final:
        # Convertimos la imagen a base64 para aplicarle el filtro 'multiply' en CSS directo al HTML
        import base64

        with open(ruta_logo_final, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()

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

            # Botones de cantidad
            col_minus, col_cant, col_plus, col_del = st.columns(
                [0.8, 1.2, 0.8, 1]
            )
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
                st.write(
                    f"Subtotal: ~${precio_base:,.2f}~ **${subtotal_item:,.2f} MXN** *(-{desc_pct}%)*"
                )
            else:
                st.write(f"Subtotal: **${subtotal_item:,.2f} MXN**")

            st.divider()

        st.markdown("### 🏷️  Descuento General")
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
        monto_desc_general = subtotal_parcial * (
            st.session_state.descuento_general_pct / 100.0
        )
        total_descuentos = monto_desc_items_total + monto_desc_general
        total_final_cotizacion = subtotal_base_acumulado - total_descuentos

        st.divider()
        st.write(f"Subtotal Bruto: **${subtotal_base_acumulado:,.2f} MXN**")

        if total_descuentos > 0:
            st.write(f"Descuento Total: **-${total_descuentos:,.2f} MXN**")

        st.markdown(f"### 💵 Total: **${total_final_cotizacion:,.2f} MXN**")

        pdf_bytes = generar_pdf_binario(
            nombre_paciente_input,
            st.session_state.descuento_general_pct,
            vigencia_input,
        )
        st.download_button(
            label="📤 Descargar Presupuesto PDF",
            data=pdf_bytes,
            file_name=f"presupuesto_estudios_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary",
        )

        if st.button(
            "🧹 Vaciar Cotización", use_container_width=True, type="secondary"
        ):
            vaciar_carrito()
            st.rerun()
    else:
        st.info("La cotización está vacía. Agrega paquetes para cotizar.")


# -------------------------------------------------------------
# CONTENIDO PRINCIPAL
# -------------------------------------------------------------
st.title("🔬 Buscador de Analitos y Paquetes de Laboratorio")
st.write(
    "Ingresa uno o varios analitos o paquetes **separados por comas** (ej: *Glucosa, QS3, Antidoping*)."
)


@st.dialog("🫆 Detalles del Estudio")
def mostrar_modal_detalles(estudio):
    nombre = estudio.get("nombre", estudio.get("analito", "Estudio"))
    st.subheader(f"📦 {nombre}")
    st.markdown(f"**💰 Precio:** ${estudio.get('precio', 0):,.2f} MXN")
    st.markdown(
        f"**💉 Tipo de muestra:** {estudio.get('tipo_muestra', 'No especificada')}"
    )
    st.markdown(
        f"**⌛ Tiempo de entrega:** {estudio.get('tiempo_entrega', 'N/A')}"
    )

    st.divider()

    st.markdown("### 💡 Definición del Estudio")
    st.info(
        estudio.get(
            "definicion", "Sin definición disponible para este estudio."
        )
    )

    st.markdown("### 🧪 Lo que se analiza en este estudio:")
    analitos = estudio.get("analitos_incluidos", [nombre])
    if analitos:
        for a in analitos:
            st.markdown(f"- {a}")
    else:
        st.write("Lista de analitos no especificada.")

    st.divider()
    st.markdown(f"**📋 Indicaciones:** {estudio.get('indicaciones', 'N/A')}")

    if st.button(
        "➕ Agregar este estudio a la cotización",
        key=f"modal_add_{nombre}",
        use_container_width=True,
    ):
        agregar_al_carrito(estudio)
        st.rerun()


@st.cache_data(ttl=1)
def cargar_datos():
    with open("datos.json", "r", encoding="utf-8") as f:
        return json.load(f)


datos = cargar_datos()

busqueda_input = st.text_input(
    "🔎 Escribe aquí las pruebas o analitos (separados por comas):",
    placeholder="Ej. Glucosa, QS3, Antidoping...",
)


def renderizar_tarjeta_paquete(pkg, key_prefix, idx, es_expandido=False):
    nombre = pkg.get("nombre", "Paquete")
    precio = pkg.get("precio", 0)
    indicaciones = pkg.get("indicaciones", "Sin indicaciones.")
    tiempo = pkg.get("tiempo_entrega", "No especificado")
    muestra = pkg.get("tipo_muestra", "No especificada")

    with st.expander(
        f"📦 **{nombre}** — 💰 **${precio:,.2f} MXN**", expanded=es_expandido
    ):
        col_info, col_add, col_det = st.columns([2.5, 1, 1])

        with col_info:
            st.markdown(f"💉 **Tipo de muestra:** {muestra}")
            st.markdown(f"📋 **Indicaciones:** {indicaciones}")
            st.markdown(f"⌛ **Tiempo de entrega:** {tiempo}")

        with col_add:
            if st.button(
                "➕ Agregar",
                key=f"btn_add_{key_prefix}_{idx}_{nombre}",
                use_container_width=True,
            ):
                agregar_al_carrito(pkg)
                st.rerun()

        with col_det:
            if st.button(
                "🫆 Detalles",
                key=f"btn_det_{key_prefix}_{idx}_{nombre}",
                use_container_width=True,
            ):
                mostrar_modal_detalles(pkg)


if busqueda_input:
    terminos_raw = [t.strip() for t in busqueda_input.split(",") if t.strip()]
    paquetes_coincidencias = []
    terminos_cubiertos = set()

    # 1. LÓGICA CROSSMATCH
    if len(terminos_raw) > 1:
        todos_los_paquetes = {}
        for item in datos:
            if item.get("tipo") == "paquete" or "paquetes" in item:
                for pkg in item.get("paquetes", []):
                    if isinstance(pkg, dict):
                        nombre_pkg = pkg.get("nombre")
                        if nombre_pkg and nombre_pkg not in todos_los_paquetes:
                            todos_los_paquetes[nombre_pkg] = pkg

        for nombre_pkg, pkg_info in todos_los_paquetes.items():
            texto_paquete = (
                nombre_pkg
                + " "
                + " ".join(pkg_info.get("analitos_incluidos", []))
            )

            terminos_encontrados = set()
            for t_raw in terminos_raw:
                if coincide_busqueda(t_raw, texto_paquete):
                    terminos_encontrados.add(t_raw)

            if len(terminos_encontrados) >= 2:
                paquetes_coincidencias.append(
                    {
                        "datos_paquete": pkg_info,
                        "terminos_encontrados": terminos_encontrados,
                    }
                )

        paquetes_coincidencias.sort(
            key=lambda x: (
                -len(x["terminos_encontrados"]),
                x["datos_paquete"].get("precio", 0.0),
            )
        )

        if paquetes_coincidencias:
            terminos_cubiertos = paquetes_coincidencias[0][
                "terminos_encontrados"
            ]

    # PREPARAR LAS PESTAÑAS
    nombres_tabs = []
    if paquetes_coincidencias:
        nombres_tabs.append("🌟 Paquetes Integrales")

    for t in terminos_raw:
        nombres_tabs.append(f"🧪 {t.title()}")

    tabs_creadas = st.tabs(nombres_tabs)
    tab_index = 0

    # PESTAÑA CROSSMATCH
    if paquetes_coincidencias:
        with tabs_creadas[tab_index]:
            st.success(
                "🌟 **Paquetes integrales sugeridos que contienen varios de los analitos buscados:**"
            )

            top_cross = paquetes_coincidencias[:3]
            resto_cross = paquetes_coincidencias[3:]

            for idx, match in enumerate(top_cross):
                pkg = match["datos_paquete"]
                cant = len(match["terminos_encontrados"])
                total_b = len(terminos_raw)
                lista_enc = ", ".join(
                    [t.title() for t in match["terminos_encontrados"]]
                )

                st.markdown(
                    f"**{pkg.get('nombre')}** — *(Incluye {cant} de {total_b}: {lista_enc})*"
                )
                renderizar_tarjeta_paquete(
                    pkg, "top_cross", idx, es_expandido=(idx == 0)
                )

            if resto_cross:
                with st.expander(
                    f"✨ **Ver {len(resto_cross)} opciones integrales más...**"
                ):
                    for idx, match in enumerate(resto_cross):
                        pkg = match["datos_paquete"]
                        cant = len(match["terminos_encontrados"])
                        total_b = len(terminos_raw)
                        lista_enc = ", ".join(
                            [t.title() for t in match["terminos_encontrados"]]
                        )

                        st.markdown(
                            f"**{pkg.get('nombre')}** — *(Incluye {cant} de {total_b}: {lista_enc})*"
                        )
                        renderizar_tarjeta_paquete(
                            pkg, "resto_cross", idx, es_expandido=False
                        )

        tab_index += 1

    # PESTAÑAS INDIVIDUALES
    for termino_raw in terminos_raw:
        with tabs_creadas[tab_index]:
            paquetes_directos_hallados = []

            for item in datos:
                if item.get("tipo") == "paquete":
                    for pkg in item.get("paquetes", []):
                        if isinstance(
                            pkg, dict
                        ) and coincide_busqueda(
                            termino_raw, pkg.get("nombre", "")
                        ):
                            paquetes_directos_hallados.append(pkg)

            paquetes_directos_hallados = desduplicar_paquetes(
                paquetes_directos_hallados
            )

            # A. PAQUETE DIRECTO
            if paquetes_directos_hallados:
                st.subheader(
                    f"🧪 Opciones encontradas para: \"{termino_raw.title()}\""
                )
                paquetes_directos_ordenados = sorted(
                    paquetes_directos_hallados, key=obtener_precio_paquete
                )

                top_dir = paquetes_directos_ordenados[:3]
                resto_dir = paquetes_directos_ordenados[3:]

                for idx, pkg in enumerate(top_dir):
                    renderizar_tarjeta_paquete(
                        pkg,
                        f"top_dir_{termino_raw}",
                        idx,
                        es_expandido=(idx == 0),
                    )

                if resto_dir:
                    with st.expander(
                        f"✨ **Ver {len(resto_dir)} paquetes más relacionados con {termino_raw.title()}...**"
                    ):
                        for idx, pkg in enumerate(resto_dir):
                            renderizar_tarjeta_paquete(
                                pkg,
                                f"resto_dir_{termino_raw}",
                                idx,
                                es_expandido=False,
                            )

            # B. ANALITO GENERAL
            else:
                coincidencias = []
                nombres_vistos = set()

                for item in datos:
                    texto_busqueda = item["analito"] + " " + item.get(
                        "categoria", ""
                    )
                    if coincide_busqueda(termino_raw, texto_busqueda):
                        clave_u = item["analito"]
                        if clave_u not in nombres_vistos:
                            nombres_vistos.add(clave_u)
                            coincidencias.append(item)

                if coincidencias:
                    lista_singles = [
                        res for res in coincidencias if res.get("tipo") == "single"
                    ]
                    lista_paquetes_analito = [
                        res
                        for res in coincidencias
                        if res.get("tipo") != "single"
                    ]

                    # 1. MOSTRAR PAQUETES DE MENOR A MAYOR PRECIO
                    if lista_paquetes_analito:
                        for res in lista_paquetes_analito:
                            st.markdown(
                                f"📦 **Paquetes con {res['analito']}** — *({res['categoria']})*"
                            )

                            paquetes_asociados = desduplicar_paquetes(
                                res.get("paquetes", [])
                            )

                            paquetes_ordenados = sorted(
                                paquetes_asociados, key=obtener_precio_paquete
                            )

                            top_pkg = paquetes_ordenados[:3]
                            resto_pkg = paquetes_ordenados[3:]

                            for idx, pkg in enumerate(top_pkg):
                                renderizar_tarjeta_paquete(
                                    pkg,
                                    f"top_ind_{res['analito']}",
                                    idx,
                                    es_expandido=(idx == 0),
                                )

                            if resto_pkg:
                                with st.expander(
                                    f"✨ **Ver {len(resto_pkg)} paquetes más que incluyen {res['analito']}...**"
                                ):
                                    for idx, pkg in enumerate(resto_pkg):
                                        renderizar_tarjeta_paquete(
                                            pkg,
                                            f"resto_ind_{res['analito']}",
                                            idx,
                                            es_expandido=False,
                                        )

                    # 2. MOSTRAR SINGLES AL FINAL
                    if lista_singles:
                        st.markdown("---")
                        st.markdown("### ⚗️ Estudios Individuales (Singles)")

                        singles_ordenados = sorted(
                            lista_singles,
                            key=lambda x: float(x.get("precio", 0.0)),
                        )

                        for res in singles_ordenados:
                            with st.expander(
                                f"⚗️ **{res['analito']}** — 💰 **${res['precio']:,.2f} MXN**",
                                expanded=False,
                            ):
                                col_info, col_add, col_det = st.columns(
                                    [2.5, 1, 1]
                                )

                                with col_info:
                                    st.markdown(
                                        f"💉 **Tipo de muestra:** {res.get('tipo_muestra', 'N/A')}"
                                    )
                                    st.markdown(
                                        f"📋 **Indicaciones:** {res.get('indicaciones', 'N/A')}"
                                    )
                                    st.markdown(
                                        f"⌛ **Tiempo de entrega:** {res.get('tiempo_entrega', 'N/A')}"
                                    )

                                with col_add:
                                    if st.button(
                                        "➕ Agregar",
                                        key=f"btn_add_single_{res['analito']}",
                                        use_container_width=True,
                                    ):
                                        agregar_al_carrito(res)
                                        st.rerun()

                                with col_det:
                                    if st.button(
                                        "🫆 Detalles",
                                        key=f"btn_det_single_{res['analito']}",
                                        use_container_width=True,
                                    ):
                                        mostrar_modal_detalles(res)

                else:
                    st.warning(
                        f"❌ No se encontraron coincidencias para: **\"{termino_raw}\"**"
                    )

        tab_index += 1