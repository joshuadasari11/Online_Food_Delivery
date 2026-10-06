import os
import sys
import time
import json
import csv
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import urllib.error

# Non-GUI backend for Matplotlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

TARGET_URL = "http://localhost:5000/orders"
WORKLOADS = [
    {"name": "W1", "concurrency": 1, "total_requests": 150},
    {"name": "W2", "concurrency": 2, "total_requests": 150},
    {"name": "W3", "concurrency": 4, "total_requests": 150},
    {"name": "W4", "concurrency": 8, "total_requests": 150},
    {"name": "W5", "concurrency": 16, "total_requests": 150},
]

CONTAINERS = ["order-service", "restaurant-service", "delivery-service"]
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

class StreamingDockerStatsMonitor:
    def __init__(self):
        self.proc = None
        self.running = False
        self.samples = {c: {"cpu": [], "mem_mb": []} for c in CONTAINERS}
        self.thread = None

    def _parse_cpu(self, cpu_str):
        try:
            return float(cpu_str.replace('%', '').strip())
        except Exception:
            return 0.0

    def _parse_mem(self, mem_str):
        try:
            val = mem_str.split('/')[0].strip()
            if "GiB" in val or "GB" in val:
                return float(val.replace("GiB", "").replace("GB", "").strip()) * 1024
            elif "MiB" in val or "MB" in val:
                return float(val.replace("MiB", "").replace("MB", "").strip())
            elif "KiB" in val or "KB" in val:
                return float(val.replace("KiB", "").replace("KB", "").strip()) / 1024
            return 0.0
        except Exception:
            return 0.0

    def _reader(self):
        cmd = ["docker", "stats", "--format", "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}"] + CONTAINERS
        self.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        while self.running and self.proc.poll() is None:
            line = self.proc.stdout.readline()
            if not line:
                break
            clean_line = ANSI_ESCAPE.sub('', line).strip()
            if '|' in clean_line:
                parts = clean_line.split('|')
                if len(parts) >= 3:
                    name = parts[0].strip()
                    cpu = self._parse_cpu(parts[1])
                    mem = self._parse_mem(parts[2])
                    if name in self.samples:
                        self.samples[name]["cpu"].append(cpu)
                        self.samples[name]["mem_mb"].append(mem)

    def start(self):
        self.running = True
        self.samples = {c: {"cpu": [], "mem_mb": []} for c in CONTAINERS}
        self.thread = threading.Thread(target=self._reader, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.communicate(timeout=1.0)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass

    def get_summary(self):
        summary = {}
        total_avg_cpu = 0.0
        total_avg_mem = 0.0
        for c in CONTAINERS:
            cpus = self.samples[c]["cpu"]
            mems = self.samples[c]["mem_mb"]
            avg_cpu = sum(cpus) / len(cpus) if cpus else 0.0
            avg_mem = sum(mems) / len(mems) if mems else 0.0
            summary[f"{c}_avg_cpu"] = round(avg_cpu, 2)
            summary[f"{c}_avg_mem"] = round(avg_mem, 2)
            total_avg_cpu += avg_cpu
            total_avg_mem += avg_mem
        summary["total_avg_cpu"] = round(total_avg_cpu, 2)
        summary["total_avg_mem"] = round(total_avg_mem, 2)
        return summary


def send_single_request(request_id):
    item_id = (request_id % 5) + 1
    restaurant_id = item_id
    payload = json.dumps({
        "customer_name": f"Hungry_Client_{request_id}",
        "restaurant_id": restaurant_id,
        "item_id": item_id,
        "quantity": 1,
        "delivery_address": f"{100 + request_id} Foodie Avenue, Apt {request_id % 20}"
    }).encode("utf-8")

    req = urllib.request.Request(
        TARGET_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            status = resp.status
            resp.read()
            lat = (time.perf_counter() - t0) * 1000.0  # in ms
            return {"success": (status == 201 or status == 200), "latency": lat}
    except Exception as e:
        lat = (time.perf_counter() - t0) * 1000.0
        return {"success": False, "latency": lat, "error": str(e)}


def run_benchmark():
    os.makedirs("results/graphs", exist_ok=True)
    results = []

    print("=================================================================")
    print(" FOOD DELIVERY MICROSERVICES BENCHMARK & PERFORMANCE MONITOR")
    print("=================================================================")
    print(f"Target: {TARGET_URL}")
    print(f"Containers Monitored: {', '.join(CONTAINERS)}")
    print("-----------------------------------------------------------------")

    for wl in WORKLOADS:
        w_name = wl["name"]
        concurrency = wl["concurrency"]
        total_reqs = wl["total_requests"]

        print(f"\n[+] Executing {w_name}: Concurrency = {concurrency}, Total Requests = {total_reqs}")

        monitor = StreamingDockerStatsMonitor()
        monitor.start()
        time.sleep(1.0)  # allow monitor streaming process to attach

        latencies = []
        successes = 0
        failures = 0

        bench_start = time.perf_counter()

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(send_single_request, i) for i in range(total_reqs)]
            for fut in as_completed(futures):
                res = fut.result()
                latencies.append(res["latency"])
                if res["success"]:
                    successes += 1
                else:
                    failures += 1

        bench_duration = time.perf_counter() - bench_start
        time.sleep(0.5)  # flush final metrics
        monitor.stop()

        stats_summary = monitor.get_summary()

        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        throughput = total_reqs / bench_duration if bench_duration > 0 else 0.0

        latencies.sort()
        p95_latency = latencies[int(len(latencies) * 0.95)] if latencies else 0.0

        row = {
            "Workload": w_name,
            "Concurrency": concurrency,
            "Total_Requests": total_reqs,
            "Successful": successes,
            "Failed": failures,
            "Duration_s": round(bench_duration, 2),
            "Avg_Response_Time_ms": round(avg_latency, 2),
            "P95_Response_Time_ms": round(p95_latency, 2),
            "Throughput_req_s": round(throughput, 2),
            "Order_CPU_pct": stats_summary.get("order-service_avg_cpu", 0.0),
            "Restaurant_CPU_pct": stats_summary.get("restaurant-service_avg_cpu", 0.0),
            "Delivery_CPU_pct": stats_summary.get("delivery-service_avg_cpu", 0.0),
            "Total_CPU_pct": stats_summary.get("total_avg_cpu", 0.0),
            "Total_Mem_MB": stats_summary.get("total_avg_mem", 0.0),
            "Order_Mem_MB": stats_summary.get("order-service_avg_mem", 0.0),
            "Restaurant_Mem_MB": stats_summary.get("restaurant-service_avg_mem", 0.0),
            "Delivery_Mem_MB": stats_summary.get("delivery-service_avg_mem", 0.0)
        }
        results.append(row)

        print(f"    -> Done in {row['Duration_s']}s | Avg Latency: {row['Avg_Response_Time_ms']} ms | Throughput: {row['Throughput_req_s']} req/s")
        print(f"    -> Success: {successes} | Failed: {failures} | Total CPU: {row['Total_CPU_pct']}% | Total Mem: {row['Total_Mem_MB']} MB")
        print(f"    -> Breakdown CPU - Order: {row['Order_CPU_pct']}%, Restaurant: {row['Restaurant_CPU_pct']}%, Delivery: {row['Delivery_CPU_pct']}%")

        time.sleep(2)

    # Save to CSV
    csv_file = "results/workload_observations.csv"
    keys = list(results[0].keys())
    with open(csv_file, mode="w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n[✓] Results successfully exported to {csv_file}")

    # Generate Graphs
    generate_all_graphs(results)


def generate_all_graphs(results):
    concurrencies = [r["Concurrency"] for r in results]
    avg_latency = [r["Avg_Response_Time_ms"] for r in results]
    throughput = [r["Throughput_req_s"] for r in results]
    total_cpu = [r["Total_CPU_pct"] for r in results]
    total_mem = [r["Total_Mem_MB"] for r in results]

    order_cpu = [r["Order_CPU_pct"] for r in results]
    rest_cpu = [r["Restaurant_CPU_pct"] for r in results]
    deliv_cpu = [r["Delivery_CPU_pct"] for r in results]

    order_mem = [r["Order_Mem_MB"] for r in results]
    rest_mem = [r["Restaurant_Mem_MB"] for r in results]
    deliv_mem = [r["Delivery_Mem_MB"] for r in results]

    # Graph 1: Concurrent Requests vs Average Response Time
    plt.figure(figsize=(8, 5))
    plt.plot(concurrencies, avg_latency, marker='o', color='#2563eb', linewidth=2.5, markersize=8)
    for x, y in zip(concurrencies, avg_latency):
        plt.annotate(f"{y} ms", (x, y), textcoords="offset points", xytext=(0, 10), ha='center', fontweight='bold', fontsize=9)
    plt.title("Online Food Delivery: Concurrency vs. Average Response Time", fontsize=13, fontweight='bold', pad=15)
    plt.xlabel("Concurrency Level (Concurrent Requests)", fontsize=11)
    plt.ylabel("Average Response Time (ms)", fontsize=11)
    plt.xticks(concurrencies)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    g1_path = "results/graphs/Concurrent_Requests_vs_Average_Response_Time.png"
    plt.savefig(g1_path, dpi=300)
    plt.close()
    print(f"[✓] Graph saved: {g1_path}")

    # Graph 2: Concurrent Requests vs Throughput
    plt.figure(figsize=(8, 5))
    plt.plot(concurrencies, throughput, marker='s', color='#16a34a', linewidth=2.5, markersize=8)
    for x, y in zip(concurrencies, throughput):
        plt.annotate(f"{y} req/s", (x, y), textcoords="offset points", xytext=(0, 10), ha='center', fontweight='bold', fontsize=9)
    plt.title("Online Food Delivery: Concurrency vs. Throughput", fontsize=13, fontweight='bold', pad=15)
    plt.xlabel("Concurrency Level (Concurrent Requests)", fontsize=11)
    plt.ylabel("Throughput (Requests / Second)", fontsize=11)
    plt.xticks(concurrencies)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    g2_path = "results/graphs/Concurrent_Requests_vs_Throughput.png"
    plt.savefig(g2_path, dpi=300)
    plt.close()
    print(f"[✓] Graph saved: {g2_path}")

    # Graph 3: Concurrent Requests vs CPU Utilization
    plt.figure(figsize=(8, 5))
    plt.plot(concurrencies, total_cpu, marker='^', color='#dc2626', linewidth=2.5, markersize=8, label="Total System CPU %")
    plt.plot(concurrencies, order_cpu, marker='o', color='#ea580c', linestyle='--', label="Order Service CPU %")
    plt.plot(concurrencies, rest_cpu, marker='v', color='#0284c7', linestyle='--', label="Restaurant Service CPU %")
    plt.plot(concurrencies, deliv_cpu, marker='d', color='#9333ea', linestyle='--', label="Delivery Service CPU %")
    for x, y in zip(concurrencies, total_cpu):
        plt.annotate(f"{y}%", (x, y), textcoords="offset points", xytext=(0, 8), ha='center', fontweight='bold', fontsize=8)
    plt.title("Online Food Delivery: Concurrency vs. CPU Utilization", fontsize=13, fontweight='bold', pad=15)
    plt.xlabel("Concurrency Level (Concurrent Requests)", fontsize=11)
    plt.ylabel("CPU Utilization (%)", fontsize=11)
    plt.xticks(concurrencies)
    plt.legend(loc="upper left")
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    g3_path = "results/graphs/Concurrent_Requests_vs_CPU_Utilization.png"
    plt.savefig(g3_path, dpi=300)
    plt.close()
    print(f"[✓] Graph saved: {g3_path}")

    # Graph 4: Concurrent Requests vs Memory Utilization
    plt.figure(figsize=(8, 5))
    plt.plot(concurrencies, total_mem, marker='D', color='#8b5cf6', linewidth=2.5, markersize=8, label="Total System Memory (MB)")
    plt.plot(concurrencies, order_mem, marker='o', color='#ea580c', linestyle='--', label="Order Service (MB)")
    plt.plot(concurrencies, rest_mem, marker='s', color='#0284c7', linestyle='--', label="Restaurant Service (MB)")
    plt.plot(concurrencies, deliv_mem, marker='^', color='#9333ea', linestyle='--', label="Delivery Service (MB)")
    for x, y in zip(concurrencies, total_mem):
        plt.annotate(f"{y} MB", (x, y), textcoords="offset points", xytext=(0, 8), ha='center', fontweight='bold', fontsize=8)
    plt.title("Online Food Delivery: Concurrency vs. Memory Utilization", fontsize=13, fontweight='bold', pad=15)
    plt.xlabel("Concurrency Level (Concurrent Requests)", fontsize=11)
    plt.ylabel("Memory Utilization (MB)", fontsize=11)
    plt.xticks(concurrencies)
    plt.legend(loc="lower right")
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    g4_path = "results/graphs/Concurrent_Requests_vs_Memory_Utilization.png"
    plt.savefig(g4_path, dpi=300)
    plt.close()
    print(f"[✓] Graph saved: {g4_path}")

    # Combined Dashboard Graph
    fig, axs = plt.subplots(2, 2, figsize=(14, 10))
    axs[0, 0].plot(concurrencies, avg_latency, marker='o', color='#2563eb', linewidth=2)
    axs[0, 0].set_title("Response Time vs Concurrency", fontweight='bold')
    axs[0, 0].set_xlabel("Concurrency")
    axs[0, 0].set_ylabel("Avg Response Time (ms)")
    axs[0, 0].set_xticks(concurrencies)
    axs[0, 0].grid(True, linestyle="--", alpha=0.5)

    axs[0, 1].plot(concurrencies, throughput, marker='s', color='#16a34a', linewidth=2)
    axs[0, 1].set_title("Throughput vs Concurrency", fontweight='bold')
    axs[0, 1].set_xlabel("Concurrency")
    axs[0, 1].set_ylabel("Throughput (req/s)")
    axs[0, 1].set_xticks(concurrencies)
    axs[0, 1].grid(True, linestyle="--", alpha=0.5)

    axs[1, 0].plot(concurrencies, total_cpu, marker='^', color='#dc2626', linewidth=2, label="Total")
    axs[1, 0].plot(concurrencies, order_cpu, linestyle='--', label="Order")
    axs[1, 0].plot(concurrencies, rest_cpu, linestyle='--', label="Restaurant")
    axs[1, 0].plot(concurrencies, deliv_cpu, linestyle='--', label="Delivery")
    axs[1, 0].set_title("CPU Utilization vs Concurrency", fontweight='bold')
    axs[1, 0].set_xlabel("Concurrency")
    axs[1, 0].set_ylabel("CPU %")
    axs[1, 0].set_xticks(concurrencies)
    axs[1, 0].legend()
    axs[1, 0].grid(True, linestyle="--", alpha=0.5)

    axs[1, 1].plot(concurrencies, total_mem, marker='D', color='#8b5cf6', linewidth=2, label="Total")
    axs[1, 1].plot(concurrencies, order_mem, linestyle='--', label="Order")
    axs[1, 1].plot(concurrencies, rest_mem, linestyle='--', label="Restaurant")
    axs[1, 1].plot(concurrencies, deliv_mem, linestyle='--', label="Delivery")
    axs[1, 1].set_title("Memory Utilization vs Concurrency", fontweight='bold')
    axs[1, 1].set_xlabel("Concurrency")
    axs[1, 1].set_ylabel("Memory (MB)")
    axs[1, 1].set_xticks(concurrencies)
    axs[1, 1].legend()
    axs[1, 1].grid(True, linestyle="--", alpha=0.5)

    plt.suptitle("Food Delivery Microservices Performance Dashboard", fontsize=16, fontweight='bold')
    plt.tight_layout()
    dashboard_path = "results/graphs/Evaluation_Dashboard.png"
    plt.savefig(dashboard_path, dpi=300)
    plt.close()
    print(f"[✓] Dashboard saved: {dashboard_path}")


if __name__ == '__main__':
    run_benchmark()
