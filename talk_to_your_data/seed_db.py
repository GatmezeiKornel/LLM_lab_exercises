import os
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "shop.db"
random.seed(42)

SCHEMA = """
DROP TABLE IF EXISTS reviews;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id   INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    country       TEXT NOT NULL,
    created_at    DATE NOT NULL
);

CREATE TABLE products (
    product_id    INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    category      TEXT NOT NULL,
    price         REAL NOT NULL,
    stock         INTEGER NOT NULL
);

CREATE TABLE orders (
    order_id      INTEGER PRIMARY KEY,
    customer_id   INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date    DATE NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('pending','shipped','delivered','cancelled')),
    total_amount  REAL NOT NULL
);

CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id      INTEGER NOT NULL REFERENCES orders(order_id),
    product_id    INTEGER NOT NULL REFERENCES products(product_id),
    quantity      INTEGER NOT NULL,
    unit_price    REAL NOT NULL
);

CREATE TABLE reviews (
    review_id     INTEGER PRIMARY KEY,
    customer_id   INTEGER NOT NULL REFERENCES customers(customer_id),
    product_id    INTEGER NOT NULL REFERENCES products(product_id),
    rating        INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment       TEXT,
    review_date   DATE NOT NULL
);
"""

FIRST_NAMES = ["Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace", "Hugo",
               "Iris", "Jack", "Kara", "Leo", "Mia", "Noah", "Olivia", "Paul",
               "Quinn", "Rita", "Sam", "Tina", "Uma", "Vera", "Will", "Xena"]
LAST_NAMES = ["Adams", "Brown", "Clark", "Davis", "Evans", "Ford", "Green", "Hill",
              "Irwin", "Jones", "King", "Lewis", "Moore", "Nash", "Owen", "Park"]
COUNTRIES = ["HU", "DE", "AT", "FR", "UK", "US", "ES", "IT", "NL", "SE"]

PRODUCTS = [
    ("Wireless Mouse", "Electronics", 24.99, 120),
    ("USB-C Charger 65W", "Electronics", 39.50, 85),
    ("Mechanical Keyboard", "Electronics", 119.00, 40),
    ("4K Monitor 27\"", "Electronics", 329.00, 18),
    ("Noise-Cancelling Headphones", "Electronics", 179.00, 33),
    ("Standing Desk", "Furniture", 459.00, 12),
    ("Office Chair", "Furniture", 219.00, 25),
    ("LED Desk Lamp", "Furniture", 49.90, 70),
    ("Bookshelf", "Furniture", 139.00, 22),
    ("Coffee Beans 1kg", "Grocery", 18.50, 200),
    ("Green Tea (50 bags)", "Grocery", 7.20, 150),
    ("Dark Chocolate 200g", "Grocery", 4.95, 300),
    ("Running Shoes", "Apparel", 89.00, 60),
    ("Cotton T-Shirt", "Apparel", 15.00, 220),
    ("Winter Jacket", "Apparel", 159.00, 18),
    ("Yoga Mat", "Sports", 29.00, 80),
    ("Dumbbell Set 20kg", "Sports", 69.00, 35),
    ("Bicycle Helmet", "Sports", 54.00, 28),
    ("Hardcover Notebook", "Stationery", 12.50, 180),
    ("Gel Pens (pack of 10)", "Stationery", 6.80, 250),
]

REVIEW_SNIPPETS = [
    "Exactly what I needed.", "Decent for the price.", "Stopped working after a month.",
    "Highly recommend.", "Packaging was damaged.", "Arrived earlier than expected.",
    "Mediocre quality.", "Five stars, would buy again.", "Not as described.",
    "Customer service was helpful.", "Great value.", "Build feels cheap."
]


def random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def seed() -> None:
    if DB_PATH.exists():
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(SCHEMA)

    # Customers
    customers = []
    for cid in range(1, 31):
        fname = random.choice(FIRST_NAMES)
        lname = random.choice(LAST_NAMES)
        email = f"{fname.lower()}.{lname.lower()}{cid}@example.com"
        country = random.choice(COUNTRIES)
        created = random_date(date(2023, 1, 1), date(2024, 6, 1))
        customers.append((cid, f"{fname} {lname}", email, country, created.isoformat()))
    cur.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?)", customers)

    # Products
    products = [(pid + 1, *row) for pid, row in enumerate(PRODUCTS)]
    cur.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?)", products)

    # Orders + items
    order_id = 1
    item_id = 1
    statuses = ["pending", "shipped", "delivered", "delivered", "delivered", "cancelled"]
    for _ in range(150):
        cust = random.choice(customers)
        order_date = random_date(date(2024, 1, 1), date(2025, 4, 30))
        status = random.choice(statuses)
        n_items = random.randint(1, 4)
        chosen = random.sample(products, n_items)
        items = []
        total = 0.0
        for prod in chosen:
            qty = random.randint(1, 3)
            unit_price = prod[3]
            items.append((item_id, order_id, prod[0], qty, unit_price))
            total += qty * unit_price
            item_id += 1
        cur.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
            (order_id, cust[0], order_date.isoformat(), status, round(total, 2)),
        )
        cur.executemany("INSERT INTO order_items VALUES (?, ?, ?, ?, ?)", items)
        order_id += 1

    # Reviews
    review_id = 1
    for _ in range(120):
        cust = random.choice(customers)
        prod = random.choice(products)
        rating = random.randint(1, 5)
        comment = random.choice(REVIEW_SNIPPETS)
        rdate = random_date(date(2024, 1, 1), date(2025, 4, 30))
        cur.execute(
            "INSERT INTO reviews VALUES (?, ?, ?, ?, ?, ?)",
            (review_id, cust[0], prod[0], rating, comment, rdate.isoformat()),
        )
        review_id += 1

    conn.commit()
    conn.close()
    print(f"Seeded {DB_PATH}")
    print(f"  customers : {len(customers)}")
    print(f"  products  : {len(products)}")
    print(f"  orders    : {order_id - 1}")
    print(f"  reviews   : {review_id - 1}")


if __name__ == "__main__":
    seed()
