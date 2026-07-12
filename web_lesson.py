import sqlite3
from fastapi import FastAPI

app = FastAPI()


# Нова сторінка, яка покаже користувачів із бази даних
@app.get("/users")
def get_users_from_db():
    # 1. Підключаємося до нашої бази даних
    connection = sqlite3.connect("my_database.db")
    cursor = connection.cursor()

    # 2. Беремо всіх користувачів
    cursor.execute("SELECT * FROM users")
    all_users = cursor.fetchall()

    # 3. Закриваємо з'єднання
    connection.close()

    # 4. Повертаємо цей список у браузер!
    return {"users_in_database": all_users}