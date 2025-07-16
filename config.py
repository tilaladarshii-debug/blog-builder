import os

DATABASE_CONFIG = {
    'dbname': 'postgres',
    'user': 'postgres',
    'password': 'dt11',
    'host': 'localhost',
    'port': '5432'
}

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'static/uploads')
SECRET_KEY = 'd27'
