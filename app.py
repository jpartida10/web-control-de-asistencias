# app.py (REEMPLAZAR totalmente con este contenido)
# Proyecto: Control de Asistencias (integrado y completo)
# Requisitos: streamlit, sqlalchemy, psycopg2-binary, bcrypt, plotly, streamlit-option-menu, qrcode, pillow
# Ejemplo pip:
# pip install streamlit sqlalchemy psycopg2-binary bcrypt plotly streamlit-option-menu qrcode pillow

import streamlit as st
import pandas as pd
import sqlalchemy
from sqlalchemy import text
import datetime
import bcrypt
from streamlit_option_menu import option_menu
from io import BytesIO
import qrcode
import base64
import random
import string
import plotly.express as px

# =========================
# CONFIGURACIÓN DE PÁGINA
# =========================
st.set_page_config(page_title="Control de Asistencias", page_icon="📋", layout="wide")

# =========================
# CONFIG: Cambia si es necesario
# =========================
# Usa tu string de Neon/Postgres o local. Mantén sslmode si usas Neon.
DATABASE_URL = "postgresql://neondb_owner:npg_1f3sluIdFRyA@ep-solitary-meadow-adthlkqa-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
# BASE_URL debe apuntar a la URL pública del frontend (Streamlit) para que los QR generados funcionen al escanear
BASE_URL = "https://web-control-de-asistencias-6dfeqqhenqmcaisphdh4qu.streamlit.app/"

# =========================
# CONEXIÓN
# =========================
def get_engine():
    return sqlalchemy.create_engine(DATABASE_URL, pool_pre_ping=True)

def get_connection():
    engine = get_engine()
    return engine.connect()

# =========================
# UTILIDADES
# =========================
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def check_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def mostrar_df_download(df: pd.DataFrame, filename: str, label: str = "Descargar CSV"):
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(label, data=csv, file_name=filename, mime='text/csv')

def generar_token(longitud=24):
    letras = string.ascii_letters + string.digits
    return ''.join(random.choice(letras) for _ in range(longitud))

def generar_qr_image_data(url: str):
    qr_img = qrcode.make(url)
    buffer = BytesIO()
    qr_img.save(buffer, format="PNG")
    buffer.seek(0)
    img_bytes = buffer.getvalue()
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    return b64

# Horarios permitidos
HORARIOS = [
    "07:00 - 07:50",
    "07:50 - 08:40",
    "09:20 - 10:10",
    "10:10 - 11:00",
    "11:00 - 11:50",
    "11:50 - 12:40",
    "12:40 - 13:30",
    "13:30 - 14:20",
    "14:20 - 15:10"
]

# =========================
# CREAR TABLAS / MIGRACIONES
# =========================
def crear_tablas():
    conn = get_connection()
    try:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS usuarios (
            usuarioid SERIAL PRIMARY KEY,
            nombreusuario VARCHAR(80) UNIQUE NOT NULL,
            contrasena TEXT NOT NULL,
            rol VARCHAR(20),
            maestroid INT,
            matricula INT
        );
        CREATE TABLE IF NOT EXISTS alumnos (
            matricula SERIAL PRIMARY KEY,
            nombre VARCHAR(80),
            apellido VARCHAR(80)
        );
        CREATE TABLE IF NOT EXISTS maestros (
            maestroid SERIAL PRIMARY KEY,
            nombre VARCHAR(80),
            apellido VARCHAR(80)
        );
        CREATE TABLE IF NOT EXISTS materias (
            materiaid SERIAL PRIMARY KEY,
            nombre VARCHAR(120),
            descripcion TEXT,
            maestroid INT,
            horario VARCHAR(50)
        );
        CREATE TABLE IF NOT EXISTS clase_alumnos (
            id SERIAL PRIMARY KEY,
            materiaid INT NOT NULL,
            matricula INT NOT NULL,
            UNIQUE (materiaid, matricula)
        );
        CREATE TABLE IF NOT EXISTS asistencias (
            asistenciaid SERIAL PRIMARY KEY,
            matricula INT,
            maestroid INT,
            materiaid INT,
            fecha DATE,
            estado VARCHAR(20)
        );
        CREATE TABLE IF NOT EXISTS qr_tokens (
            id SERIAL PRIMARY KEY,
            token VARCHAR(80) UNIQUE NOT NULL,
            materiaid INT,
            maestroid INT,
            fecha_creacion TIMESTAMP DEFAULT NOW(),
            expiracion TIMESTAMP,
            activo BOOLEAN DEFAULT TRUE,
            single_use BOOLEAN DEFAULT FALSE
        );
        """))
        # columnas idempotentes (por si el script se ejecuta más de una vez)
        conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS maestroid INT;"))
        conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS matricula INT;"))
        conn.execute(text("ALTER TABLE materias ADD COLUMN IF NOT EXISTS maestroid INT;"))
        conn.execute(text("ALTER TABLE materias ADD COLUMN IF NOT EXISTS horario VARCHAR(50);"))
        conn.execute(text("ALTER TABLE asistencias ADD COLUMN IF NOT EXISTS maestroid INT;"))
        conn.execute(text("ALTER TABLE asistencias ADD COLUMN IF NOT EXISTS materiaid INT;"))
        conn.execute(text("ALTER TABLE qr_tokens ADD COLUMN IF NOT EXISTS single_use BOOLEAN DEFAULT FALSE;"))
        conn.commit()
    finally:
        conn.close()

# Inicializar tablas
try:
    crear_tablas()
except Exception as e:
    st.error(f"Error inicializando la base de datos: {e}")

# =========================
# SESIÓN
# =========================
if "usuario" not in st.session_state:
    st.session_state.usuario = None

# =========================
# MODO QR: si llega ?qr_token=...
# =========================
params = st.experimental_get_query_params()
if "qr_token" in params:
    token = params["qr_token"][0]
    conn = get_connection()
    try:
        qr = conn.execute(text("SELECT * FROM qr_tokens WHERE token = :t AND activo = TRUE"), {"t": token}).mappings().fetchone()
        if not qr:
            st.error("QR inválido o ya utilizado / inactivo.")
            conn.close()
            st.stop()
        # verificar expiración (usar UTC)
        ahora = datetime.datetime.utcnow()
        expir = qr["expiracion"]
        if expir is not None and expir <= ahora:
            st.error("QR expirado.")
            conn.execute(text("UPDATE qr_tokens SET activo = FALSE WHERE token = :t"), {"t": token})
            conn.commit()
            conn.close()
            st.stop()

        # Si hay sesión y es alumno -> registro automático
        if st.session_state.usuario and st.session_state.usuario.get("rol") == "alumno":
            matricula = st.session_state.usuario.get("matricula")
            if not matricula:
                st.warning("Tu cuenta no está vinculada a una matrícula. Pide al admin que la vincule.")
                conn.close()
                st.stop()
            fecha_hoy = datetime.date.today()
            dup = conn.execute(text("""
                SELECT * FROM asistencias
                WHERE matricula = :mat AND materiaid = :mid AND fecha = :f
            """), {"mat": int(matricula), "mid": int(qr["materiaid"]), "f": fecha_hoy}).mappings().fetchone()
            if dup:
                st.info("Tu asistencia para esta materia ya está registrada hoy.")
            else:
                conn.execute(text("""
                    INSERT INTO asistencias (matricula, maestroid, materiaid, fecha, estado)
                    VALUES (:mat, :ma, :materia, :f, :est)
                """), {"mat": int(matricula), "ma": int(qr["maestroid"]), "materia": int(qr["materiaid"]), "f": fecha_hoy, "est": "Presente"})
                conn.commit()
                st.success("✅ Asistencia registrada correctamente.")
            if qr["single_use"]:
                conn.execute(text("UPDATE qr_tokens SET activo = FALSE WHERE token = :t"), {"t": token})
                conn.commit()
            conn.close()
            st.stop()

        # Si no hay sesión de alumno -> pedir login y registrar tras autenticación
        st.title("🎓 Registro de Asistencia por QR")
        st.info("Escaneaste un código QR. Ingresa con tu cuenta de alumno para registrar tu asistencia automáticamente.")
        with st.form("login_from_qr"):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submit_login = st.form_submit_button("Ingresar y registrar asistencia")
            if submit_login:
                try:
                    user = conn.execute(text("SELECT * FROM usuarios WHERE nombreusuario = :u"), {"u": username}).mappings().fetchone()
                    if user and check_password(password, user["contrasena"]):
                        sess = {"nombre": user["nombreusuario"], "rol": user["rol"]}
                        if user["maestroid"]:
                            sess["maestroid"] = int(user["maestroid"])
                        if user["matricula"]:
                            sess["matricula"] = int(user["matricula"])
                        st.session_state.usuario = sess
                        # registrar si es alumno
                        if user["rol"] == "alumno" and user["matricula"]:
                            fecha_hoy = datetime.date.today()
                            dup2 = conn.execute(text("""
                                SELECT * FROM asistencias
                                WHERE matricula = :mat AND materiaid = :mid AND fecha = :f
                            """), {"mat": int(user["matricula"]), "mid": int(qr["materiaid"]), "f": fecha_hoy}).mappings().fetchone()
                            if dup2:
                                st.info("Tu asistencia para esta materia ya está registrada hoy.")
                            else:
                                conn.execute(text("""
                                    INSERT INTO asistencias (matricula, maestroid, materiaid, fecha, estado)
                                    VALUES (:mat, :ma, :materia, :f, :est)
                                """), {"mat": int(user["matricula"]), "ma": int(qr["maestroid"]), "materia": int(qr["materiaid"]), "f": fecha_hoy, "est": "Presente"})
                                conn.commit()
                                st.success("✅ Asistencia registrada correctamente.")
                            if qr["single_use"]:
                                conn.execute(text("UPDATE qr_tokens SET activo = FALSE WHERE token = :t"), {"t": token})
                                conn.commit()
                        else:
                            st.warning("Tu cuenta no es de tipo 'alumno' o no está vinculada a una matrícula.")
                        conn.close()
                        st.rerun()
                    else:
                        st.error("Usuario o contraseña incorrectos.")
                except Exception as e:
                    st.error(f"Error al autenticar: {e}")
        conn.close()
        st.stop()
    except Exception as e:
        conn.close()
        st.error(f"Error al procesar token QR: {e}")
        st.stop()

# =========================
# PANTALLA LOGIN / REGISTRO NORMAL
# =========================
def pantalla_login():
    st.title("🔐 Iniciar sesión - Control de Asistencias")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Iniciar sesión")
        with st.form("login_form"):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submit_login = st.form_submit_button("Ingresar")
            if submit_login:
                try:
                    conn = get_connection()
                    user = conn.execute(text("SELECT * FROM usuarios WHERE nombreusuario = :u"), {"u": username}).mappings().fetchone()
                    conn.close()
                    if user and check_password(password, user["contrasena"]):
                        sess = {"nombre": user["nombreusuario"], "rol": user["rol"]}
                        if user["maestroid"]:
                            sess["maestroid"] = int(user["maestroid"])
                        if user["matricula"]:
                            sess["matricula"] = int(user["matricula"])
                        st.session_state.usuario = sess
                        st.success(f"Bienvenido {user['nombreusuario']}")
                        st.rerun()
                    else:
                        st.error("Usuario o contraseña incorrectos.")
                except Exception as e:
                    st.error(f"Error al iniciar sesión: {e}")

    with col2:
        st.subheader("Crear cuenta")
        with st.form("registro_form"):
            new_user = st.text_input("Nombre de usuario")
            new_pass = st.text_input("Contraseña", type="password")
            rol = st.selectbox("Tipo de cuenta", ["alumno", "maestro", "admin"])
            conn = get_connection()
            maestros_df = pd.read_sql("SELECT maestroid, nombre, apellido FROM maestros ORDER BY nombre", conn)
            alumnos_df = pd.read_sql("SELECT matricula, nombre, apellido FROM alumnos ORDER BY nombre", conn)
            conn.close()

            col_a, col_b = st.columns(2)
            maestro_link = None
            alumno_link = None
            with col_a:
                if rol == "maestro":
                    if maestros_df.empty:
                        st.info("No hay maestros registrados: crea el registro en la sección 'Maestros' después.")
                    else:
                        maestro_link = st.selectbox("Vincular a maestro existente (opcional)", ["-- Ninguno --"] + (maestros_df["nombre"] + " " + maestros_df["apellido"]).tolist())
                        if maestro_link == "-- Ninguno --":
                            maestro_link = None
                elif rol == "alumno":
                    if alumnos_df.empty:
                        st.info("No hay alumnos registrados: crea el registro en la sección 'Alumnos' después.")
                    else:
                        alumno_link = st.selectbox("Vincular a alumno existente (opcional)", ["-- Ninguno --"] + (alumnos_df["nombre"] + " " + alumnos_df["apellido"]).tolist())
                        if alumno_link == "-- Ninguno --":
                            alumno_link = None

            submit_reg = st.form_submit_button("Registrar cuenta")
            if submit_reg:
                if not new_user or not new_pass:
                    st.warning("Completa todos los campos.")
                else:
                    try:
                        h = hash_password(new_pass)
                        conn = get_connection()
                        ma_id = None
                        mat_id = None
                        if rol == "maestro" and maestro_link:
                            ma_id = int(maestros_df.loc[(maestros_df["nombre"] + " " + maestros_df["apellido"]) == maestro_link, "maestroid"].iloc[0])
                        if rol == "alumno" and alumno_link:
                            mat_id = int(alumnos_df.loc[(alumnos_df["nombre"] + " " + alumnos_df["apellido"]) == alumno_link, "matricula"].iloc[0])
                        conn.execute(text("""
                            INSERT INTO usuarios (nombreusuario, contrasena, rol, maestroid, matricula)
                            VALUES (:u, :p, :r, :ma, :ma2)
                        """), {"u": new_user, "p": h, "r": rol, "ma": ma_id, "ma2": mat_id})
                        conn.commit()
                        conn.close()
                        st.success("Usuario registrado correctamente.")
                    except Exception as e:
                        st.error(f"No se pudo crear el usuario: {e}")

# =========================
# LOGOUT
# =========================
def logout():
    st.session_state.usuario = None
    st.rerun()

# =========================
# FUNCIONES DE GESTIÓN
# =========================
def admin_panel(conn):
    st.header("📊 Panel Administrador")
    try:
        total_al = pd.read_sql("SELECT COUNT(*) as cnt FROM alumnos", conn).iloc[0]["cnt"]
        total_ma = pd.read_sql("SELECT COUNT(*) as cnt FROM maestros", conn).iloc[0]["cnt"]
        total_mat = pd.read_sql("SELECT COUNT(*) as cnt FROM materias", conn).iloc[0]["cnt"]
        total_as = pd.read_sql("SELECT COUNT(*) as cnt FROM asistencias", conn).iloc[0]["cnt"]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Alumnos", total_al)
        c2.metric("Maestros", total_ma)
        c3.metric("Materias", total_mat)
        c4.metric("Asistencias", total_as)

        st.markdown("---")
        df_as = pd.read_sql("SELECT estado, COUNT(*) as cnt FROM asistencias GROUP BY estado", conn)
        if df_as.empty:
            st.info("No hay registros de asistencias aún.")
        else:
            st.subheader("Asistencias por estado")
            st.dataframe(df_as, use_container_width=True)
            fig_bar = px.bar(df_as, x="estado", y="cnt", labels={"estado": "Estado", "cnt": "Cantidad"}, title="Asistencias por Estado")
            st.plotly_chart(fig_bar, use_container_width=True)
            fig_pie = px.pie(df_as, names="estado", values="cnt", title="Distribución por estado")
            st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown("---")
        df_time = pd.read_sql("""
            SELECT fecha::date AS fecha, COUNT(*) AS cnt
            FROM asistencias
            GROUP BY fecha::date
            ORDER BY fecha::date
        """, conn)
        if df_time.empty:
            st.info("No hay datos de tendencia.")
        else:
            st.subheader("Tendencia de asistencias (por fecha)")
            fig_line = px.line(df_time, x="fecha", y="cnt", markers=True, title="Asistencias por Día")
            st.plotly_chart(fig_line, use_container_width=True)

        st.markdown("---")
        df_mat_ma = pd.read_sql("""
            SELECT ma.maestroid, ma.nombre || ' ' || ma.apellido AS maestro, COUNT(m.materiaid) AS cantidad
            FROM maestros ma
            LEFT JOIN materias m ON m.maestroid = ma.maestroid
            GROUP BY ma.maestroid, maestro
            ORDER BY cantidad DESC
        """, conn)
        if not df_mat_ma.empty:
            st.subheader("Materias por Maestro")
            st.dataframe(df_mat_ma, use_container_width=True)
            fig_hbar = px.bar(df_mat_ma, x="cantidad", y="maestro", orientation="h", title="Cantidad de Materias por Maestro")
            st.plotly_chart(fig_hbar, use_container_width=True)

        st.markdown("---")
        st.subheader("Exportar datos")
        alumnos = pd.read_sql("SELECT * FROM alumnos", conn)
        maestros = pd.read_sql("SELECT * FROM maestros", conn)
        materias = pd.read_sql("SELECT * FROM materias", conn)
        asistencias = pd.read_sql("SELECT * FROM asistencias", conn)
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            mostrar_df_download(alumnos, "alumnos.csv", "📥 Descargar Alumnos")
        with col2:
            mostrar_df_download(maestros, "maestros.csv", "📥 Descargar Maestros")
        with col3:
            mostrar_df_download(materias, "materias.csv", "📥 Descargar Materias")
        with col4:
            mostrar_df_download(asistencias, "asistencias.csv", "📥 Descargar Asistencias")

    except Exception as e:
        st.error(f"Error panel admin: {e}")

def gestion_alumnos(conn):
    st.header("👨‍🎓 Gestión de Alumnos")
    try:
        alumnos = pd.read_sql("SELECT * FROM alumnos ORDER BY matricula", conn)
        st.dataframe(alumnos, use_container_width=True)
        with st.form("form_alumno"):
            nombre = st.text_input("Nombre")
            apellido = st.text_input("Apellido")
            submit = st.form_submit_button("Guardar")
            if submit:
                if nombre and apellido:
                    conn.execute(text("INSERT INTO alumnos (nombre, apellido) VALUES (:n, :a)"), {"n": nombre, "a": apellido})
                    conn.commit()
                    st.success("Alumno agregado.")
                    st.rerun()
                else:
                    st.warning("Completa los campos.")
        if not alumnos.empty:
            st.subheader("Editar / Eliminar alumno")
            sel = st.selectbox("Selecciona alumno", alumnos["nombre"] + " " + alumnos["apellido"])
            alu_id = alumnos.loc[(alumnos["nombre"] + " " + alumnos["apellido"]) == sel, "matricula"].iloc[0]
            accion = st.radio("Acción", ["Editar", "Eliminar"])
            if accion == "Editar":
                nuevo_nom = st.text_input("Nuevo nombre")
                nuevo_ape = st.text_input("Nuevo apellido")
                if st.button("Guardar cambios"):
                    conn.execute(text("UPDATE alumnos SET nombre=:n, apellido=:a WHERE matricula=:id"), {"n": nuevo_nom, "a": nuevo_ape, "id": int(alu_id)})
                    conn.commit()
                    st.success("Alumno actualizado.")
                    st.rerun()
            elif accion == "Eliminar":
                if st.button("Eliminar alumno"):
                    # borrar relaciones en clase_alumnos y asistencias también
                    conn.execute(text("DELETE FROM clase_alumnos WHERE matricula = :id"), {"id": int(alu_id)})
                    conn.execute(text("DELETE FROM asistencias WHERE matricula = :id"), {"id": int(alu_id)})
                    conn.execute(text("DELETE FROM usuarios WHERE matricula = :id"), {"id": int(alu_id)})
                    conn.execute(text("DELETE FROM alumnos WHERE matricula = :id"), {"id": int(alu_id)})
                    conn.commit()
                    st.warning("Alumno eliminado (y relaciones).")
                    st.rerun()
    except Exception as e:
        st.error(f"Error alumnos: {e}")

def gestion_maestros(conn):
    st.header("👨‍🏫 Gestión de Maestros")
    try:
        maestros = pd.read_sql("SELECT * FROM maestros ORDER BY maestroid", conn)
        st.dataframe(maestros, use_container_width=True)
        with st.form("form_maestro"):
            nombre = st.text_input("Nombre")
            apellido = st.text_input("Apellido")
            submit = st.form_submit_button("Guardar")
            if submit:
                if nombre and apellido:
                    conn.execute(text("INSERT INTO maestros (nombre, apellido) VALUES (:n, :a)"), {"n": nombre, "a": apellido})
                    conn.commit()
                    st.success("Maestro agregado.")
                    st.rerun()
                else:
                    st.warning("Completa los campos.")
        if not maestros.empty:
            st.subheader("Editar / Eliminar maestro")
            sel = st.selectbox("Selecciona maestro", maestros["nombre"] + " " + maestros["apellido"])
            m_id = maestros.loc[(maestros["nombre"] + " " + maestros["apellido"]) == sel, "maestroid"].iloc[0]
            accion = st.radio("Acción", ["Editar", "Eliminar"])
            if accion == "Editar":
                nuevo_nom = st.text_input("Nuevo nombre")
                nuevo_ape = st.text_input("Nuevo apellido")
                if st.button("Guardar cambios maestro"):
                    conn.execute(text("UPDATE maestros SET nombre=:n, apellido=:a WHERE maestroid=:id"), {"n": nuevo_nom, "a": nuevo_ape, "id": int(m_id)})
                    conn.commit()
                    st.success("Maestro actualizado.")
                    st.rerun()
            elif accion == "Eliminar":
                if st.button("Eliminar maestro"):
                    # borrar materias del maestro y desvincular usuarios
                    conn.execute(text("UPDATE materias SET maestroid = NULL WHERE maestroid = :id"), {"id": int(m_id)})
                    conn.execute(text("UPDATE usuarios SET maestroid = NULL WHERE maestroid = :id"), {"id": int(m_id)})
                    conn.execute(text("DELETE FROM maestros WHERE maestroid = :id"), {"id": int(m_id)})
                    conn.commit()
                    st.warning("Maestro eliminado y materias desvinculadas.")
                    st.rerun()
    except Exception as e:
        st.error(f"Error maestros: {e}")

def gestion_materias(conn):
    st.header("📚 Gestión de Materias / Clases")
    try:
        materias = pd.read_sql("""
            SELECT m.materiaid, m.nombre, m.descripcion, m.horario,
                   ma.maestroid, ma.nombre AS maestro_nombre, ma.apellido AS maestro_apellido
            FROM materias m
            LEFT JOIN maestros ma ON m.maestroid = ma.maestroid
            ORDER BY m.materiaid
        """, conn)
        st.dataframe(materias, use_container_width=True)

        maestros = pd.read_sql("SELECT maestroid, nombre, apellido FROM maestros ORDER BY nombre", conn)
        st.subheader("Agregar nueva materia")
        with st.form("form_materia"):
            nombre = st.text_input("Nombre")
            descripcion = st.text_area("Descripción")
            if maestros.empty:
                st.warning("Primero registra maestros.")
                maestro_id = None
            else:
                maestro_sel = st.selectbox("Selecciona maestro", ["-- Ninguno --"] + (maestros["nombre"] + " " + maestros["apellido"]).tolist())
                maestro_id = None
                if maestro_sel != "-- Ninguno --":
                    maestro_id = int(maestros.loc[(maestros["nombre"] + " " + maestros["apellido"]) == maestro_sel, "maestroid"].iloc[0])
            horario_sel = st.selectbox("Horario", HORARIOS)
            submit = st.form_submit_button("Guardar")
            if submit:
                if not nombre:
                    st.warning("El nombre es obligatorio.")
                elif maestro_id is None:
                    st.warning("Selecciona un maestro.")
                else:
                    conflicto = conn.execute(
                        text("SELECT * FROM materias WHERE maestroid = :m AND horario = :h"),
                        {"m": maestro_id, "h": horario_sel}
                    ).mappings().fetchall()
                    if conflicto:
                        st.error("⚠️ El maestro ya tiene una clase en ese horario.")
                    else:
                        conn.execute(text("INSERT INTO materias (nombre, descripcion, maestroid, horario) VALUES (:n, :d, :m, :h)"),
                                     {"n": nombre, "d": descripcion, "m": maestro_id, "h": horario_sel})
                        conn.commit()
                        st.success("Materia agregada.")
                        st.rerun()

        if not materias.empty:
            st.subheader("Editar / Eliminar materia")
            sel = st.selectbox("Selecciona materia", materias["nombre"])
            mat_id = materias.loc[materias["nombre"] == sel, "materiaid"].iloc[0]
            accion = st.radio("Acción", ["Editar", "Eliminar"])
            if accion == "Editar":
                nuevo_nom = st.text_input("Nuevo nombre")
                nueva_desc = st.text_area("Nueva descripción")
                maestro_sel2 = st.selectbox("Nuevo maestro", ["-- Mantener --"] + (maestros["nombre"] + " " + maestros["apellido"]).tolist())
                horario_new = st.selectbox("Nuevo horario", ["-- Mantener --"] + HORARIOS)
                if st.button("Guardar cambios materia"):
                    maestro_new_id = None
                    if maestro_sel2 != "-- Mantener --":
                        maestro_new_id = int(maestros.loc[(maestros["nombre"] + " " + maestros["apellido"]) == maestro_sel2, "maestroid"].iloc[0])
                    # verificar conflicto si hay maestro nuevo y horario nuevo
                    if maestro_new_id is not None and horario_new != "-- Mantener --":
                        conflicto = pd.read_sql(
                            "SELECT * FROM materias WHERE maestroid = %s AND horario = %s AND materiaid != %s",
                            conn,
                            params=[maestro_new_id, horario_new, int(mat_id)]
                        )
                        if not conflicto.empty:
                            st.error("⚠️ Conflicto de horario para el maestro seleccionado.")
                        else:
                            conn.execute(text("UPDATE materias SET nombre=:n, descripcion=:d, maestroid=:m, horario=:h WHERE materiaid=:id"),
                                         {"n": nuevo_nom or sel, "d": nueva_desc or None, "m": maestro_new_id, "h": horario_new, "id": int(mat_id)})
                            conn.commit()
                            st.success("Materia actualizada.")
                            st.rerun()
                    else:
                        update_q = "UPDATE materias SET nombre=:n, descripcion=:d {extra} WHERE materiaid=:id"
                        extra = ""
                        params = {"n": nuevo_nom or sel, "d": nueva_desc or None, "id": int(mat_id)}
                        if maestro_new_id is not None:
                            extra += ", maestroid=:m"
                            params["m"] = maestro_new_id
                        if horario_new != "-- Mantener --":
                            extra += ", horario=:h"
                            params["h"] = horario_new
                        conn.execute(text(update_q.format(extra=extra)), params)
                        conn.commit()
                        st.success("Materia actualizada.")
                        st.rerun()
            elif accion == "Eliminar":
                if st.button("Eliminar materia"):
                    # eliminar relaciones y asistencias asociadas
                    conn.execute(text("DELETE FROM clase_alumnos WHERE materiaid = :id"), {"id": int(mat_id)})
                    conn.execute(text("DELETE FROM asistencias WHERE materiaid = :id"), {"id": int(mat_id)})
                    conn.execute(text("DELETE FROM qr_tokens WHERE materiaid = :id"), {"id": int(mat_id)})
                    conn.execute(text("DELETE FROM materias WHERE materiaid = :id"), {"id": int(mat_id)})
                    conn.commit()
                    st.warning("Materia eliminada (y relaciones).")
                    st.rerun()
    except Exception as e:
        st.error(f"Error materias: {e}")

def gestion_asignaciones(conn):
    st.header("🔗 Asignar Alumnos a Clases (Admin)")
    try:
        materias = pd.read_sql("SELECT materiaid, nombre, horario FROM materias ORDER BY nombre", conn)
        alumnos = pd.read_sql("SELECT matricula, nombre, apellido FROM alumnos ORDER BY nombre", conn)
        if materias.empty or alumnos.empty:
            st.info("Primero crea materias y alumnos.")
            return
        mat_map = {f"{r['materiaid']}: {r['nombre']} ({r['horario']})": r['materiaid'] for _, r in materias.iterrows()}
        alu_map = {f"{r['matricula']}: {r['nombre']} {r['apellido']}": r['matricula'] for _, r in alumnos.iterrows()}
        sel_mat = st.selectbox("Materia", list(mat_map.keys()))
        sel_alu = st.selectbox("Alumno", list(alu_map.keys()))
        if st.button("Asignar alumno a clase"):
            try:
                conn.execute(text("INSERT INTO clase_alumnos (materiaid, matricula) VALUES (:mid, :mat)"), {"mid": mat_map[sel_mat], "mat": alu_map[sel_alu]})
                conn.commit()
                st.success("Alumno asignado a la clase.")
                st.rerun()
            except Exception as e:
                st.error("No se pudo asignar (quizá ya está asignado).")
        st.markdown("---")
        st.subheader("Ver / Eliminar asignaciones")
        filtros = pd.read_sql("""
            SELECT ca.id, ca.materiaid, m.nombre AS materia, m.horario, ca.matricula, a.nombre AS alumno_nom, a.apellido AS alumno_ape
            FROM clase_alumnos ca
            LEFT JOIN materias m ON ca.materiaid = m.materiaid
            LEFT JOIN alumnos a ON ca.matricula = a.matricula
            ORDER BY m.nombre
        """, conn)
        if filtros.empty:
            st.info("No hay asignaciones aún.")
        else:
            st.dataframe(filtros, use_container_width=True)
            sel_id = st.selectbox("Selecciona ID de asignación para eliminar", filtros["id"].tolist())
            if st.button("Eliminar asignación"):
                conn.execute(text("DELETE FROM clase_alumnos WHERE id = :id"), {"id": int(sel_id)})
                conn.commit()
                st.warning("Asignación eliminada.")
                st.rerun()
    except Exception as e:
        st.error(f"Error asignaciones: {e}")

def gestion_asistencias(conn, maestroid_for_teacher=None, matricula_for_student=None):
    st.header("📅 Gestión de Asistencias")
    try:
        asist = pd.read_sql("""
            SELECT a.asistenciaid, a.fecha, a.estado,
                   al.nombre AS alumno_nombre, al.apellido AS alumno_apellido,
                   ma.nombre AS maestro_nombre, ma.apellido AS maestro_apellido,
                   m.nombre AS materia_nombre
            FROM asistencias a
            LEFT JOIN alumnos al ON a.matricula = al.matricula
            LEFT JOIN maestros ma ON a.maestroid = ma.maestroid
            LEFT JOIN materias m ON a.materiaid = m.materiaid
            ORDER BY a.fecha DESC
        """, conn)
        st.dataframe(asist, use_container_width=True)

        st.subheader("Registrar asistencia")
        with st.form("form_asistencia_admin"):
            alumnos = pd.read_sql("SELECT matricula, nombre, apellido FROM alumnos ORDER BY nombre", conn)
            maestros = pd.read_sql("SELECT maestroid, nombre, apellido FROM maestros ORDER BY nombre", conn)
            materias = pd.read_sql("SELECT materiaid, nombre FROM materias ORDER BY nombre", conn)

            if matricula_for_student is not None:
                alumno_sel = alumnos.loc[alumnos["matricula"] == matricula_for_student, "nombre"].iloc[0] + " " + alumnos.loc[alumnos["matricula"] == matricula_for_student, "apellido"].iloc[0]
                st.write(f"Alumno: {alumno_sel}")
            else:
                alumno_sel = st.selectbox("Alumno", alumnos["nombre"] + " " + alumnos["apellido"])

            if maestroid_for_teacher is not None:
                maestro_sel = maestros.loc[maestros["maestroid"] == maestroid_for_teacher, "nombre"].iloc[0] + " " + maestros.loc[maestros["maestroid"] == maestroid_for_teacher, "apellido"].iloc[0]
                st.write(f"Maestro: {maestro_sel}")
            else:
                maestro_sel = st.selectbox("Maestro", maestros["nombre"] + " " + maestros["apellido"])

            materia_sel = st.selectbox("Materia", ["-- Seleccionar --"] + materias["nombre"].tolist())
            estado = st.selectbox("Estado", ["Presente", "Ausente", "Retardo"])
            fecha = st.date_input("Fecha", datetime.date.today())
            submit = st.form_submit_button("Guardar")

            if submit:
                if matricula_for_student is not None:
                    alumno_id = matricula_for_student
                else:
                    alumno_id = int(alumnos.loc[(alumnos["nombre"] + " " + alumnos["apellido"]) == alumno_sel, "matricula"].iloc[0])
                if maestroid_for_teacher is not None:
                    maestro_id = maestroid_for_teacher
                else:
                    maestro_id = int(maestros.loc[(maestros["nombre"] + " " + maestros["apellido"]) == maestro_sel, "maestroid"].iloc[0])
                if materia_sel == "-- Seleccionar --":
                    st.warning("Selecciona una materia.")
                else:
                    materia_id = int(materias.loc[materias["nombre"] == materia_sel, "materiaid"].iloc[0])
                    conn.execute(text("INSERT INTO asistencias (matricula, maestroid, materiaid, fecha, estado) VALUES (:a, :m, :matid, :f, :e)"),
                                 {"a": int(alumno_id), "m": int(maestro_id), "matid": int(materia_id), "f": fecha, "e": estado})
                    conn.commit()
                    st.success("Asistencia registrada.")
                    st.rerun()

        if not asist.empty:
            st.subheader("Eliminar registro de asistencia")
            sel_id = st.selectbox("Selecciona ID de asistencia", asist["asistenciaid"])
            if st.button("Eliminar asistencia"):
                conn.execute(text("DELETE FROM asistencias WHERE asistenciaid = :id"), {"id": int(sel_id)})
                conn.commit()
                st.warning("Registro eliminado.")
                st.rerun()

    except Exception as e:
        st.error(f"Error asistencias: {e}")

# =========================
# INTERFAZ PRINCIPAL
# =========================
if st.session_state.usuario:
    user = st.session_state.usuario

    # Sidebar styling
    st.sidebar.markdown("""
        <style>
        [data-testid="stSidebar"] {height:100vh; background-color: #0d47a1;}
        [data-testid="stSidebar"] div {color: white;}
        .streamlit-expanderHeader {color: white;}
        </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/3209/3209993.png", width=80)
        st.markdown(f"**{user['nombre']}**")
        st.markdown(f"Rol: **{user['rol']}**")
        if user["rol"] == "admin":
            opciones = ["Panel Admin", "Alumnos", "Maestros", "Materias", "Asignaciones", "Asistencias", "Tokens QR"]
        elif user["rol"] == "maestro":
            opciones = ["Mis Materias", "Registrar Asistencia", "📷 Asistencia por QR", "Asistencias (mis registros)", "Tokens QR"]
        else:
            opciones = ["Mis Clases", "Mis Asistencias", "Registrar Asistencia (token)"]
        seleccion = option_menu("Menú", opciones, icons=["house", "people", "person-badge", "book", "link", "calendar-check"], menu_icon="cast")
        st.button("Cerrar sesión", on_click=logout, use_container_width=True)

    conn = get_connection()

    # ADMIN
    if user["rol"] == "admin":
        if seleccion == "Panel Admin":
            admin_panel(conn)
        elif seleccion == "Alumnos":
            gestion_alumnos(conn)
        elif seleccion == "Maestros":
            gestion_maestros(conn)
        elif seleccion == "Materias":
            gestion_materias(conn)
        elif seleccion == "Asignaciones":
            gestion_asignaciones(conn)
        elif seleccion == "Asistencias":
            gestion_asistencias(conn)
        elif seleccion == "Tokens QR":
            st.header("🔑 Tokens QR (historial)")
            df_tokens = pd.read_sql("SELECT * FROM qr_tokens ORDER BY fecha_creacion DESC LIMIT 200", conn)
            st.dataframe(df_tokens, use_container_width=True)
            if st.button("Desactivar tokens expirados"):
                conn.execute(text("UPDATE qr_tokens SET activo = FALSE WHERE expiracion <= NOW()"))
                conn.commit()
                st.success("Tokens expirados desactivados.")
                st.rerun()

    # MAESTRO
    elif user["rol"] == "maestro":
        # asegurar maestroid en session si no existe
        if "maestroid" not in user:
            try:
                res = conn.execute(text("SELECT maestroid FROM usuarios WHERE nombreusuario = :u"), {"u": user["nombre"]}).mappings().fetchone()
                if res and res["maestroid"]:
                    st.session_state.usuario["maestroid"] = int(res["maestroid"])
                    user = st.session_state.usuario
            except Exception:
                pass

        if seleccion == "Mis Materias":
            st.header("📘 Mis Materias")
            if "maestroid" not in user:
                st.warning("No estás vinculado a un maestro (tu usuario). Pide al admin que vincule tu cuenta o crea el maestro y vincula tu usuario.")
            else:
                ma_id = user["maestroid"]
                materias_df = pd.read_sql("SELECT materiaid, nombre, descripcion, horario FROM materias WHERE maestroid = :m ORDER BY horario", conn, params={"m": ma_id})
                if materias_df.empty:
                    st.info("No tienes materias asignadas.")
                else:
                    for _, row in materias_df.iterrows():
                        st.subheader(f"{row['nombre']}  —  {row['horario']}")
                        # listar alumnos asignados a la materia
                        alumnos_materia = pd.read_sql("""
                            SELECT a.matricula, a.nombre, a.apellido
                            FROM clase_alumnos ca
                            JOIN alumnos a ON ca.matricula = a.matricula
                            WHERE ca.materiaid = :mid
                            ORDER BY a.nombre
                        """, conn, params={"mid": int(row["materiaid"])})
                        if alumnos_materia.empty:
                            st.info("No hay alumnos asignados a esta materia.")
                        else:
                            st.write("Alumnos asignados:")
                            st.dataframe(alumnos_materia, use_container_width=True)

        elif seleccion == "Registrar Asistencia":
            st.header("✍️ Registrar Asistencia (Maestro)")
            if "maestroid" not in user:
                st.warning("No estás vinculado a un maestro (tu usuario).")
            else:
                gestion_asistencias(conn, maestroid_for_teacher=user["maestroid"])

        elif seleccion == "Asistencias (mis registros)":
            st.header("📄 Mis registros de asistencia")
            if "maestroid" not in user:
                st.warning("No estás vinculado a un maestro.")
            else:
                df = pd.read_sql("""
                    SELECT a.asistenciaid, a.fecha, a.estado, al.nombre AS alumno, al.apellido AS apellido, m.nombre AS materia
                    FROM asistencias a
                    JOIN alumnos al ON a.matricula = al.matricula
                    LEFT JOIN materias m ON a.materiaid = m.materiaid
                    WHERE a.maestroid = :m
                    ORDER BY a.fecha DESC
                """, conn, params={"m": user["maestroid"]})
                if df.empty:
                    st.info("No tienes registros aún.")
                else:
                    st.dataframe(df, use_container_width=True)
                    mostrar_df_download(df, "mis_asistencias.csv", "📥 Descargar mis asistencias")

        elif seleccion == "📷 Asistencia por QR":
            st.header("📷 Generar Asistencia por Código QR")
            if "maestroid" not in user:
                st.warning("No estás vinculado a un maestro.")
            else:
                ma_id = user["maestroid"]
                materias = pd.read_sql("SELECT materiaid, nombre, horario FROM materias WHERE maestroid = :m ORDER BY horario", conn, params={"m": ma_id})
                if materias.empty:
                    st.info("No tienes materias asignadas.")
                else:
                    materia_sel = st.selectbox("Selecciona materia", materias["nombre"])
                    materia_id = int(materias.loc[materias["nombre"] == materia_sel, "materiaid"].iloc[0])
                    single_use = st.checkbox("Token de un solo uso (se inactivará tras primer uso)", value=False)
                    tiempo_min = st.number_input("Minutos de validez del QR", min_value=1, max_value=60, value=5)
                    if st.button("Generar QR temporal"):
                        token = generar_token(16)
                        expiracion = datetime.datetime.utcnow() + datetime.timedelta(minutes=int(tiempo_min))
                        conn.execute(text("""
                            INSERT INTO qr_tokens (token, materiaid, maestroid, expiracion, activo, single_use)
                            VALUES (:t, :mid, :maid, :exp, TRUE, :su)
                        """), {"t": token, "mid": materia_id, "maid": ma_id, "exp": expiracion, "su": single_use})
                        conn.commit()
                        qr_url = f"{BASE_URL}?qr_token={token}"
                        b64 = generar_qr_image_data(qr_url)
                        st.success(f"✅ QR generado para **{materia_sel}**. Escanea con el celular (o comparte el enlace).")
                        st.image(f"data:image/png;base64,{b64}")
                        st.markdown(f"**Enlace QR:** {qr_url}")
                        tokens_ma = pd.read_sql("SELECT * FROM qr_tokens WHERE maestroid = :m ORDER BY fecha_creacion DESC LIMIT 20", conn, params={"m": ma_id})
                        st.subheader("Tokens recientes")
                        st.dataframe(tokens_ma, use_container_width=True)

        elif seleccion == "Tokens QR":
            st.header("🔑 Tokens QR (mis tokens)")
            if "maestroid" not in user:
                st.warning("No estás vinculado a un maestro.")
            else:
                df_tokens = pd.read_sql("SELECT * FROM qr_tokens WHERE maestroid = :m ORDER BY fecha_creacion DESC LIMIT 200", conn, params={"m": user["maestroid"]})
                st.dataframe(df_tokens, use_container_width=True)
                if st.button("Desactivar tokens expirados (mis tokens)"):
                    conn.execute(text("UPDATE qr_tokens SET activo = FALSE WHERE expiracion <= NOW() AND maestroid = :m"), {"m": user["maestroid"]})
                    conn.commit()
                    st.success("Tokens expirados desactivados.")
                    st.rerun()

    # ALUMNO
    elif user["rol"] == "alumno":
        if "matricula" not in user:
            try:
                res = conn.execute(text("SELECT matricula FROM usuarios WHERE nombreusuario = :u"), {"u": user["nombre"]}).mappings().fetchone()
                if res and res["matricula"]:
                    st.session_state.usuario["matricula"] = int(res["matricula"])
                    user = st.session_state.usuario
            except Exception:
                pass

        if seleccion == "Mis Clases":
            st.header("📚 Mis Clases Asignadas")
            if "matricula" not in user:
                st.warning("Tu cuenta no está vinculada a una matrícula. Pide al admin que la vincule.")
            else:
                mat = user["matricula"]
                clases = pd.read_sql("""
                    SELECT m.materiaid, m.nombre AS materia, m.horario, ma.nombre AS maestro_nom, ma.apellido AS maestro_ape
                    FROM clase_alumnos ca
                    JOIN materias m ON ca.materiaid = m.materiaid
                    LEFT JOIN maestros ma ON m.maestroid = ma.maestroid
                    WHERE ca.matricula = :mat
                    ORDER BY m.horario
                """, conn, params={"mat": mat})
                if clases.empty:
                    st.info("No tienes clases asignadas.")
                else:
                    st.dataframe(clases, use_container_width=True)
                    mostrar_df_download(clases, "mis_clases.csv", "📥 Descargar mis clases")

        elif seleccion == "Mis Asistencias":
            st.header("📆 Mis Asistencias")
            try:
                query = text("""
                    SELECT a.fecha,
                           a.estado,
                           ma.nombre AS maestro,
                           ma.apellido AS maestro_apellido,
                           m.nombre AS materia
                    FROM asistencias a
                    LEFT JOIN maestros ma ON a.maestroid = ma.maestroid
                    LEFT JOIN materias m ON a.materiaid = m.materiaid
                    WHERE a.matricula = :mat
                    ORDER BY a.fecha DESC
                """)
                result = conn.execute(query, {"mat": user["matricula"]}).mappings().all()
                if result:
                    df = pd.DataFrame(result)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No se han registrado asistencias aún.")
            except Exception as e:
                st.error(f"Ocurrió un error al cargar tus asistencias: {e}")

        elif seleccion == "Registrar Asistencia (token)":
            st.header("Registrar asistencia por token (pega token o usa QR)")
            mat = user.get("matricula")
            if not mat:
                st.warning("Tu usuario no está vinculado a una matrícula.")
            else:
                token = st.text_input("Token QR (o deja vacío si vienes desde ?qr_token=...)", key="token_input_alumno")
                params = st.experimental_get_query_params()
                if "qr_token" in params:
                    token = params["qr_token"][0]
                    st.info("Se detectó token en la URL.")
                if st.button("Registrar asistencia"):
                    if not token:
                        st.warning("Proporciona un token.")
                    else:
                        # registrar llamando DB directamente (mismo comportamiento que en inicio QR)
                        qr = conn.execute(text("SELECT * FROM qr_tokens WHERE token = :t AND activo = TRUE"), {"t": token}).mappings().fetchone()
                        if not qr:
                            st.error("Token inválido o inactivo.")
                        else:
                            ahora = datetime.datetime.utcnow()
                            if qr["expiracion"] is not None and qr["expiracion"] <= ahora:
                                st.error("Token expirado.")
                                conn.execute(text("UPDATE qr_tokens SET activo = FALSE WHERE token = :t"), {"t": token})
                                conn.commit()
                            else:
                                hoy = datetime.date.today()
                                dup = conn.execute(text("SELECT * FROM asistencias WHERE matricula = :mat AND materiaid = :mid AND fecha = :f"), {"mat": int(mat), "mid": int(qr["materiaid"]), "f": hoy}).mappings().fetchone()
                                if dup:
                                    st.info("Tu asistencia para esta materia ya está registrada hoy.")
                                else:
                                    conn.execute(text("INSERT INTO asistencias (matricula, maestroid, materiaid, fecha, estado) VALUES (:mat, :ma, :mid, :f, :est)"),
                                                 {"mat": int(mat), "ma": int(qr["maestroid"]), "mid": int(qr["materiaid"]), "f": hoy, "est": "Presente"})
                                    if qr["single_use"]:
                                        conn.execute(text("UPDATE qr_tokens SET activo = FALSE WHERE token = :t"), {"t": token})
                                    conn.commit()
                                    st.success("Asistencia registrada correctamente.")
    conn.close()

else:
    pantalla_login()
