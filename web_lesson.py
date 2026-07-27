import asyncio
import sqlite3
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

TELEGRAM_TOKEN = "8916527546:AAGzG2i9GZBCYlA9W7pmpiSZfdQLMC0uKUw"
MY_CHAT_ID = 6561129115
ADMIN_PASSWORD = "stas_secret_pass"


# 🛠️ Створення/ініціалізація баз даних при запуску
def init_db():
    connection = sqlite3.connect("my_database.db")
    cursor = connection.cursor()

    # Таблиця користувачів
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        age INTEGER NOT NULL
    )
    """
    )

    # Нова таблиця замовлень із зовнішнім ключем FOREIGN KEY
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT NOT NULL,
        price REAL NOT NULL,
        user_id INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """
    )

    connection.commit()
    connection.close()


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
                    message = update.get("message", {})
                    chat_id = message.get("chat", {}).get("id")
                    text = message.get("text", "")

                    if chat_id == MY_CHAT_ID:
                        if text == "/status":
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
                                    reply_text = f"🗑️ Користувача {user_name} (ID: {user_id}) видалено з бази!"
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
    init_db()  # Автоматично створюємо таблиці при запуску сервера
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


# Модель для створення замовлення
class OrderInput(BaseModel):
    item_name: str
    price: float
    user_id: int


@app.get("/users")
def get_users_from_db(x_password: str = Header(None)):
    if x_password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=401, detail="Невірний пароль доступу!"
        )

    connection = sqlite3.connect("my_database.db")
    cursor = connection.cursor()

    # Складний SQL-запит (JOIN), який об'єднує користувачів та їхні замовлення!
    cursor.execute(
        """
        SELECT users.id, users.name, users.age, orders.item_name, orders.price
        FROM users
        LEFT JOIN orders ON users.id = orders.user_id
    """
    )
    data = cursor.fetchall()
    connection.close()
    return {"users_and_orders": data}


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

    text_message = f"🔔 Новий користувач!\n👤 Ім'я: {user.name}\n🎂 Вік: {user.age}"
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(
        telegram_url, json={"chat_id": MY_CHAT_ID, "text": text_message}
    )

    return {"status": "success", "message": f"Користувача {user.name} додано!"}


# 🛒 НОВИЙ МЕТОД: Додавання замовлення для користувача
@app.post("/add-order")
def add_order_to_db(order: OrderInput, x_password: str = Header(None)):
    if x_password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=401, detail="Невірний пароль доступу!"
        )

    connection = sqlite3.connect("my_database.db")
    cursor = connection.cursor()

    # Перевіримо, чи існує такий юзер
    cursor.execute("SELECT name FROM users WHERE id = ?", (order.user_id,))
    user = cursor.fetchone()

    if not user:
        connection.close()
        raise HTTPException(
            status_code=404, detail="Користувача з таким ID не існує!"
        )

    cursor.execute(
        "INSERT INTO orders (item_name, price, user_id) VALUES (?, ?, ?)",
        (order.item_name, order.price, order.user_id),
    )
    connection.commit()
    connection.close()

    return {
        "status": "success",
        "message": f"Товар '{order.item_name}' за ${order.price} успішно прив'язано до {user[0]} (ID: {order.user_id})!",
    }