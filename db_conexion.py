import sqlalchemy

# URL que Render te proporciona
DATABASE_URL = "postgresql://asistencia_db_c026_user:Tj2lei1PKAv1jmrAnplSMBRFldW3FHhk@dpg-d47pamshg0os73frp270-a/asistencia_db_c026"
def get_connection():
    engine = sqlalchemy.create_engine(DATABASE_URL)
    return engine.connect()
