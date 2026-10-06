import random
from locust import HttpUser, task, between

class FoodDeliveryUser(HttpUser):
    """
    Locust load testing suite for Online Food Delivery System.
    Simulates high-traffic peak dinner hour swarms placing food orders.
    """
    wait_time = between(0.05, 0.2)

    @task(4)
    def place_food_order_e2e(self):
        """
        End-to-End Orchestrated Food Order Flow:
        Client -> Order Service -> Restaurant Service -> Delivery Service
        """
        item_id = random.randint(1, 5)
        payload = {
            "customer_name": f"Customer_{random.randint(1, 10000)}",
            "restaurant_id": item_id,
            "item_id": item_id,
            "quantity": random.randint(1, 2),
            "delivery_address": f"{random.randint(10, 999)} Metro Boulevard, Floor {random.randint(1, 15)}"
        }
        self.client.post(
            "/orders",
            json=payload,
            name="POST /orders [Food Order E2E Orchestration]"
        )

    @task(1)
    def check_past_orders(self):
        """Queries order ledger database."""
        self.client.get("/orders", name="GET /orders")

    @task(1)
    def health_check(self):
        """Verifies order service health."""
        self.client.get("/health", name="GET /health")
