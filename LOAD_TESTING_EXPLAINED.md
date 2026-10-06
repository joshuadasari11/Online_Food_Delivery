# 🧪 Load Testing & Benchmark Script — Detailed Explanation

> **Script Path:** [`scripts/workload_benchmark.py`](file:///home/akash_td/CloudComputing_Lab/FoodDelivery-Microservices/scripts/workload_benchmark.py)  
> **Target Endpoint:** `POST http://localhost:5000/orders` (Full end-to-end orchestration)  
> **Output Files:**
> - Observation Table: [`results/workload_observations.csv`](file:///home/akash_td/CloudComputing_Lab/FoodDelivery-Microservices/results/workload_observations.csv)
> - Graphs: [`results/graphs/`](file:///home/akash_td/CloudComputing_Lab/FoodDelivery-Microservices/results/graphs/)

---

## 1. Overview and Purpose

The script `scripts/workload_benchmark.py` is an **automated end-to-end performance evaluation harness**. It fulfills all requirements of **Checkpoint 4 and Checkpoint 5** in the lab evaluation manual by:
1. Generating concurrent HTTP traffic across five standardized concurrency tiers ($W_1=1, W_2=2, W_3=4, W_4=8, W_5=16$).
2. Concurrently streaming real-time container resource utilization (`docker stats`) for all three containers (`order-service`, `restaurant-service`, `delivery-service`).
3. Calculating wall-clock execution duration, throughput (requests/sec), average latency (ms), and P95 latency (ms).
4. Exporting the complete observation table to CSV.
5. Automatically plotting and saving all four recommended performance curves + a composite dashboard using Matplotlib.

---

## 2. Architecture of the Script

```
┌────────────────────────────────────────────────────────────────────────┐
│                      scripts/workload_benchmark.py                     │
├────────────────────────────────────────────────────────────────────────┤
│ 1. Configuration: Defines the 5 workload levels (W1 to W5)             │
│ 2. StreamingDockerStatsMonitor: Background thread reading docker stats │
│ 3. ThreadPoolExecutor: Blasts concurrent HTTP requests to /orders     │
│ 4. Metrics & Matplotlib: Exports CSV table & renders the 4 graphs      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Code Breakdown by Component

### Component A: Workload Configuration
```python
TARGET_URL = "http://localhost:5000/orders"
WORKLOADS = [
    {"name": "W1", "concurrency": 1,  "total_requests": 150},
    {"name": "W2", "concurrency": 2,  "total_requests": 150},
    {"name": "W3", "concurrency": 4,  "total_requests": 150},
    {"name": "W4", "concurrency": 8,  "total_requests": 150},
    {"name": "W5", "concurrency": 16, "total_requests": 150},
]
CONTAINERS = ["order-service", "restaurant-service", "delivery-service"]
```
* **Why 150 requests?** Keeping total work constant at 150 requests allows us to isolate **concurrency** as the single independent variable. It runs long enough (4 to 8 seconds) for Docker to take multiple resource samples.

---

### Component B: Real-Time Docker Resource Monitor (`StreamingDockerStatsMonitor`)
```python
class StreamingDockerStatsMonitor:
    def _reader(self):
        cmd = ["docker", "stats", "--format", "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}"] + CONTAINERS
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, ...)
```
* **How it works:**
  1. Starts a non-blocking background daemon thread that executes `docker stats` in continuous streaming mode.
  2. Parses container CPU% (e.g. `53.58%`) and memory strings (e.g. `113 MiB / 3.76 GiB` into float MiB).
  3. Uses regular expressions (`ANSI_ESCAPE`) to strip terminal cursor-repositioning escape codes.
  4. Collects samples across the run and averages them into `Order_CPU_pct`, `Restaurant_CPU_pct`, `Delivery_CPU_pct`, `Total_CPU_pct`, and `Total_Mem_MB`.

---

### Component C: Sending End-to-End Requests (`send_single_request`)
```python
def send_single_request(request_id):
    payload = json.dumps({
        "customer_name": f"Hungry_Client_{request_id}",
        "restaurant_id": (request_id % 5) + 1,
        "item_id": (request_id % 5) + 1,
        "quantity": 1,
        "delivery_address": "Foodie Avenue"
    }).encode("utf-8")

    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=10.0) as resp:
        latency = (time.perf_counter() - t0) * 1000.0  # in milliseconds
        return {"success": True, "latency": latency}
```
* **How it works:**
  - Formats a JSON food order payload and sends an HTTP POST request to `http://localhost:5000/orders`.
  - Measures high-precision elapsed time in milliseconds using `time.perf_counter()`.

---

### Component D: Concurrency Execution Engine (`run_benchmark`)
```python
for wl in WORKLOADS:
    concurrency = wl["concurrency"]
    monitor.start()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(send_single_request, i) for i in range(total_reqs)]
        for fut in as_completed(futures):
            res = fut.result()
            latencies.append(res["latency"])

    monitor.stop()
    stats = monitor.get_summary()
```
* **How it works:**
  - Uses Python's `ThreadPoolExecutor(max_workers=concurrency)`.
  - At concurrency = 8, 8 operating system worker threads fire requests simultaneously.
  - Computes:
    - **Throughput:** $\frac{\text{Total Requests (150)}}{\text{Elapsed Duration (seconds)}}$
    - **Average Latency:** Mean of all 150 round-trip latencies.
    - **P95 Latency:** 95th percentile worst-case response time.

---

### Component E: Automated Graph Generation (`generate_all_graphs`)
Uses `matplotlib` with non-GUI `Agg` backend to save high-resolution 300 DPI figures:
1. `Concurrent_Requests_vs_Average_Response_Time.png`
2. `Concurrent_Requests_vs_Throughput.png`
3. `Concurrent_Requests_vs_CPU_Utilization.png`
4. `Concurrent_Requests_vs_Memory_Utilization.png`
5. `Evaluation_Dashboard.png` (4-in-1 consolidated dashboard)

---

## 4. Measured Performance Results Summary

| Workload | Concurrency | Total Requests | Success / Fail | Avg Latency (ms) | P95 Latency (ms) | Throughput (req/s) | Order CPU (%) | Restaurant CPU (%) | Delivery CPU (%) | Total CPU (%) | Total Mem (MB) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **W1** | **1** | 150 | 150 / 0 | **52.04** | 84.16 | **19.13** | 36.54% | 17.47% | 19.91% | **73.91%** | 297.74 MB |
| **W2** | **2** | 150 | 150 / 0 | **59.65** | 109.58 | **33.35** | 53.58% | 30.67% | 27.41% | **111.66%** | 297.99 MB |
| **W3** | **4** | 150 | 150 / 0 | **126.52** | 308.57 | **30.98** | 70.25% | 32.39% | 34.76% | **137.41%** | 298.62 MB |
| **W4** | **8** | 150 | 150 / 0 | **328.75** | 776.77 | **23.91** | 66.89% | 25.52% | 36.04% | **128.45%** | 298.62 MB |
| **W5** | **16** | 150 | 150 / 0 | **658.68** | 2450.50 | **23.47** | 50.37% | 21.12% | 26.36% | **97.85%** | 298.82 MB |

---

## 5. Quick Viva Speech (30 Seconds)

> *"Our benchmark script (`workload_benchmark.py`) is an automated test harness.*  
> *It uses Python's `ThreadPoolExecutor` to generate the 5 concurrency levels ($1, 2, 4, 8, 16$) against our `POST /orders` endpoint.*  
> *While the load is running, a background thread streams `docker stats` to measure real-time CPU% and memory utilization across the three containers.*  
> *Finally, it computes response time and throughput, exports the observation table to `workload_observations.csv`, and automatically plots the 4 performance curves using Matplotlib."*
