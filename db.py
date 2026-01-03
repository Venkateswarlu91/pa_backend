import pymysql

def get_db_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="Venkateswarlu@91",
        database="pa_db",
        cursorclass=pymysql.cursors.DictCursor
    )
