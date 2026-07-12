import sqlite3  # Підключаємо інструмент для роботи з базою даних

# 1. Створюємо файл бази даних. Він з'явиться прямо у твоїй папці!
connection = sqlite3.connect("my_database.db")
cursor = connection.cursor()

# 2. Створюємо таблицю з користувачами, якщо її ще немає
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    name TEXT,
    age INTEGER
)
"""
)

# 3. Додаємо тебе в таблицю! (Ім'я Stas, вік 17)
cursor.execute("INSERT INTO users (name, age) VALUES ('Stas', 17)")
connection.commit()  # Зберігаємо зміни в базі

# 4. Просимо базу показати нам усіх, хто в ній є
cursor.execute("SELECT * FROM users WHERE id = 2")
all_users = cursor.fetchall()

print("Ось хто записаний в базі даних:")
print(all_users)

connection.close()  # Закриваємо з'єднання