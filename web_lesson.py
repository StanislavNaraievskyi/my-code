import asyncio
import sqlite3
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

TELEGRAM_TOKEN = "8916527546:AAGzG2i9GZBCYlA9W7pmpiSZfdQLMC0uKUw"
MY_CHAT_ID = 6561129115

#  Секретний пароль адміна
ADMIN_PASSWORD = "stas_secret_pass"


async def check_telegram_messages():
    offset = 0
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"

    print("🤖 Бот-асистент запущений і слухає команди в Telegram...")

    while True:
        try:
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

                    if chat_id == MY_CHAT_ID:
                        if text == "/status":
                            connection = sqlite3.connect("my_database.db")
                            cursor = connection.cursor()
                            cursor.execute("SELECT COUNT(*) FROM users")
                            count = cursor.fetchone()[0]
                            connection.close()

                            reply_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                            requests.post(
                                reply_url,
                                json={
                                    "chat_id": MY_CHAT_ID,
                                    "text": f" Звіт по БД:\nНаразі в базі даних зареєстровано користувачів: {count} 👤",
                                },
                            )

                        elif text.startswith("/delete "):
                            parts = text.split(" ")
                            if len(parts) == 2 and parts[1].isdigit():
                                user_id = int(parts[1])
                                connection = sqlite3.connect("my_database.db")
                                cursor = connection.cursor()
                                cursor.execute(
                                    "SELECT name FROM users WHERE id = ?",
                                    (user_id,),
                                )
                                user = cursor.fetchone()

                                if user:
                                    user_name = user[0]
                                    cursor.execute(
                                        "DELETE FROM users WHERE id = ?",
                                        (user_id,),
                                    )
                                    connection.commit()
                                    reply_text = f"🗑️ Користувача {user_name} (ID: {user_id}) успішно видалено з бази!"
                                else:
                                    reply_text = f"❓ Користувача з ID {user_id} не знайдено в базі даних."

                                connection.close()
                            else:
                                reply_text = "⚠️ Неправильний формат! Пиши так: /delete [номер_ID]"

                            reply_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                            requests.post(
                                reply_url,
                                json={
                                    "chat_id": MY_CHAT_ID,
                                    "text": reply_text,
                                },
                            )

        except Exception as e:
            print(f"Помилка бота: {e}")

        await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
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


#  ПЕРЕВІРКА ПАРОЛЯ У ЗАГОЛОВКАХ
@app.get("/users")
def get_users_from_db(x_password: str = Header(None)):
    if x_password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=401, detail="Невірний пароль доступу!"
        )

    connection = sqlite3.connect("my_database.db")
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM users")
    all_users = cursor.fetchall()
    connection.close()
    return {"users_in_database": all_users}


#  ПЕРЕВІРКА ПАРОЛЯ ДЛЯ ДОДАВАННЯ
@app.post("/add-user")
def add_user_to_db(user: UserInput, x_password: str = Header(None)):
    if x_password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=401, detail="Невірний пароль доступу!"
        )

    connection = sqlite3.connect("my_database.db")
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO users (name, age) VALUES (?, ?)", (user.name, user.age)
    )
    connection.commit()
    connection.close()

    text_message = f"🔔 Новий користувач на сайті!\n👤 Ім'я: {user.name}\n🎂 Вік: {user.age}"
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(
        telegram_url, json={"chat_id": MY_CHAT_ID, "text": text_message}
    )

    return {"status": "success", "message": f"Користувача {user.name} додано!"}