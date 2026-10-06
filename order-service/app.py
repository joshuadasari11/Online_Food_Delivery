import os
import time
import uuid
import hashlib
import sqlite3
import requests
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

RESTAURANT_SERVICE_URL = os.getenv("RESTAURANT_SERVICE_URL", "http://restaurant-service:5001")
DELIVERY_SERVICE_URL = os.getenv("DELIVERY_SERVICE_URL", "http://delivery-service:5002")
DB_PATH = os.getenv("DB_PATH", "/app/orders.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            customer_name TEXT,
            restaurant_name TEXT,
            item_id INTEGER,
            item_name TEXT,
            quantity INTEGER,
            subtotal REAL,
            delivery_fee REAL,
            total_amount REAL,
            delivery_id TEXT,
            rider_name TEXT,
            eta_minutes INTEGER,
            delivery_address TEXT,
            status TEXT,
            signature TEXT,
            latency_ms REAL,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def simulate_cpu_work(iterations=5000):
    """Simulates realistic microservice CPU processing (e.g. food order validation & token hashing)"""
    data = b"food_order_signature_payload"
    for _ in range(iterations):
        data = hashlib.sha256(data).digest()
    return data.hex()[:16]

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "service": "order-service",
        "domain": "Online Food Delivery",
        "status": "UP",
        "timestamp": time.time()
    }), 200

@app.route('/orders', methods=['GET'])
def list_orders():
    conn = get_db_connection()
    orders = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify({
        "total_orders": len(orders),
        "orders": [dict(row) for row in orders]
    }), 200

@app.route('/orders/<order_id>', methods=['GET'])
def get_order(order_id):
    conn = get_db_connection()
    order = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    conn.close()
    if not order:
        return jsonify({"error": "Order not found"}), 404
    return jsonify(dict(order)), 200

@app.route('/orders', methods=['POST'])
def create_order():
    start_time = time.time()
    data = request.get_json() or {}

    customer_name = data.get("customer_name", "Hungry Customer")
    restaurant_id = int(data.get("restaurant_id", 1))
    item_id = int(data.get("item_id", 1))
    quantity = int(data.get("quantity", 1))
    delivery_address = data.get("delivery_address", "123 Main Street, Suite 4B")

    # Internal compute simulation
    signature = simulate_cpu_work(6000)

    # Step 1: Inter-service call -> Restaurant Service to reserve menu items
    try:
        rest_response = requests.post(
            f"{RESTAURANT_SERVICE_URL}/menu/{item_id}/reserve",
            json={"quantity": quantity, "restaurant_id": restaurant_id},
            timeout=5.0
        )
        if rest_response.status_code != 200:
            return jsonify({
                "error": "Restaurant reservation failed",
                "details": rest_response.json()
            }), rest_response.status_code
        rest_data = rest_response.json()
    except requests.exceptions.RequestException as e:
        return jsonify({
            "error": "Failed to communicate with Restaurant Service",
            "message": str(e)
        }), 503

    item_name = rest_data.get("item_name", "Delicious Dish")
    restaurant_name = rest_data.get("restaurant_name", "Gourmet Bistro")
    unit_price = rest_data.get("unit_price", 12.99)
    subtotal = round(unit_price * quantity, 2)
    order_id = f"FOOD-{uuid.uuid4().hex[:8].upper()}"

    # Step 2: Inter-service call -> Delivery Service to assign rider & calculate delivery fee
    try:
        deliv_response = requests.post(
            f"{DELIVERY_SERVICE_URL}/deliveries/assign",
            json={
                "order_id": order_id,
                "restaurant_id": restaurant_id,
                "delivery_address": delivery_address,
                "subtotal": subtotal
            },
            timeout=5.0
        )
        if deliv_response.status_code != 200:
            # Compensating transaction: roll back restaurant stock if delivery assignment fails
            requests.post(
                f"{RESTAURANT_SERVICE_URL}/menu/{item_id}/restock",
                json={"quantity": quantity},
                timeout=3.0
            )
            return jsonify({
                "error": "Delivery rider assignment failed",
                "details": deliv_response.json()
            }), deliv_response.status_code
        deliv_data = deliv_response.json()
    except requests.exceptions.RequestException as e:
        # Compensating transaction: rollback restaurant stock
        requests.post(
            f"{RESTAURANT_SERVICE_URL}/menu/{item_id}/restock",
            json={"quantity": quantity},
            timeout=3.0
        )
        return jsonify({
            "error": "Failed to communicate with Delivery Service",
            "message": str(e)
        }), 503

    delivery_fee = deliv_data.get("delivery_fee", 3.99)
    total_amount = round(subtotal + delivery_fee, 2)
    delivery_id = deliv_data.get("delivery_id")
    rider_name = deliv_data.get("rider_name", "Express Rider")
    eta_minutes = deliv_data.get("eta_minutes", 30)

    # Step 3: Record and finalize food order
    order_record = {
        "order_id": order_id,
        "customer_name": customer_name,
        "restaurant_name": restaurant_name,
        "item_id": item_id,
        "item_name": item_name,
        "quantity": quantity,
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "total_amount": total_amount,
        "delivery_id": delivery_id,
        "rider_name": rider_name,
        "eta_minutes": eta_minutes,
        "delivery_address": delivery_address,
        "status": "CONFIRMED_PREPARING",
        "signature": signature,
        "latency_ms": round((time.time() - start_time) * 1000, 2),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO orders (
            order_id, customer_name, restaurant_name, item_id, item_name, quantity,
            subtotal, delivery_fee, total_amount, delivery_id, rider_name,
            eta_minutes, delivery_address, status, signature, latency_ms, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order_record["order_id"],
        order_record["customer_name"],
        order_record["restaurant_name"],
        order_record["item_id"],
        order_record["item_name"],
        order_record["quantity"],
        order_record["subtotal"],
        order_record["delivery_fee"],
        order_record["total_amount"],
        order_record["delivery_id"],
        order_record["rider_name"],
        order_record["eta_minutes"],
        order_record["delivery_address"],
        order_record["status"],
        order_record["signature"],
        order_record["latency_ms"],
        order_record["created_at"]
    ))
    conn.commit()
    conn.close()

    return jsonify({
        "message": "Food order placed and confirmed successfully",
        "order": order_record
    }), 201

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
