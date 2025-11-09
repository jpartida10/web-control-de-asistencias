import streamlit as st
import pandas as pd
import sqlalchemy
from sqlalchemy import text
import datetime
import bcrypt
from streamlit_option_menu import option_menu

# =========================================
# CONFIGURACIÓN DE LA PÁGINA
# =========================================
st.set_page_config(page_title="Control de Asistencias", layout="wide")

# =========================================
# CONEXIÓN A LA BASE DE DATOS
# =========================================
DATABASE_URL = "postgresql://neondb_owner:npg_1f3sluIdFRyA@ep-solitary-meadow-adthlkqa-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def get_connection():
    engine = sqlalchemy.create_engine(DATABASE_URL)
    return engine.connect()

# =========================================
# CREACIÓN DE TABLAS
# =========================================
def crear_tablas():
    conn = get_connection()
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS usuarios (
        usuarioid SERIAL PRIMARY KEY,
        nombreusuario VARCHAR(50) UNIQUE NOT NULL,
        contrasena TEXT NOT NULL,
        rol VARCHAR(20)
    );
    CREATE TABLE IF NOT EXISTS alumnos (
        matricula SERIAL PRIMARY KEY,
        nombre VARCHAR(50),
        apellido VARCHAR(50)
    );
    CREATE TABLE IF NOT EXISTS maestros (
        maestroid SERIAL PRIMARY KEY,
        nombre VARCHAR(50),
        apellido VARCHAR(50)
    );
    CREATE TABLE IF NOT EXISTS materias (
        materiaid SERIAL PRIMARY KEY,
        nombre VARCHAR(50),
        descripcion TEXT,
        maestroid INT REFERENCES maestros(maestroid) ON DELETE SET NULL,
        horario VARCHAR(50)
    );
    CREATE TABLE IF NOT EXISTS asistencias (
        asistenciaid SERIAL PRIMARY KEY,
        matricula INT REFERENCES alumnos(matricula) ON DELETE CASCADE,
        maestroid INT REFERENCES maestros(maestroid) ON DELETE CASCADE,
        fecha DATE,
        estado VARCHAR(20)
    );
    """))
    conn.commit()
    conn.close()

crear_tablas()

# =========================================
# SESIÓN DE USUARIO
# =========================================
if "usuario" not in st.session_state:
    st.session_state.usuario = None

# =========================================
# LOGIN Y REGISTRO
# =========================================
def pantalla_login():
    st.title("🔐 Sistema de Control de Asistencias")

    opcion = st.radio("Selecciona una opción:", ["Iniciar sesión", "Crear cuenta"])

    if opcion == "Iniciar sesión":
        with st.form("login_form"):
            usuario = st.text_input("Usuario")
            contrasena = st.text_input("Contraseña", type="password")
            enviar = st.form_submit_button("Ingresar")

            if enviar:
                conn = get_connection()
                user = conn.execute(text("SELECT * FROM usuarios WHERE nombreusuario = :usr"), {"usr": usuario}).fetchone()
                conn.close()

                if user and bcrypt.checkpw(contrasena.encode("utf-8"), user.contrasena.encode("utf-8")):
                    st.session_state.usuario = {"nombre": user.nombreusuario, "rol": user.rol}
                    st.success(f"Bienvenido {user.nombreusuario} 👋")
                    st.experimental_rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")

    else:  # Crear cuenta
        with st.form("registro_form"):
            usuario = st.text_input("Nombre de usuario")
            contrasena = st.text_input("Contraseña", type="password")
            rol = st.selectbox("Tipo de cuenta", ["alumno", "maestro", "admin"])
            registrar = st.form_submit_button("Registrar")

            if registrar:
                if usuario and contrasena:
                    hashed = bcrypt.hashpw(contrasena.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
                    conn = get_connection()
                    try:
                        conn.execute(text("""
                            INSERT INTO usuarios (nombreusuario, contrasena, rol)
                            VALUES (:usr, :pwd, :rol)
                        """), {"usr": usuario, "pwd": hashed, "rol": rol})
                        conn.commit()
                        st.success("✅ Usuario registrado correctamente.")
                    except Exception:
                        st.error("❌ El usuario ya existe.")
                    conn.close()
                else:
                    st.warning("⚠️ Todos los campos son obligatorios.")

# =========================================
# FUNCIÓN: LOGOUT
# =========================================
def logout():
    st.session_state.usuario = None
    st.experimental_rerun()

# =========================================
# INTERFAZ PRINCIPAL 
# =========================================
if st.session_state.usuario:
    user = st.session_state.usuario

    st.sidebar.markdown(
        """
        <style>
        [data-testid="stSidebar"] {
            background-color: #0d47a1;
            color: white;
        }
        [data-testid="stSidebar"] .css-1v3fvcr {
            color: white;
        }
        </style>
        """, unsafe_allow_html=True
    )

    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/3209/3209993.png", width=80)
        st.markdown(f"👤 **{user['nombre']} ({user['rol']})**")
        seleccion = option_menu(
            "Menú Principal",
            ["🏫 Alumnos", "👨‍🏫 Maestros", "📚 Materias", "📅 Asistencias"],
            icons=["people", "person-badge", "book", "calendar-check"],
            menu_icon="cast",
            default_index=0
        )
        st.button("Cerrar sesión", on_click=logout, use_container_width=True)

    # --- Secciones del menú ---
    conn = get_connection()

    # =================== ALUMNOS ===================
    if seleccion == "🏫 Alumnos":
        st.header("Gestión de Alumnos")

        alumnos = pd.read_sql("SELECT * FROM alumnos ORDER BY matricula", conn)
        st.dataframe(alumnos)

        with st.form("form_alumno"):
            nombre = st.text_input("Nombre")
            apellido = st.text_input("Apellido")
            guardar = st.form_submit_button("Guardar")

            if guardar:
                if nombre and apellido:
                    conn.execute(text("""
                        INSERT INTO alumnos (nombre, apellido) VALUES (:n, :a)
                    """), {"n": nombre, "a": apellido})
                    conn.commit()
                    st.success("✅ Alumno agregado correctamente.")
                    st.experimental_rerun()
                else:
                    st.warning("Completa todos los campos.")

        if not alumnos.empty:
            st.subheader("Editar o eliminar alumno")
            alumno_sel = st.selectbox("Selecciona alumno", alumnos["nombre"] + " " + alumnos["apellido"])
            alumno_id = alumnos.loc[
                (alumnos["nombre"] + " " + alumnos["apellido"]) == alumno_sel, "matricula"
            ].iloc[0]
            accion = st.radio("Acción", ["Editar", "Eliminar"])
            if accion == "Editar":
                nuevo_nombre = st.text_input("Nuevo nombre")
                nuevo_apellido = st.text_input("Nuevo apellido")
                if st.button("Guardar cambios"):
                    conn.execute(text("""
                        UPDATE alumnos SET nombre=:n, apellido=:a WHERE matricula=:id
                    """), {"n": nuevo_nombre, "a": nuevo_apellido, "id": alumno_id})
                    conn.commit()
                    st.success("Alumno actualizado.")
                    st.experimental_rerun()
            elif accion == "Eliminar":
                if st.button("Eliminar alumno"):
                    conn.execute(text("DELETE FROM alumnos WHERE matricula=:id"), {"id": alumno_id})
                    conn.commit()
                    st.warning("Alumno eliminado.")
                    st.experimental_rerun()

    # =================== MAESTROS ===================
    elif seleccion == "👨‍🏫 Maestros":
        st.header("Gestión de Maestros")
        maestros = pd.read_sql("SELECT * FROM maestros ORDER BY maestroid", conn)
        st.dataframe(maestros)

        with st.form("form_maestro"):
            nombre = st.text_input("Nombre")
            apellido = st.text_input("Apellido")
            guardar = st.form_submit_button("Guardar")
            if guardar:
                if nombre and apellido:
                    conn.execute(text("""
                        INSERT INTO maestros (nombre, apellido) VALUES (:n, :a)
                    """), {"n": nombre, "a": apellido})
                    conn.commit()
                    st.success("✅ Maestro agregado correctamente.")
                    st.experimental_rerun()
                else:
                    st.warning("Completa todos los campos.")

        if not maestros.empty:
            st.subheader("Editar o eliminar maestro")
            maestro_sel = st.selectbox("Selecciona maestro", maestros["nombre"] + " " + maestros["apellido"])
            maestro_id = maestros.loc[
                (maestros["nombre"] + " " + maestros["apellido"]) == maestro_sel, "maestroid"
            ].iloc[0]
            accion = st.radio("Acción", ["Editar", "Eliminar"])
            if accion == "Editar":
                nuevo_nombre = st.text_input("Nuevo nombre")
                nuevo_apellido = st.text_input("Nuevo apellido")
                if st.button("Guardar cambios"):
                    conn.execute(text("""
                        UPDATE maestros SET nombre=:n, apellido=:a WHERE maestroid=:id
                    """), {"n": nuevo_nombre, "a": nuevo_apellido, "id": maestro_id})
                    conn.commit()
                    st.success("Maestro actualizado.")
                    st.experimental_rerun()
            elif accion == "Eliminar":
                if st.button("Eliminar maestro"):
                    conn.execute(text("DELETE FROM maestros WHERE maestroid=:id"), {"id": maestro_id})
                    conn.commit()
                    st.warning("Maestro eliminado.")
                    st.experimental_rerun()

    # =================== MATERIAS ===================
    elif seleccion == "📚 Materias":
        st.header("Gestión de Materias")
        maestros = pd.read_sql("SELECT maestroid, nombre, apellido FROM maestros", conn)
        materias = pd.read_sql("""
            SELECT m.materiaid, m.nombre, m.descripcion, ma.nombre AS maestro, m.horario
            FROM materias m
            LEFT JOIN maestros ma ON m.maestroid = ma.maestroid
        """, conn)
        st.dataframe(materias)

        horarios = [
            "07:00 - 07:50", "07:50 - 08:40", "09:20 - 10:10", "10:10 - 11:00",
            "11:00 - 11:50", "11:50 - 12:40", "12:40 - 13:30", "13:30 - 14:20", "14:20 - 15:10"
        ]

        with st.form("form_materia"):
            nombre = st.text_input("Nombre de la materia")
            descripcion = st.text_area("Descripción")
            maestro_sel = st.selectbox("Maestro", maestros["nombre"] + " " + maestros["apellido"])
            horario_sel = st.selectbox("Horario", horarios)
            guardar = st.form_submit_button("Guardar")
            if guardar:
                maestro_id = maestros.loc[
                    (maestros["nombre"] + " " + maestros["apellido"]) == maestro_sel, "maestroid"
                ].iloc[0]
                conflicto = pd.read_sql("""
                    SELECT * FROM materias WHERE maestroid=:m AND horario=:h
                """, conn, params={"m": maestro_id, "h": horario_sel})
                if not conflicto.empty:
                    st.error("⚠️ El maestro ya tiene clase en ese horario.")
                else:
                    conn.execute(text("""
                        INSERT INTO materias (nombre, descripcion, maestroid, horario)
                        VALUES (:n, :d, :m, :h)
                    """), {"n": nombre, "d": descripcion, "m": maestro_id, "h": horario_sel})
                    conn.commit()
                    st.success("✅ Materia agregada correctamente.")
                    st.experimental_rerun()

        if not materias.empty:
            st.subheader("Editar o eliminar materia")
            mat_sel = st.selectbox("Selecciona materia", materias["nombre"])
            mat_id = materias.loc[materias["nombre"] == mat_sel, "materiaid"].iloc[0]
            accion = st.radio("Acción", ["Editar", "Eliminar"])
            if accion == "Editar":
                nuevo_nombre = st.text_input("Nuevo nombre")
                nueva_desc = st.text_area("Nueva descripción")
                if st.button("Guardar cambios"):
                    conn.execute(text("""
                        UPDATE materias SET nombre=:n, descripcion=:d WHERE materiaid=:id
                    """), {"n": nuevo_nombre, "d": nueva_desc, "id": mat_id})
                    conn.commit()
                    st.success("Materia actualizada.")
                    st.experimental_rerun()
            elif accion == "Eliminar":
                if st.button("Eliminar materia"):
                    conn.execute(text("DELETE FROM materias WHERE materiaid=:id"), {"id": mat_id})
                    conn.commit()
                    st.warning("Materia eliminada.")
                    st.experimental_rerun()

    # =================== ASISTENCIAS ===================
    elif seleccion == "📅 Asistencias":
        st.header("Registro de Asistencias")
        alumnos = pd.read_sql("SELECT matricula, nombre, apellido FROM alumnos", conn)
        maestros = pd.read_sql("SELECT maestroid, nombre, apellido FROM maestros", conn)
        asistencias = pd.read_sql("""
            SELECT a.asistenciaid, al.nombre AS alumno, ma.nombre AS maestro, a.fecha, a.estado
            FROM asistencias a
            JOIN alumnos al ON a.matricula = al.matricula
            JOIN maestros ma ON a.maestroid = ma.maestroid
            ORDER BY a.fecha DESC
        """, conn)
        st.dataframe(asistencias)

        with st.form("form_asistencia"):
            alumno_sel = st.selectbox("Alumno", alumnos["nombre"] + " " + alumnos["apellido"])
            maestro_sel = st.selectbox("Maestro", maestros["nombre"] + " " + maestros["apellido"])
            estado = st.selectbox("Estado", ["Presente", "Ausente", "Retardo"])
            fecha = st.date_input("Fecha", datetime.date.today())
            guardar = st.form_submit_button("Guardar")

            if guardar:
                alumno_id = alumnos.loc[
                    (alumnos["nombre"] + " " + alumnos["apellido"]) == alumno_sel, "matricula"
                ].iloc[0]
                maestro_id = maestros.loc[
                    (maestros["nombre"] + " " + maestros["apellido"]) == maestro_sel, "maestroid"
                ].iloc[0]
                conn.execute(text("""
                    INSERT INTO asistencias (matricula, maestroid, fecha, estado)
                    VALUES (:a, :m, :f, :e)
                """), {"a": alumno_id, "m": maestro_id, "f": fecha, "e": estado})
                conn.commit()
                st.success("Asistencia registrada.")
                st.experimental_rerun()

        if not asistencias.empty:
            st.subheader("Eliminar registro de asistencia")
            asis_sel = st.selectbox("Selecciona registro", asistencias["asistenciaid"])
            if st.button("Eliminar asistencia"):
                conn.execute(text("DELETE FROM asistencias WHERE asistenciaid=:id"), {"id": asis_sel})
                conn.commit()
                st.warning("Asistencia eliminada.")
                st.experimental_rerun()

    conn.close()

else:
    pantalla_login()
