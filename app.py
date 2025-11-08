import streamlit as st
import pandas as pd
import bcrypt
from datetime import date
from streamlit_option_menu import option_menu
import sqlalchemy

# =========================================
# CONFIGURACIÓN PRINCIPAL
# =========================================
st.set_page_config(page_title="Control de Asistencias", layout="wide")

# Conexión a la base de datos PostgreSQL (Render)
DATABASE_URL = "postgresql://neondb_owner:npg_1f3sluIdFRyA@ep-solitary-meadow-adthlkqa-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def get_connection():
    engine = sqlalchemy.create_engine(DATABASE_URL)
    return engine.connect()

# =========================================
# CREACIÓN AUTOMÁTICA DE TABLAS (SI NO EXISTEN)
# =========================================
def crear_tablas():
    conn = get_connection()
    conn.execute(sqlalchemy.text("""
    CREATE TABLE IF NOT EXISTS Usuarios (
        UsuarioID SERIAL PRIMARY KEY,
        NombreUsuario VARCHAR(50) UNIQUE NOT NULL,
        Contrasena TEXT NOT NULL,
        Rol VARCHAR(20),
        Matricula INT,
        MaestroID INT
    );

    CREATE TABLE IF NOT EXISTS Alumnos (
        Matricula INT PRIMARY KEY,
        Nombre VARCHAR(50),
        Apellido VARCHAR(50)
    );

    CREATE TABLE IF NOT EXISTS Materias (
        MateriaID SERIAL PRIMARY KEY,
        Nombre VARCHAR(50),
        Descripcion TEXT
    );

    CREATE TABLE IF NOT EXISTS Maestros (
        MaestroID SERIAL PRIMARY KEY,
        Nombre VARCHAR(50),
        Apellido VARCHAR(50),
        MateriaID INT REFERENCES Materias(MateriaID) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS ClaseGrupo (
        ClaseGrupoID SERIAL PRIMARY KEY,
        MaestroID INT REFERENCES Maestros(MaestroID) ON DELETE CASCADE,
        Grupo VARCHAR(10),
        Horario VARCHAR(20)
    );

    CREATE TABLE IF NOT EXISTS Alumno_ClaseGrupo (
        Matricula INT REFERENCES Alumnos(Matricula) ON DELETE CASCADE,
        ClaseGrupoID INT REFERENCES ClaseGrupo(ClaseGrupoID) ON DELETE CASCADE,
        PRIMARY KEY (Matricula, ClaseGrupoID)
    );

    CREATE TABLE IF NOT EXISTS Asistencias (
        AsistenciaID SERIAL PRIMARY KEY,
        Matricula INT REFERENCES Alumnos(Matricula) ON DELETE CASCADE,
        ClaseGrupoID INT REFERENCES ClaseGrupo(ClaseGrupoID) ON DELETE CASCADE,
        Fecha DATE,
        Estado VARCHAR(20)
    );
    """))
    conn.commit()
    conn.close()

# Ejecutar automáticamente al inicio
crear_tablas()

# =========================================
# FUNCIONES DE BASE DE DATOS
# =========================================
def ejecutar_sql(query, params=None):
    conn = get_connection()
    if params:
        conn.execute(sqlalchemy.text(query), params)
    else:
        conn.execute(sqlalchemy.text(query))
    conn.commit()
    conn.close()

def obtener_datos(query):
    conn = get_connection()
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# =========================================
# FUNCIONES DE USUARIOS
# =========================================
def verificar_usuario(nombre_usuario, contrasena):
    conn = get_connection()
    result = conn.execute(sqlalchemy.text("SELECT * FROM Usuarios WHERE NombreUsuario = :usuario"), {"usuario": nombre_usuario}).fetchone()
    conn.close()
    if result:
        hashed = result[2].encode('utf-8')
        if bcrypt.checkpw(contrasena.encode('utf-8'), hashed):
            return {
                "UsuarioID": result[0],
                "NombreUsuario": result[1],
                "Rol": result[3],
                "Matricula": result[4],
                "MaestroID": result[5]
            }
    return None

def registrar_usuario(nombre_usuario, contrasena, rol, matricula=None, maestro_id=None):
    conn = get_connection()
    existente = conn.execute(sqlalchemy.text("SELECT * FROM Usuarios WHERE NombreUsuario = :usuario"), {"usuario": nombre_usuario}).fetchone()
    if existente:
        conn.close()
        return "⚠️ El nombre de usuario ya existe."
    hashed = bcrypt.hashpw(contrasena.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    conn.execute(sqlalchemy.text("""
        INSERT INTO Usuarios (NombreUsuario, Contrasena, Rol, Matricula, MaestroID)
        VALUES (:nombre, :contrasena, :rol, :matricula, :maestroid)
    """), {"nombre": nombre_usuario, "contrasena": hashed, "rol": rol, "matricula": matricula, "maestroid": maestro_id})
    conn.commit()
    conn.close()
    return "✅ Usuario registrado correctamente."

# =========================================
# FUNCIONES DE ELIMINACIÓN
# =========================================
def eliminar_alumno(matricula):
    ejecutar_sql("DELETE FROM Asistencias WHERE Matricula = :m", {"m": matricula})
    ejecutar_sql("DELETE FROM Alumno_ClaseGrupo WHERE Matricula = :m", {"m": matricula})
    ejecutar_sql("DELETE FROM Alumnos WHERE Matricula = :m", {"m": matricula})

def eliminar_maestro(maestro_id):
    ejecutar_sql("DELETE FROM ClaseGrupo WHERE MaestroID = :m", {"m": maestro_id})
    ejecutar_sql("DELETE FROM Maestros WHERE MaestroID = :m", {"m": maestro_id})

def eliminar_materia(materia_id):
    ejecutar_sql("DELETE FROM Maestros WHERE MateriaID = :m", {"m": materia_id})
    ejecutar_sql("DELETE FROM Materias WHERE MateriaID = :m", {"m": materia_id})

# =========================================
# LOGIN Y REGISTRO
# =========================================
if "usuario" not in st.session_state:
    st.session_state.usuario = None

if st.session_state.usuario is None:
    st.image("https://cdn-icons-png.flaticon.com/512/2922/2922510.png", width=100)
    st.title("🎓 Sistema de Control de Asistencias")

    tab_login, tab_registro = st.tabs(["🔐 Iniciar Sesión", "🆕 Crear Cuenta"])

    with tab_login:
        usuario = st.text_input("👤 Usuario")
        contrasena = st.text_input("🔒 Contraseña", type="password")
        if st.button("Iniciar Sesión"):
            user = verificar_usuario(usuario, contrasena)
            if user:
                st.session_state.usuario = user
                st.success(f"Bienvenido, {user['NombreUsuario']} 👋 ({user['Rol']})")
                st.rerun()
            else:
                st.error("❌ Usuario o contraseña incorrectos")

    with tab_registro:
        nuevo_usuario = st.text_input("👤 Nuevo nombre de usuario")
        nueva_contrasena = st.text_input("🔒 Nueva contraseña", type="password")
        rol_sel = st.selectbox("🎭 Rol", ["profesor", "alumno"])

        if rol_sel == "alumno":
            matriculas = obtener_datos("SELECT Matricula, Nombre || ' ' || Apellido AS NombreCompleto FROM Alumnos")
            matricula_sel = st.selectbox("Selecciona tu matrícula", matriculas["Matricula"]) if not matriculas.empty else None
            maestro_sel = None
        else:
            maestros = obtener_datos("SELECT MaestroID, Nombre || ' ' || Apellido AS NombreCompleto FROM Maestros")
            maestro_sel = st.selectbox("Selecciona tu nombre", maestros["NombreCompleto"]) if not maestros.empty else None
            matricula_sel = None

        if st.button("🆕 Crear Cuenta"):
            if not nuevo_usuario or not nueva_contrasena:
                st.error("❌ Debes llenar todos los campos.")
            else:
                maestro_id = None
                matricula = None
                if rol_sel == "profesor" and maestro_sel:
                    maestro_id = int(maestros.loc[maestros["NombreCompleto"] == maestro_sel, "MaestroID"].iloc[0])
                elif rol_sel == "alumno" and matricula_sel:
                    matricula = int(matriculas.loc[matriculas["Matricula"] == matricula_sel, "Matricula"].iloc[0])
                resultado = registrar_usuario(nuevo_usuario, nueva_contrasena, rol_sel, matricula, maestro_id)
                st.success(resultado if "✅" in resultado else resultado)

    st.stop()

# =========================================
# MENÚ PRINCIPAL
# =========================================
usuario_actual = st.session_state.usuario
rol = usuario_actual["Rol"]

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2922/2922510.png", width=100)
    st.title(f"👋 Bienvenido, {usuario_actual['NombreUsuario']}")
    if rol == "profesor":
        opciones = ["Inicio", "Maestros", "Alumnos", "Materias", "Clases", "Asignar Alumnos", "Consultar Clases", "Asistencias"]
    else:
        opciones = ["Inicio", "Mis Clases", "Mis Asistencias"]
    selected = option_menu("Menú Principal", options=opciones, icons=["house", "book", "people"], menu_icon="cast", default_index=0)
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.usuario = None
        st.rerun()

# =========================================
# SECCIONES PRINCIPALES
# =========================================
if selected == "Inicio":
    st.title("🎓 Sistema de Control de Asistencias")
    st.markdown("Administra alumnos, maestros, materias y asistencias con inicio de sesión y control de roles.")
    st.image("https://cdn-icons-png.flaticon.com/512/2947/2947985.png", width=400)

