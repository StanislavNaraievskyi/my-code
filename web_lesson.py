import sqlite3
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel  # Інструмент для перевірки даних

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Створюємо модель: кажемо Python, які саме дані ми чекаємо з сайту
class UserInput(BaseModel):
    name: str
    age: int


@app.get("/users")
def get_users_from_db():
    connection = sqlite3.connect("my_database.db")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM users")
    all_users = cursor.fetchall()
    connection.close()
    return {"users_in_database": all_users}


# ➕ НОВИЙ МЕТОД: Додавання користувача через сайт
@app.post("/add-user")
def add_user_to_db(user: UserInput):
    connection = sqlite3.connect("my_database.db")
    cursor = connection.cursor()

    # Записуємо отримані з сайту ім'я та вік у таблицю
    cursor.execute(
        "INSERT INTO users (name, age) VALUES (?, ?)", (user.name, user.age)
    )
    connection.commit()
    connection.close()

    return {"status": "success", "message": f"Користувача {user.name} додано!"}