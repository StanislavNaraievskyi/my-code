import sqlite3
import asyncio
from contextlib import asynccontextmanager
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Твої секретні ключі, які ми вже перевірили
TELEGRAM_TOKEN = "8916527546:AAGzG2i9GZBCYlA9W7pmpiSZfdQLMC0uKUw"
MY_CHAT_ID = 6561129115  # Твій ID як число


# Функція, яка буде постійно перевіряти нові повідомлення в Telegram
async def check_telegram_messages():
    offset = 0
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"

    print("🤖 Бот-асистент запущений і слухає команди в Telegram...")

    while True:
        try:
            # Запитуємо нові повідомлення (чекаємо до 10 секунд, якщо повідомлень немає)
            response = requests.get(
                telegram_url, params={"offset": offset, "timeout": 10}
            )
            if response.status_code == 200:
                data = response.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    message = update.get("message", {})
                    chat_id = message.get("chat", {}).get("id")
                    text = message.get("text", "")

                    # Перевіряємо, чи пише саме власник (ти) і яка команда прийшла
                    if chat_id == MY_CHAT_ID:
                        if text == "/status":
                            # Ідемо в базу даних рахувати користувачів
                            connection = sqlite3.connect("my_database.db")
                            cursor = connection.cursor()
                            cursor.execute("SELECT COUNT(*) FROM users")
                            count = cursor.fetchone()[0]
                            connection.close()

                            # Відправляємо відповідь назад у Telegram
                            reply_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                            requests.post(
                                reply_url,
                                json={
                                    "chat_id": MY_CHAT_ID,
                                    "text": f"📊 Звіт по БД:\nНаразі в базі даних зареєстровано користувачів: {count} 👤",
                                },
                            )

        except Exception as e:
            print(f"Помилка бота: {e}")

        # Невеликий перепочинок, щоб не перевантажувати процесор
        await asyncio.sleep(1)


# Налаштовуємо FastAPI, щоб бот запускався одночасно з сервером
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Запускаємо бота у фоновому режимі
    asyncio.create_task(check_telegram_messages())
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.post("/add-user")
def add_user_to_db(user: UserInput):
    connection = sqlite3.connect("my_database.db")
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO users (name, age) VALUES (?, ?)", (user.name, user.age)
    )
    connection.commit()
    connection.close()

    text_message = f"🔔 Новий користувач на сайті!\n👤 Ім'я: {user.name}\n🎂 Вік: {user.age}"
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(telegram_url, json={"chat_id": MY_CHAT_ID, "text": text_message})

    return {"status": "success", "message": f"Користувача {user.name} додано!"}