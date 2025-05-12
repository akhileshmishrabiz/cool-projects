#!/usr/bin/env python3
from flask import Flask, jsonify, request, render_template_string
import psycopg2
from psycopg2.extras import RealDictCursor
import threading
import time
import random
import hashlib
import json
import os
from datetime import datetime

app = Flask(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'postgres'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'monitordb'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres123')
}

# Global memory storage
memory_cache = {}
computation_results = []
background_tasks = []

# Initialize database
def init_db():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Create tables
        cur.execute('''
            CREATE TABLE IF NOT EXISTS performance_data (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metric_name VARCHAR(50),
                metric_value FLOAT,
                metadata JSONB
            )
        ''')
        
        cur.execute('''
            CREATE TABLE IF NOT EXISTS computation_results (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                computation_type VARCHAR(50),
                input_size INTEGER,
                result TEXT,
                duration_ms FLOAT
            )
        ''')
        
        conn.commit()
        cur.close()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")

# CPU-intensive function
def cpu_intensive_task(iterations=1000000):
    """Perform CPU-intensive calculations"""
    start_time = time.time()
    result = 0
    for i in range(iterations):
        result += i ** 2 * random.random()
        if i % 1000 == 0:
            # Create some string operations to increase CPU usage
            temp = hashlib.sha256(str(result).encode()).hexdigest()
    
    duration = (time.time() - start_time) * 1000  # ms
    return result, duration

# Memory-intensive function
def memory_intensive_task(size_mb=10):
    """Allocate memory and perform operations"""
    start_time = time.time()
    
    # Allocate memory
    data = []
    for i in range(size_mb):
        # Create 1MB of data
        chunk = 'X' * (1024 * 1024)
        data.append(chunk)
        # Store in cache
        memory_cache[f'chunk_{i}_{time.time()}'] = chunk
    
    # Perform operations on data
    result = len(''.join(data))
    duration = (time.time() - start_time) * 1000  # ms
    
    return result, duration

# Background worker thread
def background_worker():
    """Continuously perform background tasks"""
    while True:
        try:
            # Simulate database operations
            conn = psycopg2.connect(**DB_CONFIG)
            cur = conn.cursor()
            
            # Insert random metrics
            metrics = ['cpu_load', 'memory_usage', 'request_count', 'error_rate']
            for metric in metrics:
                value = random.uniform(0, 100)
                cur.execute('''
                    INSERT INTO performance_data (metric_name, metric_value, metadata)
                    VALUES (%s, %s, %s)
                ''', (metric, value, json.dumps({'source': 'background_worker'})))
            
            conn.commit()
            cur.close()
            conn.close()
            
            # Perform some computation
            result, duration = cpu_intensive_task(100000)
            computation_results.append({
                'timestamp': datetime.now().isoformat(),
                'result': result,
                'duration': duration
            })
            
            # Keep only last 100 results to prevent unlimited growth
            if len(computation_results) > 100:
                computation_results.pop(0)
            
            # Clean old cache entries
            if len(memory_cache) > 50:
                keys = list(memory_cache.keys())
                for key in keys[:10]:
                    del memory_cache[key]
            
            time.sleep(5)  # Wait 5 seconds before next iteration
            
        except Exception as e:
            print(f"Background worker error: {e}")
            time.sleep(10)

# Start background workers
for i in range(3):  # Start 3 background workers
    thread = threading.Thread(target=background_worker, daemon=True)
    thread.start()
    background_tasks.append(thread)

@app.route('/')
def index():
    html_template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>High-Performance Monitored Application</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .metric { 
                display: inline-block; 
                margin: 10px; 
                padding: 20px; 
                background: #f0f0f0; 
                border-radius: 5px; 
                min-width: 200px;
            }
            .metric h3 { margin: 0 0 10px 0; }
            .metric .value { font-size: 24px; font-weight: bold; color: #333; }
            button { 
                padding: 10px 20px; 
                margin: 5px; 
                font-size: 16px; 
                cursor: pointer;
                background: #007bff;
                color: white;
                border: none;
                border-radius: 5px;
            }
            button:hover { background: #0056b3; }
            .results { 
                margin-top: 20px; 
                padding: 20px; 
                background: #f9f9f9; 
                border-radius: 5px;
            }
        </style>
    </head>
    <body>
        <h1>High-Performance Monitored Application</h1>
        
        <div class="metrics">
            <div class="metric">
                <h3>Memory Cache Size</h3>
                <div class="value">{{ cache_size }} entries</div>
            </div>
            <div class="metric">
                <h3>Computation Results</h3>
                <div class="value">{{ results_count }} stored</div>
            </div>
            <div class="metric">
                <h3>Background Tasks</h3>
                <div class="value">{{ tasks_count }} running</div>
            </div>
            <div class="metric">
                <h3>Database Records</h3>
                <div class="value">{{ db_records }} total</div>
            </div>
        </div>
        
        <h2>Stress Test Controls</h2>
        <button onclick="runCpuTest()">Run CPU Test</button>
        <button onclick="runMemoryTest()">Run Memory Test</button>
        <button onclick="runDatabaseTest()">Run Database Test</button>
        <button onclick="runCombinedTest()">Run Combined Test</button>
        
        <div id="results" class="results"></div>
        
        <h2>Available Endpoints:</h2>
        <ul>
            <li><a href="/">/</a> - Main dashboard</li>
            <li><a href="/health">/health</a> - Health check</li>
            <li><a href="/api/stats">/api/stats</a> - System statistics</li>
            <li><a href="/api/cpu-intensive">/api/cpu-intensive</a> - CPU intensive task</li>
            <li><a href="/api/memory-intensive">/api/memory-intensive</a> - Memory intensive task</li>
            <li><a href="/api/database-intensive">/api/database-intensive</a> - Database intensive task</li>
        </ul>
        
        <script>
            function updateResults(data) {
                document.getElementById('results').innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
            }
            
            function runCpuTest() {
                fetch('/api/cpu-intensive?iterations=2000000')
                    .then(response => response.json())
                    .then(data => updateResults(data));
            }
            
            function runMemoryTest() {
                fetch('/api/memory-intensive?size_mb=50')
                    .then(response => response.json())
                    .then(data => updateResults(data));
            }
            
            function runDatabaseTest() {
                fetch('/api/database-intensive?operations=1000')
                    .then(response => response.json())
                    .then(data => updateResults(data));
            }
            
            function runCombinedTest() {
                fetch('/api/combined-stress?duration=30')
                    .then(response => response.json())
                    .then(data => updateResults(data));
            }
        </script>
    </body>
    </html>
    '''
    
    # Get current statistics
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM performance_data")
        db_records = cur.fetchone()[0]
        cur.close()
        conn.close()
    except:
        db_records = 0
    
    return render_template_string(html_template,
        cache_size=len(memory_cache),
        results_count=len(computation_results),
        tasks_count=len([t for t in background_tasks if t.is_alive()]),
        db_records=db_records
    )

@app.route('/health')
def health():
    try:
        # Check database connection
        conn = psycopg2.connect(**DB_CONFIG)
        conn.close()
        return 'healthy\n', 200
    except:
        return 'unhealthy\n', 500

@app.route('/api/stats')
def stats():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get recent metrics
        cur.execute('''
            SELECT metric_name, AVG(metric_value) as avg_value
            FROM performance_data
            WHERE timestamp > NOW() - INTERVAL '5 minutes'
            GROUP BY metric_name
        ''')
        metrics = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'memory_cache_size': len(memory_cache),
            'computation_results': len(computation_results),
            'background_tasks': len([t for t in background_tasks if t.is_alive()]),
            'recent_metrics': metrics
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cpu-intensive')
def api_cpu_intensive():
    iterations = int(request.args.get('iterations', 1000000))
    result, duration = cpu_intensive_task(iterations)
    
    # Store result in database
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO computation_results (computation_type, input_size, result, duration_ms)
            VALUES (%s, %s, %s, %s)
        ''', ('cpu_intensive', iterations, str(result), duration))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Database error: {e}")
    
    return jsonify({
        'type': 'cpu_intensive',
        'iterations': iterations,
        'result': result,
        'duration_ms': duration
    })

@app.route('/api/memory-intensive')
def api_memory_intensive():
    size_mb = int(request.args.get('size_mb', 10))
    result, duration = memory_intensive_task(size_mb)
    
    return jsonify({
        'type': 'memory_intensive',
        'size_mb': size_mb,
        'result': result,
        'duration_ms': duration,
        'cache_size': len(memory_cache)
    })

@app.route('/api/database-intensive')
def api_database_intensive():
    operations = int(request.args.get('operations', 100))
    start_time = time.time()
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Perform many database operations
        for i in range(operations):
            # Insert
            cur.execute('''
                INSERT INTO performance_data (metric_name, metric_value, metadata)
                VALUES (%s, %s, %s)
            ''', (f'test_metric_{i}', random.uniform(0, 100), json.dumps({'iteration': i})))
            
            # Select
            if i % 10 == 0:
                cur.execute('''
                    SELECT * FROM performance_data 
                    WHERE metric_name LIKE %s 
                    ORDER BY timestamp DESC 
                    LIMIT 10
                ''', (f'test_metric_%',))
                results = cur.fetchall()
        
        conn.commit()
        cur.close()
        conn.close()
        
        duration = (time.time() - start_time) * 1000
        
        return jsonify({
            'type': 'database_intensive',
            'operations': operations,
            'duration_ms': duration
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/combined-stress')
def api_combined_stress():
    duration = int(request.args.get('duration', 10))  # seconds
    start_time = time.time()
    results = []
    
    # Start multiple threads for combined stress
    def stress_worker(worker_id):
        worker_results = []
        end_time = start_time + duration
        
        while time.time() < end_time:
            # CPU task
            cpu_result, cpu_duration = cpu_intensive_task(100000)
            worker_results.append({
                'worker_id': worker_id,
                'type': 'cpu',
                'duration_ms': cpu_duration
            })
            
            # Memory task
            mem_result, mem_duration = memory_intensive_task(5)
            worker_results.append({
                'worker_id': worker_id,
                'type': 'memory',
                'duration_ms': mem_duration
            })
            
            # Database task
            try:
                conn = psycopg2.connect(**DB_CONFIG)
                cur = conn.cursor()
                for i in range(10):
                    cur.execute('''
                        INSERT INTO performance_data (metric_name, metric_value, metadata)
                        VALUES (%s, %s, %s)
                    ''', (f'stress_test_{worker_id}', random.uniform(0, 100), json.dumps({'worker': worker_id})))
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                print(f"DB error in worker {worker_id}: {e}")
        
        results.extend(worker_results)
    
    # Start stress workers
    threads = []
    for i in range(5):  # 5 concurrent workers
        thread = threading.Thread(target=stress_worker, args=(i,))
        thread.start()
        threads.append(thread)
    
    # Wait for all workers
    for thread in threads:
        thread.join()
    
    total_duration = (time.time() - start_time) * 1000
    
    return jsonify({
        'type': 'combined_stress',
        'duration_seconds': duration,
        'total_duration_ms': total_duration,
        'operations_performed': len(results),
        'cache_size': len(memory_cache),
        'computation_results': len(computation_results)
    })

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=80, debug=False)