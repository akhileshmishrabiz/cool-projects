#!/usr/bin/env python3
from flask import Flask, render_template, jsonify, request
import subprocess
import json
import csv
import os
import time
from datetime import datetime, timedelta

app = Flask(__name__)

# Configuration
CONTAINER_NAME = os.getenv('CONTAINER_NAME', 'monitored-app')
METRICS_FILE = '/var/log/container_metrics.csv'
ALERTS_FILE = '/var/log/container_alerts.log'
# Default collection frequency in seconds
DEFAULT_COLLECTION_FREQUENCY = int(os.getenv('COLLECTION_FREQUENCY', '30'))
collection_frequency = DEFAULT_COLLECTION_FREQUENCY

# Store uptime data - initialize with some default values
uptime_data = []
latency_data = []

def get_container_stats():
    """Get current container statistics"""
    try:
        # Get container stats
        cmd = f"docker stats --no-stream --format '{{{{json .}}}}' {CONTAINER_NAME}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout:
            stats = json.loads(result.stdout)
            
            # Parse CPU percentage
            cpu = float(stats.get('CPUPerc', '0%').rstrip('%'))
            
            # Parse memory
            mem_usage = stats.get('MemUsage', '0MiB / 0MiB')
            mem_parts = mem_usage.split(' / ')
            mem_used = mem_parts[0].replace('MiB', '').replace('GiB', '')
            mem_limit = mem_parts[1].replace('MiB', '').replace('GiB', '')
            
            # Calculate memory percentage
            try:
                mem_percent = (float(mem_used) / float(mem_limit)) * 100
            except:
                mem_percent = 0
            
            # Check if container is running - for uptime calculation
            status = "running"
            uptime_value = 100  # 100% uptime if running
            
            # Calculate response time
            response_time = check_app_response_time()
            
            # Update uptime and latency data
            update_uptime_data(uptime_value)
            update_latency_data(response_time)
            
            return {
                'cpu': cpu,
                'memory_percent': mem_percent,
                'memory_used': mem_used,
                'memory_limit': mem_limit,
                'status': status,
                'response_time': response_time
            }
    except Exception as e:
        print(f"Error getting stats: {e}")
        # Update uptime data with downtime
        update_uptime_data(0)  # 0% uptime if error
    
    return {
        'cpu': 0,
        'memory_percent': 0,
        'memory_used': 0,
        'memory_limit': 0,
        'status': 'error',
        'response_time': 0
    }

def check_app_response_time():
    """Check application response time in milliseconds"""
    try:
        # Record start time in milliseconds
        start_time = time.time() * 1000
        
        # Make HTTP request to health endpoint
        url = f"http://{CONTAINER_NAME}/health"
        cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{time_total}", "-m", "5", url]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Convert to milliseconds
            response_time = float(result.stdout) * 1000
            return response_time
        else:
            return 0
    except Exception as e:
        print(f"Error checking response time: {e}")
        return 0

def update_uptime_data(uptime_value):
    """Update uptime data array with timestamp"""
    global uptime_data
    
    # Add current uptime value with timestamp
    timestamp = datetime.now()
    uptime_data.append({
        'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'value': uptime_value
    })
    
    # Keep only the last 100 data points
    if len(uptime_data) > 100:
        uptime_data = uptime_data[-100:]

def update_latency_data(latency_value):
    """Update latency data array with timestamp"""
    global latency_data
    
    # Add current latency value with timestamp
    timestamp = datetime.now()
    latency_data.append({
        'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        'value': latency_value
    })
    
    # Keep only the last 100 data points
    if len(latency_data) > 100:
        latency_data = latency_data[-100:]

def get_metrics_history():
    """Get historical metrics from CSV file"""
    metrics = []
    if os.path.exists(METRICS_FILE):
        try:
            with open(METRICS_FILE, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    metrics.append(row)
            # Return last 50 entries
            return metrics[-50:] if len(metrics) > 50 else metrics
        except:
            pass
    return []

def get_recent_alerts():
    """Get recent alerts"""
    alerts = []
    if os.path.exists(ALERTS_FILE):
        try:
            with open(ALERTS_FILE, 'r') as f:
                lines = f.readlines()
            # Return last 10 alerts
            return [line.strip() for line in lines[-10:]]
        except:
            pass
    return []

@app.route('/')
def dashboard():
    return '''
<!DOCTYPE html>
<html>
<head>
    <title>Container Monitor Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 0; 
            padding: 20px; 
            background-color: #f5f5f5;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { 
            background-color: #2c3e50; 
            color: white; 
            padding: 20px; 
            border-radius: 10px; 
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .metrics { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
            gap: 20px; 
            margin-bottom: 20px;
        }
        .metric-card { 
            background: white; 
            padding: 20px; 
            border-radius: 10px; 
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .metric-value { 
            font-size: 36px; 
            font-weight: bold; 
            margin: 10px 0;
        }
        .metric-label { 
            color: #666; 
            font-size: 14px;
        }
        .gauge { 
            width: 100%; 
            height: 20px; 
            background: #e0e0e0; 
            border-radius: 10px; 
            overflow: hidden;
        }
        .gauge-fill { 
            height: 100%; 
            border-radius: 10px;
            transition: width 0.5s ease;
        }
        .cpu-fill { background: linear-gradient(90deg, #2ecc71, #f39c12, #e74c3c); }
        .memory-fill { background: linear-gradient(90deg, #3498db, #9b59b6, #e74c3c); }
        .alerts { 
            background: white; 
            padding: 20px; 
            border-radius: 10px; 
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .alert-item { 
            padding: 10px; 
            margin: 5px 0; 
            border-left: 4px solid #e74c3c; 
            background: #fff5f5;
        }
        .chart-container { 
            background: white; 
            padding: 20px; 
            border-radius: 10px; 
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            height: 300px;
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 10px;
        }
        .status-running { background-color: #2ecc71; }
        .status-stopped { background-color: #e74c3c; }
        .settings-panel {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .settings-panel label {
            display: block;
            margin-bottom: 5px;
        }
        .settings-panel input {
            margin-bottom: 15px;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 100%;
            max-width: 200px;
        }
        .settings-panel button {
            background: #3498db;
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 4px;
            cursor: pointer;
        }
        .settings-panel button:hover {
            background: #2980b9;
        }
        .tabs {
            display: flex;
            margin-bottom: 20px;
        }
        .tab {
            padding: 10px 20px;
            cursor: pointer;
            background: #e0e0e0;
            border-radius: 5px 5px 0 0;
            margin-right: 5px;
        }
        .tab.active {
            background: white;
            font-weight: bold;
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>Container Monitor Dashboard</h1>
                <p>Real-time monitoring for ''' + CONTAINER_NAME + '''</p>
            </div>
            <div>
                <button onclick="toggleSettings()">⚙️ Settings</button>
            </div>
        </div>
        
        <div id="settings-panel" class="settings-panel" style="display: none;">
            <h3>Dashboard Settings</h3>
            <label for="collection-frequency">Data Collection Frequency (seconds):</label>
            <input type="number" id="collection-frequency" value="''' + str(DEFAULT_COLLECTION_FREQUENCY) + '''" min="5" max="300">
            <button onclick="updateSettings()">Update</button>
        </div>
        
        <div class="metrics">
            <div class="metric-card">
                <div class="metric-label">Container Status</div>
                <div class="metric-value">
                    <span class="status-indicator" id="status-indicator"></span>
                    <span id="container-status">Loading...</span>
                </div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">CPU Usage</div>
                <div class="metric-value" id="cpu-value">0%</div>
                <div class="gauge">
                    <div class="gauge-fill cpu-fill" id="cpu-gauge" style="width: 0%"></div>
                </div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">Memory Usage</div>
                <div class="metric-value" id="memory-value">0%</div>
                <div class="gauge">
                    <div class="gauge-fill memory-fill" id="memory-gauge" style="width: 0%"></div>
                </div>
                <div class="metric-label" id="memory-details">0 MB / 0 MB</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">Response Time</div>
                <div class="metric-value" id="response-time">0 ms</div>
            </div>
        </div>
        
        <div class="alerts">
            <h3>Recent Alerts</h3>
            <div id="alerts-list">No alerts</div>
        </div>
        
        <div class="tabs">
            <div class="tab active" onclick="showTab('resource-metrics')">Resource Metrics</div>
            <div class="tab" onclick="showTab('uptime-metrics')">Uptime</div>
            <div class="tab" onclick="showTab('latency-metrics')">Latency</div>
        </div>
        
        <div id="resource-metrics" class="tab-content active">
            <div class="chart-container">
                <canvas id="metrics-chart"></canvas>
            </div>
        </div>
        
        <div id="uptime-metrics" class="tab-content">
            <div class="chart-container">
                <canvas id="uptime-chart"></canvas>
            </div>
        </div>
        
        <div id="latency-metrics" class="tab-content">
            <div class="chart-container">
                <canvas id="latency-chart"></canvas>
            </div>
        </div>
    </div>
    
    <script>
        // Initialize Charts
        const metricsCtx = document.getElementById('metrics-chart').getContext('2d');
        const metricsChart = new Chart(metricsCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'CPU %',
                    data: [],
                    borderColor: '#3498db',
                    tension: 0.1
                }, {
                    label: 'Memory %',
                    data: [],
                    borderColor: '#e74c3c',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100
                    }
                }
            }
        });
        
        const uptimeCtx = document.getElementById('uptime-chart').getContext('2d');
        const uptimeChart = new Chart(uptimeCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Uptime %',
                    data: [],
                    borderColor: '#2ecc71',
                    backgroundColor: 'rgba(46, 204, 113, 0.1)',
                    fill: true,
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100
                    }
                }
            }
        });
        
        const latencyCtx = document.getElementById('latency-chart').getContext('2d');
        const latencyChart = new Chart(latencyCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Response Time (ms)',
                    data: [],
                    borderColor: '#f39c12',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
        
        // Show/hide settings panel
        function toggleSettings() {
            const panel = document.getElementById('settings-panel');
            panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
        }
        
        // Update settings
        function updateSettings() {
            const frequency = document.getElementById('collection-frequency').value;
            fetch('/api/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    collection_frequency: frequency
                }),
            })
            .then(response => response.json())
            .then(data => {
                alert('Settings updated successfully!');
                updateInterval = data.collection_frequency * 1000;
                clearInterval(dashboardInterval);
                dashboardInterval = setInterval(updateDashboard, updateInterval);
            });
        }
        
        // Switch between tabs
        function showTab(tabId) {
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Deactivate all tabs
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab content
            document.getElementById(tabId).classList.add('active');
            
            // Activate selected tab
            event.currentTarget.classList.add('active');
        }
        
        // Update dashboard
        function updateDashboard() {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    // Update status
                    const statusIndicator = document.getElementById('status-indicator');
                    const statusText = document.getElementById('container-status');
                    
                    if (data.status === 'running') {
                        statusIndicator.className = 'status-indicator status-running';
                        statusText.textContent = 'Running';
                    } else {
                        statusIndicator.className = 'status-indicator status-stopped';
                        statusText.textContent = 'Stopped';
                    }
                    
                    // Update CPU
                    document.getElementById('cpu-value').textContent = data.cpu.toFixed(1) + '%';
                    document.getElementById('cpu-gauge').style.width = data.cpu + '%';
                    
                    // Update Memory
                    document.getElementById('memory-value').textContent = data.memory_percent.toFixed(1) + '%';
                    document.getElementById('memory-gauge').style.width = data.memory_percent + '%';
                    document.getElementById('memory-details').textContent = 
                        `${data.memory_used} MB / ${data.memory_limit} MB`;
                        
                    // Update Response Time
                    document.getElementById('response-time').textContent = 
                        `${Math.round(data.response_time)} ms`;
                });
            
            // Update alerts
            fetch('/api/alerts')
                .then(response => response.json())
                .then(alerts => {
                    const alertsList = document.getElementById('alerts-list');
                    if (alerts.length === 0) {
                        alertsList.innerHTML = 'No recent alerts';
                    } else {
                        alertsList.innerHTML = alerts.map(alert => 
                            `<div class="alert-item">${alert}</div>`
                        ).join('');
                    }
                });
            
            // Update resource metrics chart
            fetch('/api/history')
                .then(response => response.json())
                .then(history => {
                    const timestamps = history.map(item => 
                        new Date(item.timestamp).toLocaleTimeString());
                    const cpuData = history.map(item => parseFloat(item.cpu_percent));
                    const memoryData = history.map(item => parseFloat(item.memory_percent));
                    
                    metricsChart.data.labels = timestamps;
                    metricsChart.data.datasets[0].data = cpuData;
                    metricsChart.data.datasets[1].data = memoryData;
                    metricsChart.update();
                });
                
            // Update uptime chart
            fetch('/api/uptime')
                .then(response => response.json())
                .then(uptimeData => {
                    const timestamps = uptimeData.map(item => 
                        new Date(item.timestamp).toLocaleTimeString());
                    const values = uptimeData.map(item => parseFloat(item.value));
                    
                    uptimeChart.data.labels = timestamps;
                    uptimeChart.data.datasets[0].data = values;
                    uptimeChart.update();
                });
                
            // Update latency chart
            fetch('/api/latency')
                .then(response => response.json())
                .then(latencyData => {
                    const timestamps = latencyData.map(item => 
                        new Date(item.timestamp).toLocaleTimeString());
                    const values = latencyData.map(item => parseFloat(item.value));
                    
                    latencyChart.data.labels = timestamps;
                    latencyChart.data.datasets[0].data = values;
                    latencyChart.update();
                });
        }
        
        // Initial update interval
        let updateInterval = ''' + str(DEFAULT_COLLECTION_FREQUENCY * 1000) + ''';
        
        // Update dashboard initially and set interval
        updateDashboard();
        let dashboardInterval = setInterval(updateDashboard, updateInterval);
    </script>
</body>
</html>
'''

@app.route('/api/stats')
def api_stats():
    return jsonify(get_container_stats())

@app.route('/api/alerts')
def api_alerts():
    return jsonify(get_recent_alerts())

@app.route('/api/history')
def api_history():
    return jsonify(get_metrics_history())

@app.route('/api/uptime')
def api_uptime():
    return jsonify(uptime_data)

@app.route('/api/latency')
def api_latency():
    return jsonify(latency_data)

@app.route('/api/settings', methods=['POST'])
def api_settings():
    global collection_frequency
    data = request.json
    
    if 'collection_frequency' in data:
        try:
            new_frequency = int(data['collection_frequency'])
            if 5 <= new_frequency <= 300:  # Limit between 5 and 300 seconds
                collection_frequency = new_frequency
                return jsonify({'status': 'success', 'collection_frequency': collection_frequency})
            else:
                return jsonify({'status': 'error', 'message': 'Frequency must be between 5 and 300 seconds'}), 400
        except:
            return jsonify({'status': 'error', 'message': 'Invalid frequency value'}), 400
    
    return jsonify({'status': 'error', 'message': 'Missing required parameters'}), 400

if __name__ == '__main__':
    # Initialize with some default uptime data
    now = datetime.now()
    for i in range(10):
        timestamp = (now - timedelta(minutes=10-i)).strftime('%Y-%m-%d %H:%M:%S')
        uptime_data.append({'timestamp': timestamp, 'value': 100})  # Assume 100% uptime initially
        latency_data.append({'timestamp': timestamp, 'value': 20})  # Assume 20ms latency initially
    
    app.run(host='0.0.0.0', port=8001, debug=True)