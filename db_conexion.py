import sqlalchemy

# URL que Render te proporciona
DATABASE_URL = "postgresql://neondb_owner:npg_1f3sluIdFRyA@ep-solitary-meadow-adthlkqa-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
def get_connection():
    engine = sqlalchemy.create_engine(DATABASE_URL)
    return engine.connect()
