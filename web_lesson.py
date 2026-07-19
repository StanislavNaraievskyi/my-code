import requests
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


# ➕ ОНОВЛЕНИЙ МЕТОД: Додавання користувача + сповіщення в Telegram
@app.post("/add-user")
def add_user_to_db(user: UserInput):
    # 1. Записуємо в базу даних SQLite (як і раніше)
    connection = sqlite3.connect("my_database.db")
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO users (name, age) VALUES (?, ?)", (user.name, user.age)
    )
    connection.commit()
    connection.close()

    # 2. НАДВИЛЬ БОТА: Відправляємо сповіщення в Telegram!
    TELEGRAM_TOKEN = "8916527546:AAGzG2i9GZBCYlA9W7pmpiSZfdQLMC0uKUw"
    MY_CHAT_ID = "6561129115"
    text_message = (
        f"🔔 Новий користувач на сайті!\n👤 Ім'я: {user.name}\n🎂 Вік: {user.age}"
    )

    # Формуємо запит до серверів Telegram
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": MY_CHAT_ID, "text": text_message}

    try:
        # Надсилаємо запит за допомогою бібліотеки requests
        requests.post(telegram_url, json=payload)
    except Exception as e:
        print(f"Не вдалося надіслати сповіщення в Telegram: {e}")

    return {"status": "success", "message": f"Користувача {user.name} додано!"}
# 📈 НОВИЙ МЕТОД: Запит до реального світового API курсу валют
@app.get("/crypto-rate")
def get_crypto_rate():
    # Стукаємо до безкоштовного публічного API курсів валют
    url = "https://open.er-api.com/v6/latest/EUR"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        # Забираємо курс долара (USD) відносно євро
        usd_rate = data["rates"]["USD"]
        return {
            "status": "success",
            "currency": "EUR to USD",
            "rate": usd_rate,
        }
    else:
        return {"status": "error", "message": "Не вдалося отримати курс"}