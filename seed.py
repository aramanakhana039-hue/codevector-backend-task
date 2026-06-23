import asyncio
import os
import random
from datetime import datetime, timedelta
import asyncpg
from dotenv import load_dotenv

# .env file se environment variables load karne ke liye
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Fake data generate karne ke liye simple helpers
PRODUCT_NAMES = ["Laptop", "Smartphone", "Headphones", "Smartwatch", "Keyboard", "Mouse", "Monitor", "Tablet"]
BRANDS = ["TechCorp", "GadgetMaster", "MacroSoft", "FruitInc", "LogiTech"]

def generate_fake_products(batch_size=10000):
    batch = []
    base_time = datetime.utcnow()
    for _ in range(batch_size):
        name = f"{random.choice(BRANDS)} {random.choice(PRODUCT_NAMES)} {random.randint(100, 999)}"
        price = round(random.uniform(10.0, 2000.0), 2)
        # 30 din purani alag-alag timestamps generate karne ke liye
        created_at = base_time - timedelta(
            days=random.randint(0, 30),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59)
        )
        batch.append((name, price, created_at))
    return batch

async def seed_database():
    if not DATABASE_URL:
        print("Error: DATABASE_URL environment variable nahi mila!")
        return

    print("Database se connect ho rha hai...")
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # 1. Products table banana (agar pehle se nahi bani hai)
        print("Table create ho rha hai...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                price NUMERIC(10, 2) NOT NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
            );
        """)

        # 2. Performance ke liye Composite Index lagana (created_at aur id par)
        print("Composite index create ho rha hai high performance ke liye...")
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_products_created_id 
            ON products (created_at DESC, id DESC);
        """)

        # 3. 200,000 records insert karna (20 batches of 10,000)
        total_records = 200000
        batch_size = 10000
        batches = total_records // batch_size

        print(f"Total {total_records} records insert hona shuru ho rahe hain...")
        for i in range(batches):
            products_batch = generate_fake_products(batch_size)
            # executemany ka use karke fast batch insertion
            await conn.executemany("""
                INSERT INTO products (name, price, created_at) 
                VALUES ($1, $2, $3);
            """, products_batch)
            print(f"Batch {i+1}/{batches} ({len(products_batch)} records) successfully inserted.")

        print("Database seeding successfully poori ho gayi! 🎉")

    except Exception as e:
        print(f"Kuch error aaya: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(seed_database())
