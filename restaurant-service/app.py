import os
import time
import hashlib
from flask import Flask, request, jsonify

app = Flask(__name__)

# Restaurant Partners
restaurants_db = {
    1: {"id": 1, "name": "Mario's Italian Trattoria", "cuisine": "Italian", "rating": 4.8},
    2: {"id": 2, "name": "Spice Route Royal Kitchen", "cuisine": "North Indian & Mughlai", "rating": 4.9},
    3: {"id": 3, "name": "The Gourmet Burger Shack", "cuisine": "American Gourmet", "rating": 4.6},
    4: {"id": 4, "name": "Tokyo Zen Sushi & Ramen", "cuisine": "Japanese", "rating": 4.7},
    5: {"id": 5, "name": "Green Garden Healthy Bowls", "cuisine": "Salads & Vegan", "rating": 4.5}
}

# Menu Items catalog
menu_db = {
    1: {"id": 1, "restaurant_id": 1, "name": "Artisanal Margherita Pizza", "price": 14.99, "stock": 50000, "prep_time_mins": 15},
    2: {"id": 2, "restaurant_id": 2, "name": "Royal Chicken Dum Biryani", "price": 16.50, "stock": 50000, "prep_time_mins": 20},
    3: {"id": 3, "restaurant_id": 3, "name": "Double Smash Cheddar Burger", "price": 12.25, "stock": 50000, "prep_time_mins": 12},
    4: {"id": 4, "restaurant_id": 4, "name": "Salmon Nigiri & Dragon Roll Set", "price": 19.99, "stock": 50000, "prep_time_mins": 18},
    5: {"id": 5, "restaurant_id": 5, "name": "Mediterranean Quinoa Falafel Bowl", "price": 11.50, "stock": 50000, "prep_time_mins": 10}
}

def simulate_cpu_work(iterations=4000):
    """Simulates realistic restaurant kitchen ticketing & order validation"""
    data = b"kitchen_inventory_order_ticket"
    for _ in range(iterations):
        data = hashlib.sha256(data).digest()
    return data.hex()[:16]

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "service": "restaurant-service",
        "domain": "Online Food Delivery",
        "status": "UP",
        "timestamp": time.time()
    }), 200

@app.route('/restaurants', methods=['GET'])
def list_restaurants():
    return jsonify({
        "total_restaurants": len(restaurants_db),
        "restaurants": list(restaurants_db.values())
    }), 200

@app.route('/menu', methods=['GET'])
def list_menu():
    return jsonify({
        "total_items": len(menu_db),
        "menu": list(menu_db.values())
    }), 200

@app.route('/menu/<int:item_id>', methods=['GET'])
def get_menu_item(item_id):
    item = menu_db.get(item_id)
    if not item:
        return jsonify({"error": "Menu item not found"}), 404
    restaurant = restaurants_db.get(item["restaurant_id"], {})
    return jsonify({
        "item": item,
        "restaurant": restaurant
    }), 200

@app.route('/menu/<int:item_id>/reserve', methods=['POST'])
def reserve_menu_item(item_id):
    simulate_cpu_work(4000)
    data = request.get_json() or {}
    quantity = int(data.get("quantity", 1))

    item = menu_db.get(item_id)
    if not item:
        return jsonify({"error": f"Menu item {item_id} not found"}), 404

    restaurant = restaurants_db.get(item["restaurant_id"], {})

    if item["stock"] < quantity:
        return jsonify({
            "error": "Kitchen capacity full or ingredients out of stock",
            "available_stock": item["stock"],
            "requested_quantity": quantity
        }), 400

    item["stock"] -= quantity

    return jsonify({
        "status": "KITCHEN_RESERVED",
        "item_id": item_id,
        "item_name": item["name"],
        "unit_price": item["price"],
        "restaurant_id": item["restaurant_id"],
        "restaurant_name": restaurant.get("name", "Partner Restaurant"),
        "quantity_reserved": quantity,
        "remaining_stock": item["stock"],
        "estimated_prep_mins": item["prep_time_mins"]
    }), 200

@app.route('/menu/<int:item_id>/restock', methods=['POST'])
def restock_menu_item(item_id):
    data = request.get_json() or {}
    quantity = int(data.get("quantity", 1))

    item = menu_db.get(item_id)
    if not item:
        return jsonify({"error": f"Menu item {item_id} not found"}), 404

    item["stock"] += quantity
    return jsonify({
        "status": "RESTOCKED",
        "item_id": item_id,
        "new_stock": item["stock"]
    }), 200

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5001))
    app.run(host='0.0.0.0', port=port)
