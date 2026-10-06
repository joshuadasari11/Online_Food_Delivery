# 🍔 Online Food Delivery Microservices — Teammate Quick Reference Guide

> **GitHub Repository:** [akaraj187/OnlineFoodDelivery-Microservices-Evaluation](https://github.com/akaraj187/OnlineFoodDelivery-Microservices-Evaluation)  
> **Experiment:** Build, Deploy, and Analyze a Containerized Microservice Application Under Varying Workloads  
> **Application Domain:** Online Food Delivery & Restaurant Fulfillment System  

This document is a complete cheat sheet for teammates to understand the architecture, run the demo, and answer questions during the viva/evaluation.

---

## 📌 1. System Architecture at a Glance

Our application contains **three independent microservices** running in isolated Docker containers:

```
[ Client / Tester / Locust ]
             │
             │ HTTP POST /orders (Host Port 5000)
             ▼
     ┌────────────────────────────────────────────────────────┐
     │           Order Service (Port 5000)                    │
     │ - API Gateway & Food Order Orchestrator                │
     │ - SQLite Database for food order ledger                │
     └───────────────┬────────────────────────┬───────────────┘
                     │                        │
  HTTP POST /reserve │                        │ HTTP POST /assign
   (Internal DNS)    │                        │  (Internal DNS)
                     ▼                        ▼
       ┌────────────────────────┐  ┌────────────────────────┐
       │ Restaurant Service     │  │ Delivery Service       │
       │ (Port 5001)            │  │ (Port 5002)            │
       │ - Menus & Restaurants  │  │ - Rider fleet dispatch │
       │ - Kitchen capacity     │  │ - GPS route fee & ETA  │
       └────────────────────────┘  └────────────────────────┘
```

* **Network:** Custom Docker bridge network (`fooddelivery-network`).
* **Service Discovery:** Services communicate using Docker service names (`http://restaurant-service:5001` and `http://delivery-service:5002`), NOT hardcoded IPs.

---

## 🚀 2. Live Demo Runbook (The 2-Minute Evaluator Script)

Navigate to the project directory:
```bash
cd /home/akash_td/CloudComputing_Lab/FoodDelivery-Microservices
```

### Step 1: Launch Containers (Checkpoint 2 — 1 Mark)
```bash
docker compose up -d
docker compose ps
```
💬 **What to say:** *"All three food delivery microservices (Order, Restaurant, Delivery) are built, containerized, and running on ports 5000, 5001, and 5002 on a custom Docker bridge network."*

---

### Step 2: Show Microservices & Inter-Service Communication (Checkpoints 1 & 3 — 2 Marks)
```bash
./scripts/test_services.sh
```
💬 **What to say:** *"This script tests each service independently first (restaurant menus and rider dispatch), then places an end-to-end food order via Order Service. Order Service coordinates with Restaurant Service to reserve meals and Delivery Service to dispatch a rider, returning a complete confirmed receipt."*

---

### Step 3: Run Load Testing (Checkpoint 4 — 1 Mark)

You have **two options** depending on what the evaluator asks for:

* **Option A: Automated Benchmark with Live Docker Stats**
  ```bash
  python3 scripts/workload_benchmark.py
  ```
  *(Tests 5 concurrency tiers: 1, 2, 4, 8, 16 threads; records CPU% & Memory live; updates CSV and graphs).*

* **Option B: Using Locust**
  * **Headless (Terminal mode):**
    ```bash
    locust -f scripts/locustfile.py -H http://localhost:5000 --headless -u 16 -r 4 -t 20s
    ```
  * **Interactive Web UI (Browser mode):**
    ```bash
    locust -f scripts/locustfile.py -H http://localhost:5000
    ```
    Open `http://localhost:8089` in your browser $\rightarrow$ Users: `16`, Spawn rate: `4` $\rightarrow$ Click **"Start swarming"** to see live graphs.

---

### Step 4: Show Results & Analysis (Checkpoint 5 — 1 Mark)
```bash
cat results/workload_observations.csv
```
Or open the graphs in `results/graphs/`:
* `Concurrent_Requests_vs_Average_Response_Time.png`
* `Concurrent_Requests_vs_Throughput.png`
* `Concurrent_Requests_vs_CPU_Utilization.png`
* `Concurrent_Requests_vs_Memory_Utilization.png`
* `Evaluation_Dashboard.png`

---

### Step 5: Clean Up
```bash
docker compose down
```

---

## 📊 3. Performance Data Reference

| Workload | Concurrency | Avg Latency | Throughput | Order CPU | Total CPU | Memory | Key Takeaway |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **W1** | 1 | 52.04 ms | 19.13 req/s | 36.54% | 73.91% | 298 MB | Baseline sequential flow. |
| **W2** | 2 | 59.65 ms | **33.35 req/s** | 53.58% | 111.66% | 298 MB | **Peak Throughput!** Multi-threading overlaps I/O. |
| **W3** | 4 | 126.52 ms | 30.98 req/s | **70.25%** | **137.41%** | 299 MB | **Peak CPU Utilization** across microservices. |
| **W4** | 8 | 328.75 ms | 23.91 req/s | 66.89% | 128.45% | 299 MB | High concurrency queueing delays begin. |
| **W5** | 16 | 658.68 ms | 23.47 req/s | 50.37% | 97.85% | 299 MB | Saturation: Socket & thread contention increases latency. |

---

## 🧠 4. Top Viva Questions & Ready Answers

### Q1: "Why is a Docker containerized implementation better than Virtual Machines?"
> **Answer:** *"Virtual Machines require a separate Guest OS per service, consuming gigabytes of RAM and taking minutes to boot. Docker uses OS-level virtualization: containers share the host Linux kernel, boot in less than 2 seconds, and all three of our food delivery services combined consume only ~298 MB of RAM."*

### Q2: "What is Docker Compose and why did we use it?"
> **Answer:** *"Docker runs single containers. Docker Compose is a tool for defining and running multi-container applications. Through `docker-compose.yml`, we configure all three services, manage networking, and set up automatic internal DNS resolution using a single command: `docker compose up -d`."*

### Q3: "Which microservice consumed the most CPU and why?"
> **Answer:** *"**Order Service** was the highest consumer (peaking at 70.25% CPU). This is because Order Service acts as the API Gateway/Orchestrator: it handles incoming client connections, manages two outbound HTTP connections to Restaurant and Delivery services, and writes order records to SQLite."*

### Q4: "Why did throughput plateau and latency increase at 16 concurrent requests (W5)?"
> **Answer:** *"At 16 concurrency, the system reached its worker saturation limit. Requests spent more time waiting in the connection backlog for available WSGI workers, resulting in higher latency (658 ms) while throughput settled at ~23.5 req/s."*

### Q5: "What happened to memory usage during load testing?"
> **Answer:** *"Memory usage remained virtually flat at ~298 MB total across all 5 workload levels (~113 MB for Order, ~91 MB for Restaurant, ~93 MB for Delivery). This confirms that there are **zero memory leaks** and garbage collection remained stable under load."*
