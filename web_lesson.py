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

    # Таблиця користувачів з поштою та датою реєстрації
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

    # Таблиця замовлень зі статусом та датою створення
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


# 🤖 Telegram-бот із кнопковим меню та виправленим експортом
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
                    # Гарантовано оновлюємо offset для уникнення дублювання
                    offset = update["update_id"] + 1

                    message = update.get("message", {})
                    chat_id = message.get("chat", {}).get("id")
                    text = message.get("text", "")

                    if chat_id == MY_CHAT_ID:
                        # 🚀 Привітання та створення кнопок
                        if text == "/start":
                            keyboard = {
                                "keyboard": [
                                    [
                                        {"text": "📊 Статус БД"},
                                        {"text": "📁 Завантажити CSV"},
                                    ],
                                    [{"text": "ℹ️ Довідка"}],
                                ],
                                "resize_keyboard": True,
                            }
                            reply_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                            requests.post(
                                reply_url,
                                json={
                                    "chat_id": MY_CHAT_ID,
                                    "text": "Вітаю в адмін-панелі! Обирай дію на кнопках нижче 👇",
                                    "reply_markup": keyboard,
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

                            reply_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                            requests.post(
                                reply_url,
                                json={
                                    "chat_id": MY_CHAT_ID,
                                    "text": f"📊 Звіт по БД:\n👤 Користувачів: {users_count}\n🛒 Замовлень: {orders_count}",
                                },
                            )

                        # 📁 Експорт у CSV (рівно 1 файл)
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

                            # 1. Записуємо та закриваємо файл
                            with open(
                                filename, mode="w", newline="", encoding="utf-8"
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

                            # 2. Відправляємо файл у Telegram
                            doc_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
                            with open(filename, "rb") as file_to_send:
                                requests.post(
                                    doc_url,
                                    data={"chat_id": MY_CHAT_ID},
                                    files={"document": file_to_send},
                                )

                            # 3. Видаляємо тимчасовий файл з диска
                            if os.path.exists(filename):
                                os.remove(filename)

                        # ℹ️ Інструкція
                        elif text == "ℹ️ Довідка":
                            help_text = (
                                "🛠 **Доступні команди:**\n\n"
                                "• Натискай кнопки меню для швидких звітів.\n"
                                "• Щоб видалити користувача, набери: `/delete [ID]`\n"
                                "*(наприклад: `/delete 3`)*"
                            )
                            reply_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
                            requests.post(
                                reply_url,
                                json={
                                    "chat_id": MY_CHAT_ID,
                                    "text": help_text,
                                    "parse_mode": "Markdown",
                                },
                            )

                        # 🗑️ Видалення користувача
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
                                    reply_text = f"🗑️ Користувача {user_name} (ID: {user_id}) видалено!"
                                else:
                                    reply_text = f"❓ Користувача з ID {user_id} не знайдено."

                                connection.close()
                            else:
                                reply_text = (
                                    "⚠️ Неправильний формат! Пиши: /delete [ID]"
                                )

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


# Pydantic-моделі для валідації запитів
class UserInput(BaseModel):
    name: str
    age: int
    email: str = "не вказано"


class OrderInput(BaseModel):
    item_name: str
    price: float
    user_id: int
    status: str = "pending"


# 🔍 Отримання списку користувачів та їх замовлень
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


# 👤 Додавання нового користувача
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


# 🛒 Додавання замовлення
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