import streamlit as st
import pandas as pd
import sqlalchemy
from streamlit_option_menu import option_menu

# =========================================
# CONFIGURACIÓN INICIAL
# =========================================
st.set_page_config(page_title="Control de Asistencias", layout="wide")

st.markdown("""
<style>
h1, h2, h3 {
    color: #1565C0;
    font-family: 'Segoe UI Black';
}
[data-testid="stSidebar"] {
    background-color: #E3F2FD;
}
</style>
""", unsafe_allow_html=True)

# =========================================
# CONEXIÓN A LA BASE DE DATOS (Neon)
# =========================================
DATABASE_URL = 'postgresql://neondb_owner:npg_1f3sluIdFRyA@ep-solitary-meadow-adthlkqa-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

def get_connection():
    engine = sqlalchemy.create_engine(DATABASE_URL)
    return engine.connect()

# =========================================
# CREACIÓN AUTOMÁTICA DE TABLAS
# =========================================
def crear_tablas():
    conn = get_connection()
    conn.execute(sqlalchemy.text("""
    CREATE TABLE IF NOT EXISTS Usuarios (
        UsuarioID SERIAL PRIMARY KEY,
        NombreUsuario VARCHAR(50) UNIQUE NOT NULL,
        Contrasena TEXT NOT NULL,
        Rol VARCHAR(20)
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
    CREATE TABLE IF NOT EXISTS Asistencias (
        AsistenciaID SERIAL PRIMARY KEY,
        Matricula INT REFERENCES Alumnos(Matricula) ON DELETE CASCADE,
        MaestroID INT REFERENCES Maestros(MaestroID) ON DELETE CASCADE,
        Fecha DATE,
        Estado VARCHAR(20)
    );
    """))
    conn.commit()
    conn.close()

crear_tablas()

# =========================================
# MENÚ LATERAL
# =========================================
with st.sidebar:
    seleccion = option_menu(
        "Menú Principal",
        ["Inicio", "Alumnos", "Maestros", "Materias", "Asistencias"],
        icons=["house", "people", "person-badge", "book", "check2-circle"]
    )

# =========================================
# SECCIÓN INICIO
# =========================================
if seleccion == "Inicio":
    st.title("📘 Sistema de Control de Asistencias")
    st.markdown("Bienvenido al sistema. Usa el menú lateral para navegar.")

# =========================================
# SECCIÓN ALUMNOS
# =========================================
elif seleccion == "Alumnos":
    st.header("👨‍🎓 Registro de Alumnos")

    try:
        conn = get_connection()
        df = pd.read_sql("SELECT * FROM Alumnos", conn)
        conn.close()

        st.subheader("Lista de alumnos")
        if df.empty:
            st.info("No hay alumnos registrados todavía.")
        else:
            st.dataframe(df)

        st.subheader("Agregar nuevo alumno")
        with st.form("form_alumno"):
            matricula = st.text_input("Matrícula")
            nombre = st.text_input("Nombre")
            apellido = st.text_input("Apellido")
            submit = st.form_submit_button("Guardar")

            if submit:
                if matricula and nombre and apellido:
                    conn = get_connection()
                    conn.execute(sqlalchemy.text("""
                        INSERT INTO Alumnos (Matricula, Nombre, Apellido)
                        VALUES (:mat, :nom, :ape)
                    """), {"mat": matricula, "nom": nombre, "ape": apellido})
                    conn.commit()
                    conn.close()
                    st.success("✅ Alumno agregado correctamente.")
                else:
                    st.warning("Completa todos los campos.")
    except Exception as e:
        st.error(f"Ocurrió un error: {e}")

# =========================================
# SECCIÓN MATERIAS
# =========================================
elif seleccion == "Materias":
    st.header("📚 Registro de Materias")

    try:
        conn = get_connection()
        df = pd.read_sql("SELECT * FROM Materias", conn)
        conn.close()

        st.subheader("Lista de materias")
        if df.empty:
            st.info("No hay materias registradas todavía.")
        else:
            st.dataframe(df)

        st.subheader("Agregar nueva materia")
        with st.form("form_materia"):
            nombre = st.text_input("Nombre de la materia")
            descripcion = st.text_area("Descripción")
            submit = st.form_submit_button("Guardar")

            if submit:
                if nombre:
                    conn = get_connection()
                    conn.execute(sqlalchemy.text("""
                        INSERT INTO Materias (Nombre, Descripcion)
                        VALUES (:nom, :desc)
                    """), {"nom": nombre, "desc": descripcion})
                    conn.commit()
                    conn.close()
                    st.success("✅ Materia agregada correctamente.")
                else:
                    st.warning("El nombre es obligatorio.")
    except Exception as e:
        st.error(f"Ocurrió un error: {e}")

# =========================================
# SECCIÓN MAESTROS
# =========================================
elif seleccion == "Maestros":
    st.header("👨‍🏫 Registro de Maestros")

    try:
        conn = get_connection()
        materias = pd.read_sql("SELECT * FROM Materias", conn)
        maestros = pd.read_sql("""
            SELECT Maestros.MaestroID, Maestros.Nombre, Maestros.Apellido, Materias.Nombre AS Materia
            FROM Maestros
            LEFT JOIN Materias ON Maestros.MateriaID = Materias.MateriaID
        """, conn)
        conn.close()

        st.subheader("Lista de maestros")
        if maestros.empty:
            st.info("No hay maestros registrados todavía.")
        else:
            st.dataframe(maestros)

        st.subheader("Agregar nuevo maestro")
        if materias.empty:
            st.warning("Primero registra una materia.")
        else:
            with st.form("form_maestro"):
                nombre = st.text_input("Nombre")
                apellido = st.text_input("Apellido")
                materia_sel = st.selectbox("Materia asignada", materias["Nombre"])
                submit = st.form_submit_button("Guardar")

                if submit:
                    materia_id = materias.loc[materias["Nombre"] == materia_sel, "MateriaID"].iloc[0]
                    conn = get_connection()
                    conn.execute(sqlalchemy.text("""
                        INSERT INTO Maestros (Nombre, Apellido, MateriaID)
                        VALUES (:nom, :ape, :mat)
                    """), {"nom": nombre, "ape": apellido, "mat": materia_id})
                    conn.commit()
                    conn.close()
                    st.success("✅ Maestro agregado correctamente.")
    except Exception as e:
        st.error(f"Ocurrió un error: {e}")

# =========================================
# SECCIÓN ASISTENCIAS
# =========================================
elif seleccion == "Asistencias":
    st.header("📅 Registro de Asistencias")

    try:
        conn = get_connection()
        alumnos = pd.read_sql("SELECT * FROM Alumnos", conn)
        maestros = pd.read_sql("SELECT * FROM Maestros", conn)
        conn.close()

        if alumnos.empty or maestros.empty:
            st.warning("⚠️ Debes registrar al menos un alumno y un maestro.")
        else:
            alumno_sel = st.selectbox("Selecciona Alumno", alumnos["Nombre"])
            maestro_sel = st.selectbox("Selecciona Maestro", maestros["Nombre"])
            estado = st.selectbox("Estado de Asistencia", ["Presente", "Ausente", "Justificado"])
            fecha = st.date_input("Fecha")

            if st.button("Registrar asistencia"):
                mat = alumnos.loc[alumnos["Nombre"] == alumno_sel, "Matricula"].iloc[0]
                maestroid = maestros.loc[maestros["Nombre"] == maestro_sel, "MaestroID"].iloc[0]
                conn = get_connection()
                conn.execute(sqlalchemy.text("""
                    INSERT INTO Asistencias (Matricula, MaestroID, Fecha, Estado)
                    VALUES (:mat, :mae, :fec, :est)
                """), {"mat": mat, "mae": maestroid, "fec": fecha, "est": estado})
                conn.commit()
                conn.close()
                st.success("✅ Asistencia registrada correctamente.")

        st.subheader("Historial de asistencias")
        conn = get_connection()
        asist = pd.read_sql("""
            SELECT a.AsistenciaID, al.Nombre AS Alumno, ma.Nombre AS Maestro, a.Fecha, a.Estado
            FROM Asistencias a
            JOIN Alumnos al ON a.Matricula = al.Matricula
            JOIN Maestros ma ON a.MaestroID = ma.MaestroID
            ORDER BY a.Fecha DESC
        """, conn)
        conn.close()

        if asist.empty:
            st.info("No hay asistencias registradas.")
        else:
            st.dataframe(asist)

    except Exception as e:
        st.error(f"Ocurrió un error: {e}")


