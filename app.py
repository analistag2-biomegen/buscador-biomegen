from datetime import datetime
from difflib import SequenceMatcher
import io
import json
import os
import re
import unicodedata

from PIL import Image as PILImage
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

# -------------------------------------------------------------
# SISTEMA DE SEGURIDAD / CONTRASEÑA
# -------------------------------------------------------------
CONTRASEÑA_CORRECTA = "Biomegen_P.Catalogo"


def verificar_contraseña():
    if "autenticado" not in st.session_state:
        st.session_state.autenticado = False

    if not st.session_state.autenticado:
        st.markdown(
            "<h2 style='color: #094A73;'>🔒 Acceso Restringido - BIOMEGEN</h2>",
            unsafe_allow_html=True,
        )
        st.write("Por favor ingresa la contraseña corporativa para acceder al buscador:")

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

        st.stop()


verificar_contraseña()


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


def normalizar(texto):
    if not texto:
        return ""
    texto_str = str(texto).lower()
    nfkd = unicodedata.normalize("NFKD", texto_str)
    texto_sin_acentos = "".join([c for c in nfkd if not unicodedata.combining(c)])
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

    style_leyenda = ParagraphStyle(
        "LeyendaDH",
        parent=style_normal,
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#475569"),
    )

    story = []
    ahora = datetime.now().strftime("%d/%m/%Y")

    rutas_posibles_logo = ["LOGO BIOMEGEN SF.png", "LOGO BIOMEGEN.png", "LOGO BIOMEGEN_2.png"]
    ruta_logo_final = None
    for r in rutas_posibles_logo:
        if os.path.exists(r):
            ruta_logo_final = r
            break

    if ruta_logo_final:
        p_logo = PILImage.open(ruta_logo_final)
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

    for nombre, item in st.session_state.carrito.items():
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


# -------------------------------------------------------------
# SIDEBAR
# -------------------------------------------------------------
with st.sidebar:
    rutas_posibles_logo = ["LOGO BIOMEGEN SF.png", "LOGO BIOMEGEN.png", "LOGO BIOMEGEN_2.png"]
    ruta_logo_final = None
    for r in rutas_posibles_logo:
        if os.path.exists(r):
            ruta_logo_final = r
            break

    if ruta_logo_final:
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

        pdf_bytes = generar_pdf_binario(
            nombre_paciente_input,
            st.session_state.descuento_general_pct,
            vigencia_input,
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

@st.cache_data(ttl=1)
def cargar_datos():
    with open("datos.json", "r", encoding="utf-8") as f:
        return json.load(f)


datos = cargar_datos()

TODOS_LOS_PAQUETES = {}
DICCIONARIO_SINGLES = {}

for item in datos:
    tipo_item = item.get("tipo")
    if tipo_item == "paquete" or "paquetes" in item:
        for pkg in item.get("paquetes", []):
            if isinstance(pkg, dict):
                nom_p = pkg.get("nombre")
                if nom_p and nom_p not in TODOS_LOS_PAQUETES:
                    TODOS_LOS_PAQUETES[nom_p] = pkg
    elif tipo_item in ["single", "individual"]:
        nom_s = item.get("analito", item.get("nombre"))
        if nom_s:
            DICCIONARIO_SINGLES[normalizar(nom_s)] = item


def buscar_precio_estudio_o_single(nombre_analito):
    norm_a = normalizar(nombre_analito)
    if norm_a in DICCIONARIO_SINGLES:
        return DICCIONARIO_SINGLES[norm_a]
    for item in datos:
        if coincide_busqueda(nombre_analito, item.get("analito", "")):
            if item.get("tipo") in ["single", "individual"]:
                return item
            elif item.get("paquetes"):
                pkgs_ord = sorted(item["paquetes"], key=lambda x: x.get("precio", 0.0))
                if pkgs_ord:
                    return pkgs_ord[0]
    return None


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
        terminos_raw = [t.strip() for t in busqueda_input.split(",") if t.strip()]

        # Mapa de equivalencias para que entienda las abreviaturas de las Químicas
        MAPA_ALIAS_QS = {
            "qs3": ["qs3", "quimica sanguinea 3", "quimica sanguinea de 3"],
            "qs4": ["qs4", "quimica sanguinea 4", "quimica sanguinea de 4"],
            "qs5": ["qs5", "quimica sanguinea 5", "quimica sanguinea de 5"],
            "qs6": ["qs6", "quimica sanguinea 6", "quimica sanguinea de 6"],
            "qs12": ["qs12", "quimica sanguinea 12", "quimica sanguinea de 12"],
            "qs14": ["qs14", "quimica sanguinea 14", "quimica sanguinea de 14"],
            "qs19": ["qs19", "quimica sanguinea 19", "quimica sanguinea de 19"],
            "qs24": ["qs24", "quimica sanguinea 24", "quimica sanguinea de 24"],
            "qs27": ["qs27", "quimica sanguinea 27", "quimica sanguinea de 27"],
            "qs28": ["qs28", "quimica sanguinea 28", "quimica sanguinea de 28"],
            "qs30": ["qs30", "quimica sanguinea 30", "quimica sanguinea de 30"],
            "qs32": ["qs32", "quimica sanguinea 32", "quimica sanguinea de 32"],
            "qs36": ["qs36", "quimica sanguinea 36", "quimica sanguinea de 36"],
            "qs38": ["qs38", "quimica sanguinea 38", "quimica sanguinea de 38"],
            "qs44": ["qs44", "quimica sanguinea 44", "quimica sanguinea de 44"],
            "bh": ["bh", "biometria hematica"],
            "ego": ["ego", "examen general de orina"],
        }

        paquetes_coincidencias = []

        if len(terminos_raw) >= 2:
            for nombre_pkg, pkg_info in TODOS_LOS_PAQUETES.items():
                # Reunir todo el texto del paquete (Nombre + Analitos incluidos)
                texto_paquete_norm = normalizar(nombre_pkg + " " + " ".join(pkg_info.get("analitos_incluidos", [])))

                terminos_encontrados = set()
                for t_raw in terminos_raw:
                    t_norm = normalizar(t_raw)
                    
                    # 1. Verificar si el término directo o sus variantes alias están en el paquete
                    variantes = MAPA_ALIAS_QS.get(t_norm, [t_norm])
                    match_hallado = False
                    
                    for var in variantes:
                        if var in texto_paquete_norm or coincide_busqueda(var, texto_paquete_norm):
                            match_hallado = True
                            break

                    # 2. Si no matchó directo, verificar en la base de datos de analitos
                    if not match_hallado:
                        for item_d in datos:
                            if coincide_busqueda(t_raw, item_d.get("analito", "")):
                                for p_asoc in item_d.get("paquetes", []):
                                    if p_asoc.get("nombre") == nombre_pkg:
                                        match_hallado = True
                                        break

                    if match_hallado:
                        terminos_encontrados.add(t_raw)

                if len(terminos_encontrados) >= 1:
                    paquetes_coincidencias.append({
                        "datos_paquete": pkg_info,
                        "terminos_encontrados": terminos_encontrados,
                    })

            # Ordenar primero por la cantidad de coincidencias (de mayor a menor) y luego por menor precio
            paquetes_coincidencias.sort(
                key=lambda x: (-len(x["terminos_encontrados"]), x["datos_paquete"].get("precio", 0.0))
            )

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
                
                # 1. BÚSQUEDA DIRECTA COMO PAQUETE
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
                    # 2. BÚSQUEDA COMO ANALITO EN LA BASE DE DATOS
                    coincidencias = []
                    nombres_vistos = set()

                    for item in datos:
                        texto_busqueda = item.get("analito", "") + " " + item.get("categoria", "")
                        if coincide_busqueda(termino_raw, texto_busqueda):
                            clave_u = item.get("analito", "")
                            if clave_u and clave_u not in nombres_vistos:
                                nombres_vistos.add(clave_u)
                                coincidencias.append(item)

                    if coincidencias:
                        lista_singles = [res for res in coincidencias if res.get("tipo") in ["single", "individual"]]
                        lista_paquetes_analito = [res for res in coincidencias if res.get("tipo") not in ["single", "individual"] and res.get("paquetes")]

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

                        if lista_singles:
                            if lista_paquetes_analito:
                                st.markdown("---")
                            st.markdown("<h3 class='titulo-azul'>🏺 Estudios Individuales (Singles)</h3>", unsafe_allow_html=True)

                            singles_ordenados = sorted(lista_singles, key=lambda x: float(x.get("precio", 0.0)))

                            for res in singles_ordenados:
                                with st.expander(f"📦 **{res['analito']}** — 💰 **${res['precio']:,.2f} MXN**", expanded=False):
                                    col_info, col_add, col_det = st.columns([2.5, 1, 1])

                                    with col_info:
                                        st.markdown(f"🧪 **Tipo de muestra:** {res.get('tipo_muestra', 'N/A')}")
                                        st.markdown(f"📋 **Indicaciones:** {res.get('indicaciones', 'N/A')}")
                                        st.markdown(f"⏳ **Tiempo de entrega:** {res.get('tiempo_entrega', 'N/A')}")

                                    with col_add:
                                        if st.button("➕ Agregar", key=f"btn_add_single_{res['analito']}_{termino_raw}", use_container_width=True):
                                            agregar_al_carrito(res)
                                            st.rerun()

                                    with col_det:
                                        if st.button("🫆 Detalles", key=f"btn_det_single_{res['analito']}_{termino_raw}", use_container_width=True):
                                            mostrar_modal_detalles(res)

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
        analitos_totales_map = {}
        suma_precios_individuales = 0.0
        objetos_seleccionados = []

        for p_nom in paquetes_seleccionados:
            p_data = TODOS_LOS_PAQUETES[p_nom]
            objetos_seleccionados.append(p_data)
            suma_precios_individuales += p_data.get("precio", 0.0)
            analitos_p = p_data.get("analitos_incluidos", [])

            if not analitos_p:
                for item_d in datos:
                    for pkg_d in item_d.get("paquetes", []):
                        if pkg_d.get("nombre") == p_nom:
                            analitos_p.append(item_d.get("analito"))

            for a in analitos_p:
                if a:
                    clave_norm = normalizar(a)
                    if clave_norm and clave_norm not in analitos_totales_map:
                        analitos_totales_map[clave_norm] = a

        analitos_totales_keys = set(analitos_totales_map.keys())

        if not analitos_totales_keys:
            for p_nom in paquetes_seleccionados:
                analitos_totales_map[normalizar(p_nom)] = p_nom
            analitos_totales_keys = set(analitos_totales_map.keys())

        st.info(
            f"💡 **Resumen de la combinación:** Los {len(paquetes_seleccionados)} paquetes seleccionados reúnen un total de **{len(analitos_totales_keys)} analitos requeridos**. (Suma vendiendo por separado: **${suma_precios_individuales:,.2f} MXN**)."
        )

        candidatos_master = []

        for p_nom, p_data in TODOS_LOS_PAQUETES.items():
            if p_nom in paquetes_seleccionados:
                continue

            analitos_cand = p_data.get("analitos_incluidos", [])
            if not analitos_cand:
                for item_d in datos:
                    for pkg_d in item_d.get("paquetes", []):
                        if pkg_d.get("nombre") == p_nom:
                            analitos_cand.append(item_d.get("analito"))

            analitos_candidate_keys = set([normalizar(a) for a in analitos_cand if a])

            if not analitos_candidate_keys:
                continue

            cubiertos_keys = analitos_totales_keys.intersection(analitos_candidate_keys)
            faltantes_keys = analitos_totales_keys - analitos_candidate_keys

            pct_coincidencia = (
                len(cubiertos_keys) / len(analitos_totales_keys)
            ) * 100.0

            if pct_coincidencia >= 35.0:
                faltantes_nombres = [
                    analitos_totales_map[k]
                    for k in faltantes_keys
                    if k in analitos_totales_map
                ]

                costo_faltantes = 0.0
                items_faltantes_encontrados = []
                for f_nom in faltantes_nombres:
                    item_f = buscar_precio_estudio_o_single(f_nom)
                    if item_f:
                        p_f = item_f.get("precio", 0.0)
                        if p_f == 0.0 and item_f.get("paquetes"):
                            p_f = item_f["paquetes"][0].get("precio", 0.0)
                        costo_faltantes += p_f
                        items_faltantes_encontrados.append((f_nom, item_f, p_f))
                    else:
                        items_faltantes_encontrados.append((f_nom, None, 0.0))

                candidatos_master.append({
                    "paquete": p_data,
                    "pct": pct_coincidencia,
                    "cubiertos_count": len(cubiertos_keys),
                    "total_requerido": len(analitos_totales_keys),
                    "faltantes_count": len(faltantes_keys),
                    "faltantes_nombres": sorted(faltantes_nombres),
                    "items_faltantes_detalle": items_faltantes_encontrados,
                    "costo_faltantes": costo_faltantes,
                    "costo_combo_total": p_data.get("precio", 0.0) + costo_faltantes,
                })

        candidatos_master.sort(key=lambda x: (-x["pct"], x["costo_combo_total"]))
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
# PESTAÑA 3: BUSCADOR DE PRUEBAS INDIVIDUALES / SINGLES (ORDENADO POR PRECIO)
# -------------------------------------------------------------
with tab_modo_3:
    st.markdown("<h3 class='titulo-azul'>🧪 Buscador de Pruebas Individuales (Singles)</h3>", unsafe_allow_html=True)
    st.write("Consulta precios, muestras e indicaciones de todas las pruebas que se venden por pieza.")

    busqueda_ind_input = st.text_input(
        "🔎 Escribe la prueba individual o single que buscas (separadas por comas):",
        placeholder="Ej. Glucosa sérica, Curva de tolerancia, Antidoping...",
        key="input_busqueda_individual",
    )

    if busqueda_ind_input:
        terminos_ind = [t.strip() for t in busqueda_ind_input.split(",") if t.strip()]

        for t_ind in terminos_ind:
            hallados_ind = []
            for item in datos:
                if item.get("tipo") in ["single", "individual"]:
                    nom_test = item.get("analito", item.get("nombre", ""))
                    if coincide_busqueda(t_ind, nom_test):
                        hallados_ind.append(item)

            if hallados_ind:
                # ORDENAR DE MENOR A MAYOR PRECIO
                hallados_ind_ordenados = sorted(hallados_ind, key=lambda x: float(x.get("precio", 0.0)))

                st.markdown(f"#### ✨ Resultados para: \"{t_ind.title()}\"")
                for res_i in hallados_ind_ordenados:
                    n_i = res_i.get("analito", res_i.get("nombre", "Prueba"))
                    p_i = res_i.get("precio", 0.0)

                    with st.expander(f"🧪 **{n_i}** — 💰 **${p_i:,.2f} MXN**", expanded=True):
                        col_info, col_add, col_det = st.columns([2.5, 1, 1])

                        with col_info:
                            st.markdown(f"💉 **Tipo de muestra:** {res_i.get('tipo_muestra', 'N/A')}")
                            st.markdown(f"📜 **Indicaciones:** {res_i.get('indicaciones', 'N/A')}")
                            st.markdown(f"⏳ **Tiempo de entrega:** {res_i.get('tiempo_entrega', 'N/A')}")

                        with col_add:
                            if st.button("➕ Agregar", key=f"btn_add_p3_{n_i}_{t_ind}", use_container_width=True):
                                agregar_al_carrito(res_i)
                                st.rerun()

                        with col_det:
                            if st.button("🫆 Detalles", key=f"btn_det_p3_{n_i}_{t_ind}", use_container_width=True):
                                mostrar_modal_detalles(res_i)
            else:
                st.warning(f"⚠️ No se encontró la prueba \"{t_ind}\" en la lista de Pruebas Individuales / Singles.")
