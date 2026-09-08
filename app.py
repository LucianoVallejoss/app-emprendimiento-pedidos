import os
import sqlite3
import pandas as pd
import streamlit as st
from datetime import date
import urllib.parse
import re

# Obtiene la ruta exacta de la carpeta donde está este script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "pedidos.db")

# BLOQUE 1: CONFIGURACIÓN GENERAL DE LA PÁGINA
# Define el título de la pestaña del navegador, el ícono y el ancho completo.

st.set_page_config(page_title="Gestión de Pedidos", page_icon="🍩", layout="wide")


# ==============================================================================
# BLOQUE 2: BASE DE DATOS (SQLite)
# Crea automáticamente el archivo local 'pedidos.db' y las tablas si no existen.
# ==============================================================================
def get_db_connection():
    # check_same_thread=False permite que Streamlit acceda a SQLite en múltiples hilos
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Tabla para registrar cada pedido
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente TEXT NOT NULL,
                telefono TEXT NOT NULL,
                producto TEXT NOT NULL,
                cantidad INTEGER NOT NULL,
                total REAL NOT NULL,
                fecha_entrega DATE NOT NULL,
                tipo_entrega TEXT NOT NULL,
                estado_pago TEXT NOT NULL,
                estado_pedido TEXT NOT NULL
            )
        """)
        # Tabla para registrar compras de insumos/gastos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gastos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha DATE NOT NULL,
                descripcion TEXT NOT NULL,
                categoria TEXT NOT NULL,
                monto REAL NOT NULL
            )
        """)
        conn.commit()

# Inicializa las tablas al arrancar la app
init_db()


# ==============================================================================
# BLOQUE 3: GENERADOR DE ENLACES DE WHATSAPP (wa.me)
# Limpia el número telefónico y formatea los mensajes listos para enviar.
# ==============================================================================
def limpiar_telefono(tel_raw):
    # Elimina espacios, guiones y paréntesis
    limpio = re.sub(r"\D", "", str(tel_raw))
    # Asegura el prefijo de Argentina (549)
    if not limpio.startswith("54"):
        limpio = f"549{limpio}"
    return limpio

def url_confirmacion(cliente, tel, prod, cant, tot, entrega):
    tel_fmt = limpiar_telefono(tel)
    msg = (
        f"¡Hola {cliente}! 🍩✨\n\n"
        f"Confirmamos tu pedido:\n"
        f"• Producto: {prod} (x{cant})\n"
        f"• Fecha de entrega: {entrega.strftime('%d/%m/%Y') if hasattr(entrega, 'strftime') else entrega}\n"
        f"• Total: ${tot:,.2f}\n\n"
        f"¡Muchas gracias por tu compra!"
    )
    return f"https://wa.me/{tel_fmt}?text={urllib.parse.quote(msg)}"

def url_pedido_listo(cliente, tel, prod):
    tel_fmt = limpiar_telefono(tel)
    msg = (
        f"¡Hola {cliente}! 🍩✨\n\n"
        f"Tu pedido de *{prod}* ya está listo para ser retirado / enviado.\n\n"
        f"¡Que lo disfrutes!"
    )
    return f"https://wa.me/{tel_fmt}?text={urllib.parse.quote(msg)}"


# ==============================================================================
# BLOQUE 4: MENÚ LATERAL DE NAVEGACIÓN
# ==============================================================================
st.title("🍩 Control de Pedidos y Caja")
menu = ["📝 Nuevo Pedido", "📋 Ver Pedidos", "💸 Cargar Gasto", "📊 Balance"]
opcion = st.sidebar.radio("Menú Principal", menu)


# ==============================================================================
# BLOQUE 5: PANTALLAS DE LA APLICACIÓN
# ==============================================================================

# --- 1. CARGAR NUEVO PEDIDO ---
if opcion == "📝 Nuevo Pedido":
    st.subheader("Registrar Nuevo Pedido")
    with st.form("form_nuevo_pedido", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            cliente = st.text_input("Nombre del Cliente")
            telefono = st.text_input("WhatsApp (ej: 3794123456)")
            producto = st.selectbox("Producto", [
                "Pastafrola de Membrillo",
                "Pastafrola de Batata",
                "Donitas x docena",
                "Donitas x media docena",
                "Combo Especial"
            ])
            cantidad = st.number_input("Cantidad", min_value=1, value=1, step=1)
        
        with c2:
            total = st.number_input("Monto Total ($)", min_value=0.0, step=100.0)
            fecha_entrega = st.date_input("Fecha de Entrega", date.today())
            tipo_entrega = st.selectbox("Modalidad", ["Retiro en domicilio", "Envío a domicilio"])
            estado_pago = st.selectbox("Estado del Pago", ["Pendiente", "Seña Abonada", "Pagado Total"])
            estado_pedido = st.selectbox("Estado del Pedido", ["Pendiente", "En preparación", "Entregado"])

        enviar = st.form_submit_button("Guardar Pedido", use_container_width=True)

    # Si se envía el formulario y los datos son válidos, se inserta en SQLite
    if enviar:
        if cliente.strip() and telefono.strip() and total > 0:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO pedidos (cliente, telefono, producto, cantidad, total, fecha_entrega, tipo_entrega, estado_pago, estado_pedido)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (cliente, telefono, producto, cantidad, total, fecha_entrega, tipo_entrega, estado_pago, estado_pedido))
                conn.commit()
            
            st.success(f"¡Pedido de {cliente} guardado correctamente!")
            # Muestra el botón de WhatsApp directo con el mensaje listo
            link_ws = url_confirmacion(cliente, telefono, producto, cantidad, total, fecha_entrega)
            st.link_button("📲 Enviar Confirmación por WhatsApp", link_ws, use_container_width=True)
        else:
            st.error("Por favor completá nombre, teléfono y un monto válido.")


# --- 2. LISTA Y GESTIÓN DE PEDIDOS ---
elif opcion == "📋 Ver Pedidos":
    st.subheader("Lista de Pedidos")
    with get_db_connection() as conn:
        df_pedidos = pd.read_sql_query("SELECT * FROM pedidos ORDER BY fecha_entrega ASC", conn)

    if not df_pedidos.empty:
        # Filtro interactivo por estado
        filtro = st.multiselect("Filtrar por estado:", ["Pendiente", "En preparación", "Entregado", "Cancelado"], default=["Pendiente", "En preparación"])
        df_filtrado = df_pedidos[df_pedidos["estado_pedido"].isin(filtro)]
        st.dataframe(df_filtrado, use_container_width=True)

        st.markdown("---")
        st.subheader("⚙️ Gestionar Pedido Individual")
        
        # Selector de ID para modificar estados o avisar por WhatsApp
        id_sel = st.selectbox("Seleccionar ID del Pedido:", df_pedidos["id"].tolist())
        row = df_pedidos[df_pedidos["id"] == id_sel].iloc[0]

        st.info(f"**Cliente:** {row['cliente']} | **Producto:** {row['producto']} (x{row['cantidad']}) | **Fecha:** {row['fecha_entrega']} | **Modalidad:** {row['tipo_entrega']}")

        col_a, col_b = st.columns(2)
        with col_a:
            nuevo_pago = st.selectbox("Actualizar Pago:", ["Pendiente", "Seña Abonada", "Pagado Total"], index=["Pendiente", "Seña Abonada", "Pagado Total"].index(row["estado_pago"]))
        with col_b:
            nuevo_estado = st.selectbox("Actualizar Estado:", ["Pendiente", "En preparación", "Entregado", "Cancelado"], index=["Pendiente", "En preparación", "Entregado", "Cancelado"].index(row["estado_pedido"]))

        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if st.button("💾 Guardar Cambios", use_container_width=True):
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE pedidos SET estado_pago = ?, estado_pedido = ? WHERE id = ?", (nuevo_pago, nuevo_estado, id_sel))
                    conn.commit()
                st.success("Pedido actualizado.")
                st.rerun()
        
        with c_btn2:
            link_listo = url_pedido_listo(row["cliente"], row["telefono"], row["producto"])
            st.link_button("🔔 Avisar por WhatsApp: ¡Pedido Listo!", link_listo, use_container_width=True)
    else:
        st.info("No hay pedidos registrados.")


# --- 3. CARGA DE GASTOS / INSUMOS ---
elif opcion == "💸 Cargar Gasto":
    st.subheader("Registrar Compra o Gasto de Insumos")
    with st.form("form_gasto", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            desc = st.text_input("Descripción (ej. 5kg Harina 0000, 3kg Dulce de Membrillo, Cajas)")
            categoria = st.selectbox("Categoría", ["Materia Prima", "Packaging / Bolsas", "Servicios (Gas/Luz)", "Otros"])
        with c2:
            monto = st.number_input("Monto Gastado ($)", min_value=0.0, step=100.0)
            fecha_gasto = st.date_input("Fecha de Compra", date.today())

        guardar_gasto = st.form_submit_button("Guardar Gasto", use_container_width=True)

    if guardar_gasto:
        if desc.strip() and monto > 0:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO gastos (fecha, descripcion, categoria, monto) VALUES (?, ?, ?, ?)", (fecha_gasto, desc, categoria, monto))
                conn.commit()
            st.success("Gasto registrado correctamente.")
        else:
            st.error("Completá la descripción y el monto.")


# --- 4. BALANCE Y FINANZAS ---
elif opcion == "📊 Balance":
    st.subheader("Resumen Económico")
    with get_db_connection() as conn:
        df_pagados = pd.read_sql_query("SELECT * FROM pedidos WHERE estado_pago = 'Pagado Total'", conn)
        df_gastos = pd.read_sql_query("SELECT * FROM gastos", conn)

    ingresos = df_pagados["total"].sum() if not df_pagados.empty else 0.0
    egresos = df_gastos["monto"].sum() if not df_gastos.empty else 0.0
    ganancia = ingresos - egresos

    # Tarjetas métricas arriba
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Cobrado", f"${ingresos:,.2f}")
    m2.metric("Total Gastos", f"${egresos:,.2f}")
    m3.metric("Ganancia Neta", f"${ganancia:,.2f}")

    st.markdown("---")
    c_t1, c_t2 = st.columns(2)
    with c_t1:
        st.write("**Últimos Cobros Realizados:**")
        if not df_pagados.empty:
            st.dataframe(df_pagados[["fecha_entrega", "cliente", "producto", "total"]], use_container_width=True)
        else:
            st.caption("No hay cobros registrados.")
    with c_t2:
        st.write("**Historial de Gastos:**")
        if not df_gastos.empty:
            st.dataframe(df_gastos[["fecha", "descripcion", "categoria", "monto"]], use_container_width=True)
        else:
            st.caption("No hay gastos registrados.")