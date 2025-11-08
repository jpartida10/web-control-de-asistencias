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
# ⚠️ Sustituye esta línea con tu URL real de Neon (incluyendo ?sslmode=require)
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
    CREATE TABLE IF NOT EXISTS Maestros (
        MaestroID SERIAL PRIMARY KEY,
        Nombre VARCHAR(50),
        Apellido VARCHAR(50)
    );
    CREATE TABLE IF NOT EXISTS Materias (
        MateriaID SERIAL PRIMARY KEY,
        Nombre VARCHAR(50),
        Descripcion TEXT,
        MaestroID INT REFERENCES Maestros(MaestroID) ON DELETE SET NULL,
        Horario VARCHAR(20)
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
# SECCIÓN MAESTROS
# =========================================
elif seleccion == "Maestros":
    st.header("👨‍🏫 Registro de Maestros")

    try:
        conn = get_connection()
        maestros = pd.read_sql("SELECT * FROM Maestros", conn)
        conn.close()

        st.subheader("Lista de maestros")
        if maestros.empty:
            st.info("No hay maestros registrados todavía.")
        else:
            st.dataframe(maestros)

        st.subheader("Agregar nuevo maestro")
        with st.form("form_maestro"):
            nombre = st.text_input("Nombre")
            apellido = st.text_input("Apellido")
            submit = st.form_submit_button("Guardar")

            if submit:
                if nombre and apellido:
                    conn = get_connection()
                    conn.execute(sqlalchemy.text("""
                        INSERT INTO Maestros (Nombre, Apellido)
                        VALUES (:nom, :ape)
                    """), {"nom": nombre, "ape": apellido})
                    conn.commit()
                    conn.close()
                    st.success("✅ Maestro agregado correctamente.")
                else:
                    st.warning("Completa todos los campos.")
    except Exception as e:
        st.error(f"Ocurrió un error: {e}")

# =========================================
# SECCIÓN MATERIAS (con maestro, horario, editar y eliminar)
# =========================================
elif seleccion == "Materias":
    st.header("📚 Registro de Materias")

    try:
        conn = get_connection()
        maestros = pd.read_sql("SELECT MaestroID, Nombre, Apellido FROM Maestros", conn)
        materias = pd.read_sql("""
            SELECT m.MateriaID, m.Nombre, m.Descripcion, 
                   ma.Nombre AS Maestro, m.Horario
            FROM Materias m
            LEFT JOIN Maestros ma ON m.MaestroID = ma.MaestroID
            ORDER BY m.MateriaID
        """, conn)
        conn.close()

        st.subheader("Lista de materias registradas")
        if materias.empty:
            st.info("No hay materias registradas todavía.")
        else:
            st.dataframe(materias)

            # Opciones de editar o eliminar
            st.subheader("Editar o eliminar materia existente")
            materia_sel = st.selectbox("Selecciona una materia", materias["Nombre"])
            materia_id = materias.loc[materias["Nombre"] == materia_sel, "MateriaID"].iloc[0]

            accion = st.radio("Acción a realizar", ["Editar", "Eliminar"])

            if accion == "Editar":
                st.write("✏️ **Editar materia seleccionada**")

                horarios = [
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

                with st.form("form_editar_materia"):
                    nuevo_nombre = st.text_input("Nuevo nombre", materia_sel)
                    nueva_desc = st.text_area("Nueva descripción")
                    horario_sel = st.selectbox("Selecciona horario", horarios)
                    maestro_sel = st.selectbox(
                        "Selecciona maestro",
                        maestros["Nombre"] + " " + maestros["Apellido"]
                    )
                    maestro_id = maestros.loc[
                        (maestros["Nombre"] + " " + maestros["Apellido"]) == maestro_sel,
                        "MaestroID"
                    ].iloc[0]
                    submit_edit = st.form_submit_button("Guardar cambios")

                    if submit_edit:
                        conn = get_connection()
                        conn.execute(sqlalchemy.text("""
                            UPDATE Materias
                            SET Nombre = :nom, Descripcion = :desc, 
                                MaestroID = :mae, Horario = :hor
                            WHERE MateriaID = :id
                        """), {
                            "nom": nuevo_nombre,
                            "desc": nueva_desc,
                            "mae": maestro_id,
                            "hor": horario_sel,
                            "id": materia_id
                        })
                        conn.commit()
                        conn.close()
                        st.success("✅ Materia actualizada correctamente.")

            elif accion == "Eliminar":
                if st.button("🗑️ Eliminar materia"):
                    conn = get_connection()
                    conn.execute(sqlalchemy.text("DELETE FROM Materias WHERE MateriaID = :id"), {"id": materia_id})
                    conn.commit()
                    conn.close()
                    st.warning("❌ Materia eliminada correctamente. Recarga la página para ver los cambios.")

        st.subheader("Agregar nueva materia")

        horarios = [
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

        with st.form("form_materia"):
            nombre = st.text_input("Nombre de la materia")
            descripcion = st.text_area("Descripción")

            if maestros.empty:
                st.warning("⚠️ No hay maestros registrados todavía. Agrega uno antes de crear materias.")
                maestro_id = None
            else:
                maestro_sel = st.selectbox(
                    "Selecciona el maestro que impartirá la materia",
                    maestros["Nombre"] + " " + maestros["Apellido"]
                )
                maestro_id = maestros.loc[
                    (maestros["Nombre"] + " " + maestros["Apellido"]) == maestro_sel,
                    "MaestroID"
                ].iloc[0]

            horario_sel = st.selectbox("Selecciona horario", horarios)
            submit = st.form_submit_button("Guardar")

            if submit:
                if not nombre:
                    st.warning("⚠️ El nombre de la materia es obligatorio.")
                elif maestro_id is None:
                    st.warning("⚠️ Debes registrar al menos un maestro antes.")
                else:
                    conn = get_connection()
                    conn.execute(sqlalchemy.text("""
                        INSERT INTO Materias (Nombre, Descripcion, MaestroID, Horario)
                        VALUES (:nom, :desc, :mae, :hor)
                    """), {
                        "nom": nombre,
                        "desc": descripcion,
                        "mae": maestro_id,
                        "hor": horario_sel
                    })
                    conn.commit()
                    conn.close()
                    st.success("✅ Materia agregada correctamente.")
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
