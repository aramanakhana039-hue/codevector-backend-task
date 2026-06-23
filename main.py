import os
from datetime import datetime
from typing import Optional
import asyncpg
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from dotenv import load_dotenv

# .env file load karne ke liye
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

app = FastAPI(
    title="High-Performance Scalable E-Commerce Backend",
    description="FastAPI backend with high-performance Cursor-Based Pagination on PostgreSQL"
)

# Database connection pool handle karne ke liye startup event
@app.on_event("startup")
async def startup():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable check kijiye!")
    app.state.db_pool = await asyncpg.create_pool(DATABASE_URL)

@app.on_event("shutdown")
async def shutdown():
    await app.state.db_pool.close()

# Response Model schema
class ProductResponse(BaseModel):
    id: int
    name: str
    price: float
    created_at: datetime

class PaginatedProductsResponse(BaseModel):
    data: list[ProductResponse]
    next_cursor: Optional[str] = None  # Agli request ke liye cursor string format mein

# Cursor string ko decode/parse karne ke liye helper function
def decode_cursor(cursor_str: str) -> tuple[datetime, int]:
    try:
        # Expected format: "timestamp_str|id" (e.g., "2026-06-23T12:00:00|1234")
        ts_part, id_part = cursor_str.split("|")
        created_at = datetime.fromisoformat(ts_part)
        last_id = int(id_part)
        return created_at, last_id
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cursor format!")

@app.get("/products", response_model=PaginatedProductsResponse)
async def get_products(
    limit: int = Query(default=10, ge=1, le=100, description="Ek baar mein kitne records chahiye"),
    cursor: Optional[str] = Query(default=None, description="Agli page ka unique cursor pointer")
):
    """
    High-Performance Cursor-Based Pagination Endpoint.
    Ye live updates ke dauran data skip ya duplicate hone se bachata hai.
    """
    async with app.state.db_pool.acquire() as conn:
        if cursor:
            # Agar cursor diya hai toh wahan se data fetch shuru karo
            last_created_at, last_id = decode_cursor(cursor)
            
            # Sub-second sorting issues se bachne ke liye composite comparison
            query = """
                SELECT id, name, price, created_at 
                FROM products 
                WHERE (created_at < $1) OR (created_at = $1 AND id < $2)
                ORDER BY created_at DESC, id DESC 
                LIMIT $3;
            """
            rows = await conn.fetch(query, last_created_at, last_id, limit)
        else:
            # Agar cursor nahi hai toh ekdum shuru se (latest) data fetch karo
            query = """
                SELECT id, name, price, created_at 
                FROM products 
                ORDER BY created_at DESC, id DESC 
                LIMIT $1;
            """
            rows = await conn.fetch(query, limit)

        # Database rows ko dictionary list mein convert karna
        products = [
            {
                "id": row["id"],
                "name": row["name"],
                "price": float(row["price"]),
                "created_at": row["created_at"]
            }
            for row in rows
        ]

        # Agla cursor generate karna agar current page full hai
        next_cursor = None
        if len(products) == limit:
            last_item = products[-1]
            # Next request ke liye cursor format: "ISO_TIMESTAMP|ID"
            next_cursor = f"{last_item['created_at'].isoformat()}|{last_item['id']}"

        return {
            "data": products,
            "next_cursor": next_cursor
        }
