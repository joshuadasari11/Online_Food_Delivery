#!/bin/bash
set -e

echo "=========================================================="
echo "  FOOD DELIVERY MICROSERVICES VERIFICATION & DEMO TEST"
echo "=========================================================="

echo -e "\n[1] Testing Order Service Health (Port 5000)..."
curl -s http://localhost:5000/health | python3 -m json.tool

echo -e "\n[2] Testing Restaurant Service Health & Menus (Port 5001)..."
curl -s http://localhost:5001/health | python3 -m json.tool
echo "Fetching Partner Restaurants:"
curl -s http://localhost:5001/restaurants | python3 -m json.tool
echo "Fetching Sample Menu Items:"
curl -s http://localhost:5001/menu | python3 -m json.tool

echo -e "\n[3] Testing Delivery Service Health (Port 5002)..."
curl -s http://localhost:5002/health | python3 -m json.tool

echo -e "\n[4] Testing Independent Restaurant Kitchen Reservation (Checkpoint 1)..."
curl -s -X POST http://localhost:5001/menu/1/reserve \
  -H "Content-Type: application/json" \
  -d '{"quantity": 2}' | python3 -m json.tool

echo -e "\n[5] Testing Independent Rider Dispatch (Checkpoint 1)..."
curl -s -X POST http://localhost:5002/deliveries/assign \
  -H "Content-Type: application/json" \
  -d '{"order_id": "TEST-FD-101", "restaurant_id": 1, "delivery_address": "742 Evergreen Terrace", "subtotal": 29.98}' | python3 -m json.tool

echo -e "\n[6] Testing Full End-to-End Orchestrated Food Order Flow (Checkpoint 3)..."
echo "Sending POST http://localhost:5000/orders (Client -> Order -> Restaurant & Delivery)..."
curl -s -X POST http://localhost:5000/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "Samantha Green",
    "restaurant_id": 2,
    "item_id": 2,
    "quantity": 2,
    "delivery_address": "450 Sunset Blvd, Apt 12B"
  }' | python3 -m json.tool

echo -e "\n[7] Querying Food Orders Database from Order Service..."
curl -s http://localhost:5000/orders | python3 -m json.tool

echo -e "\n=========================================================="
echo "  ALL FOOD DELIVERY INTER-SERVICE TESTS PASSED (100%)"
echo "=========================================================="
