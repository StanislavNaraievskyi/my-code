import asyncio
import csv
import hashlib
import os
import sqlite3
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

# 🔑 Токен бота та твій Chat ID
TELEGRAM_TOKEN = "8916527546:AAGzG2i9GZBCYlA9W7pmpiSZfdQLMC0uKUw"
MY_CHAT_ID = 6561129115

# 🔐 Налаштування безпеки (Хешування SHA-256)
RAW_PASSWORD = "stas_secret_pass"
ADMIN_PASSWORD_HASH = hashlib.sha256(RAW_PASSWORD.encode("utf-8")).hexdigest()


def check_auth(x_password: str = Header(None)):
    if not x_password:
        raise HTTPException(
            status_code=401, detail="Пароль не надано у заголовках!"
        )

    clean_pass = x_password.strip().strip('"').strip("'")
    user_hash = hashlib.sha256(clean_pass.encode("utf-8")).hexdigest()

    if user_hash != ADMIN_PASSWORD_HASH:
        raise HTTPException(
            status_code=401, detail="Невірний пароль доступу!"
        )


# 🛠️ Створення розширеної структури БД
def init_db():
    connection = sqlite3.connect("my_database.db")
    cursor = connection.cursor()

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        age INTEGER NOT NULL,
        email TEXT DEFAULT 'не вказано',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """
    )

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT NOT NULL,
        price REAL NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        user_id INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """
    )

    connection.commit()
    connection.close()


# 🤖 Telegram-бот з Inline-кнопками видалення
async def check_telegram_messages():
    offset = 0
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"

    while True:
        try:
            response = requests.get(
                telegram_url, params={"offset": offset, "timeout": 10}
            )
            if response.status_code == 200:
                data = response.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1

                    # 1. Обробка натискань на Inline-кнопки (видалення користувача)
                    if "callback_query" in update:
                        cb = update["callback_query"]
                        chat_id = cb.get("message", {}).get("chat", {}).get("id")
                        data_text = cb.get("data", "")
                        callback_id = cb.get("id")

                        if chat_id == MY_CHAT_ID and data_text.startswith(
                            "del_"
                        ):
                            user_id = int(data_text.split("_")[1])

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
                                reply_text = f"🗑️ Користувача {user_name} (ID: {user_id}) видалено!"
                            else:
                                reply_text = (
                                    f"❓ Користувача з ID {user_id} вже немає."
                                )

                            connection.close()

                            # Закриваємо годинник на кнопці в Telegram
                            requests.post(
                                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
                                json={
                                    "callback_query_id": callback_id,
                                    "text": reply_text,
                                },
                            )
                            # Відправляємо повідомлення про видалення
                            requests.post(
                                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                json={"chat_id": MY_CHAT_ID, "text": reply_text},
                            )

                    # 2. Обробка звичайних текстильних повідомлень та кнопок меню
                    elif "message" in update:
                        message = update["message"]
                        chat_id = message.get("chat", {}).get("id")
                        text = message.get("text", "")

                        if chat_id == MY_CHAT_ID:
                            # 🚀 Старт та головні кнопки
                            if text == "/start":
                                keyboard = {
                                    "keyboard": [
                                        [
                                            {"text": "📊 Статус БД"},
                                            {"text": "👥 Список користувачів"},
                                        ],
                                        [
                                            {"text": "📁 Завантажити CSV"},
                                            {"text": "ℹ️ Довідка"},
                                        ],
                                    ],
                                    "resize_keyboard": True,
                                }
                                requests.post(
                                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                    json={
                                        "chat_id": MY_CHAT_ID,
                                        "text": "Вітаю в адмін-панелі! Обирай дію на кнопках нижче 👇",
                                        "reply_markup": keyboard,
                                    },
                                )

                            # 👥 Список користувачів з кнопками видалення!
                            elif text in [
                                "/users",
                                "👥 Список користувачів",
                            ]:
                                connection = sqlite3.connect("my_database.db")
                                cursor = connection.cursor()
                                cursor.execute(
                                    "SELECT id, name, email FROM users"
                                )
                                users = cursor.fetchall()
                                connection.close()

                                if not users:
                                    requests.post(
                                        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                        json={
                                            "chat_id": MY_CHAT_ID,
                                            "text": "📭 База даних порожня.",
                                        },
                                    )
                                else:
                                    inline_keyboard = []
                                    msg_text = (
                                        "👥 **Список користувачів в БД:**\n\n"
                                    )

                                    for u in users:
                                        msg_text += f"• **ID: {u[0]}** | {u[1]} ({u[2]})\n"
                                        # Створюємо Inline-кнопку видалення під кожним користувачем
                                        inline_keyboard.append(
                                            [
                                                {
                                                    "text": f"❌ Видалити {u[1]} (ID: {u[0]})",
                                                    "callback_data": f"del_{u[0]}",
                                                }
                                            ]
                                        )

                                    requests.post(
                                        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                        json={
                                            "chat_id": MY_CHAT_ID,
                                            "text": msg_text,
                                            "parse_mode": "Markdown",
                                            "reply_markup": {
                                                "inline_keyboard": inline_keyboard
                                            },
                                        },
                                    )

                            # 📊 Звіт по кількості
                            elif text in ["/status", "📊 Статус БД"]:
                                connection = sqlite3.connect("my_database.db")
                                cursor = connection.cursor()
                                cursor.execute("SELECT COUNT(*) FROM users")
                                users_count = cursor.fetchone()[0]
                                cursor.execute("SELECT COUNT(*) FROM orders")
                                orders_count = cursor.fetchone()[0]
                                connection.close()

                                requests.post(
                                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                    json={
                                        "chat_id": MY_CHAT_ID,
                                        "text": f"📊 Звіт по БД:\n👤 Користувачів: {users_count}\n🛒 Замовлень: {orders_count}",
                                    },
                                )

                            # 📁 Експорт у CSV
                            elif text in ["/export", "📁 Завантажити CSV"]:
                                connection = sqlite3.connect("my_database.db")
                                cursor = connection.cursor()
                                cursor.execute(
                                    """
                                    SELECT users.id, users.name, users.age, users.email, users.created_at,
                                           IFNULL(orders.item_name, 'Немає покупок'), 
                                           IFNULL(orders.price, 0),
                                           IFNULL(orders.status, '-'),
                                           IFNULL(orders.created_at, '-')
                                    FROM users
                                    LEFT JOIN orders ON users.id = orders.user_id
                                """
                                )
                                rows = cursor.fetchall()
                                connection.close()

                                filename = "database_report.csv"
                                with open(
                                    filename,
                                    mode="w",
                                    newline="",
                                    encoding="utf-8",
                                ) as file:
                                    writer = csv.writer(file)
                                    writer.writerow(
                                        [
                                            "User ID",
                                            "Name",
                                            "Age",
                                            "Email",
                                            "User Created",
                                            "Item Name",
                                            "Price ($)",
                                            "Order Status",
                                            "Order Date",
                                        ]
                                    )
                                    writer.writerows(rows)

                                doc_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
                                with open(filename, "rb") as file_to_send:
                                    requests.post(
                                        doc_url,
                                        data={"chat_id": MY_CHAT_ID},
                                        files={"document": file_to_send},
                                    )

                                if os.path.exists(filename):
                                    os.remove(filename)

                            # ℹ️ Інструкція
                            elif text == "ℹ️ Довідка":
                                help_text = (
                                    "🛠 **Доступні дії:**\n\n"
                                    "• **📊 Статус БД** — загальна кількість записів.\n"
                                    "• **👥 Список користувачів** — перегляд списку з кнопками швидкого видалення.\n"
                                    "• **📁 Завантажити CSV** — вивантаження звітного файла."
                                )
                                requests.post(
                                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                                    json={
                                        "chat_id": MY_CHAT_ID,
                                        "text": help_text,
                                        "parse_mode": "Markdown",
                                    },
                                )

        except Exception as e:
            print(f"Помилка бота: {e}")

        await asyncio.sleep(1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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
    email: str = "не вказано"


class OrderInput(BaseModel):
    item_name: str
    price: float
    user_id: int
    status: str = "pending"


@app.get("/users")
def get_users_from_db(x_password: str = Header(None)):
    check_auth(x_password)

    connection = sqlite3.connect("my_database.db")
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT users.id, users.name, users.age, users.email, users.created_at,
               orders.item_name, orders.price, orders.status, orders.created_at
        FROM users
        LEFT JOIN orders ON users.id = orders.user_id
    """
    )
    data = cursor.fetchall()
    connection.close()
    return {"users_and_orders": data}


@app.post("/add-user")
def add_user_to_db(user: UserInput, x_password: str = Header(None)):
    check_auth(x_password)

    connection = sqlite3.connect("my_database.db")
    cursor = connection.cursor()
    cursor.execute(
        "INSERT INTO users (name, age, email) VALUES (?, ?, ?)",
        (user.name, user.age, user.email),
    )
    connection.commit()
    connection.close()

    text_message = f"🔔 Новий користувач!\n👤 Ім'я: {user.name}\n🎂 Вік: {user.age}\n📧 Email: {user.email}"
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(
        telegram_url, json={"chat_id": MY_CHAT_ID, "text": text_message}
    )

    return {"status": "success", "message": f"Користувача {user.name} додано!"}


@app.post("/add-order")
def add_order_to_db(order: OrderInput, x_password: str = Header(None)):
    check_auth(x_password)

    connection = sqlite3.connect("my_database.db")
    cursor = connection.cursor()

    cursor.execute("SELECT name FROM users WHERE id = ?", (order.user_id,))
    user = cursor.fetchone()

    if not user:
        connection.close()
        raise HTTPException(
            status_code=404, detail="Користувача з таким ID не існує!"
        )

    cursor.execute(
        "INSERT INTO orders (item_name, price, user_id, status) VALUES (?, ?, ?, ?)",
        (order.item_name, order.price, order.user_id, order.status),
    )
    connection.commit()
    connection.close()

    return {
        "status": "success",
        "message": f"Товар '{order.item_name}' за ${order.price} ({order.status}) додано до {user[0]}!",
    }