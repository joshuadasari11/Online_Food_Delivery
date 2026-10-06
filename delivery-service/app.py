import os
import time
import uuid
import hashlib
from flask import Flask, request, jsonify

app = Flask(__name__)

# Delivery fleet partners
riders_pool = [
    {"rider_id": "RIDER-101", "name": "Carlos Gomez", "vehicle": "Electric Scooter", "rating": 4.9},
    {"rider_id": "RIDER-102", "name": "Elena Rostova", "vehicle": "Bicycle", "rating": 4.8},
    {"rider_id": "RIDER-103", "name": "Marcus Chen", "vehicle": "Motorcycle", "rating": 4.9},
    {"rider_id": "RIDER-104", "name": "Aisha Patel", "vehicle": "Electric Bike", "rating": 4.7},
    {"rider_id": "RIDER-105", "name": "Liam O'Connor", "vehicle": "Motorcycle", "rating": 4.8}
]

# Active deliveries registry
deliveries_db = {}

def simulate_cpu_work(iterations=5000):
    """Simulates GPS routing, route dispatch optimization and payment token hashing"""
    data = b"gps_delivery_dispatch_hash"
    for _ in range(iterations):
        data = hashlib.sha256(data).digest()
    return data.hex()[:16]

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "service": "delivery-service",
        "domain": "Online Food Delivery",
        "status": "UP",
        "timestamp": time.time()
    }), 200

@app.route('/deliveries/assign', methods=['POST'])
def assign_delivery():
    data = request.get_json() or {}
    order_id = data.get("order_id")
    restaurant_id = data.get("restaurant_id", 1)
    delivery_address = data.get("delivery_address", "Customer Location")
    subtotal = float(data.get("subtotal", 10.0))

    if not order_id:
        return jsonify({"error": "order_id is required"}), 400

    # Simulate GPS routing and cryptographic token computation
    dispatch_token = simulate_cpu_work(5000)

    # Pick a rider round-robin / based on hash
    rider_index = abs(hash(order_id)) % len(riders_pool)
    assigned_rider = riders_pool[rider_index]

    # Calculate simulated distance and delivery fee
    distance_km = round(2.0 + (abs(hash(order_id)) % 60) / 10.0, 1)  # 2.0 to 8.0 km
    delivery_fee = round(2.99 + (distance_km * 0.45), 2)
    eta_minutes = int(15 + (distance_km * 3))

    delivery_id = f"DELIV-{uuid.uuid4().hex[:8].upper()}"
    delivery_record = {
        "delivery_id": delivery_id,
        "order_id": order_id,
        "restaurant_id": restaurant_id,
        "delivery_address": delivery_address,
        "rider_id": assigned_rider["rider_id"],
        "rider_name": assigned_rider["name"],
        "rider_vehicle": assigned_rider["vehicle"],
        "distance_km": distance_km,
        "delivery_fee": delivery_fee,
        "eta_minutes": eta_minutes,
        "dispatch_token": dispatch_token,
        "status": "RIDER_ASSIGNED_DISPATCHED",
        "dispatched_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    deliveries_db[delivery_id] = delivery_record

    return jsonify({
        "message": "Delivery partner successfully assigned and dispatched",
        "delivery_id": delivery_id,
        "rider_name": assigned_rider["name"],
        "rider_vehicle": assigned_rider["vehicle"],
        "delivery_fee": delivery_fee,
        "eta_minutes": eta_minutes,
        "status": "RIDER_ASSIGNED",
        "dispatch_token": dispatch_token
    }), 200

@app.route('/deliveries/<delivery_id>', methods=['GET'])
def get_delivery_status(delivery_id):
    delivery = deliveries_db.get(delivery_id)
    if not delivery:
        return jsonify({"error": "Delivery record not found"}), 404
    return jsonify(delivery), 200

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5002))
    app.run(host='0.0.0.0', port=port)
