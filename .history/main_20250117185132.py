
import os
import time
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import mysql.connector
from mysql.connector import Error
from typing import Generator
from dotenv import load_dotenv  # Importar dotenv

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Crear instancia de FastAPI
app = FastAPI()

# Configuración de la base de datos MySQL
DATABASE_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "user": os.getenv("DB_USER", "administrador"),
    "password": os.getenv("DB_PASSWORD", "Duplauto15@"),
    "database": os.getenv("DB_NAME", "users_db")
}

# Función para obtener la conexión a MySQL
def get_db_connection() -> Generator:
    conn = None
    try:
        conn = mysql.connector.connect(**DATABASE_CONFIG)
        if conn.is_connected():
            yield conn
    except Error as e:
        print(f"Error al conectar con la base de datos: {e}")
        raise HTTPException(status_code=500, detail="Error de conexión con la base de datos")
    finally:
        if conn and conn.is_connected():
            conn.close()

# Inicializar la base de datos (crear tablas si no existen)
def init_db():
    retries = 5  # Intentos de conexión
    while retries > 0:
        try:
            conn = mysql.connector.connect(
                host=DATABASE_CONFIG["host"],
                user=DATABASE_CONFIG["user"],
                password=DATABASE_CONFIG["password"]
            )
            if conn.is_connected():
                cursor = conn.cursor()
                # Crear la base de datos si no existe
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DATABASE_CONFIG['database']}")
                conn.database = DATABASE_CONFIG["database"]
                # Crear la tabla de usuarios si no existe
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INT PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        email VARCHAR(255) NOT NULL UNIQUE
                    )
                """)
                conn.commit()
                print("Base de datos inicializada correctamente")
                break
        except Error as e:
            print(f"Intento fallido de inicializar la base de datos: {e}")
            retries -= 1
            time.sleep(5)
        finally:
            if conn and conn.is_connected():
                cursor.close()
                conn.close()
    else:
        raise Exception("No se pudo conectar a la base de datos después de varios intentos")

# Modelos Pydantic
class User(BaseModel):
    id: int
    name: str
    email: str

# Inicializar la base de datos al arrancar la aplicación
@app.on_event("startup")
def startup():
    init_db()

# Rutas
@app.get("/")
def read_root():
    return {"message": "Bienvenido a la API de usuarios con MySQL"}

@app.post("/users/", response_model=User)
def create_user(user: User, db: mysql.connector.MySQLConnection = Depends(get_db_connection)):
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(
            "INSERT INTO users (id, name, email) VALUES (%s, %s, %s)",
            (user.id, user.name, user.email)
        )
        db.commit()
        return user
    except mysql.connector.IntegrityError:
        raise HTTPException(status_code=400, detail="El usuario ya existe")
    finally:
        cursor.close()

@app.get("/users/{user_id}", response_model=User)
def read_user(user_id: int, db: mysql.connector.MySQLConnection = Depends(get_db_connection)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return User(id=user["id"], name=user["name"], email=user["email"])

@app.delete("/users/{user_id}", response_model=User)
def delete_user(user_id: int, db: mysql.connector.MySQLConnection = Depends(get_db_connection)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    db.commit()
    return User(id=user["id"], name=user["name"], email=user["email"])

# Endpoint de verificación de salud
@app.get("/health")
def health_check():
    return {"status": "ok"}
