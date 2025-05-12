#!/usr/bin/env python3
from flask import Flask, render_template, jsonify
import subprocess
import json
import csv
import os
from datetime import datetime

app = Flask(__name__)

# Configuration
CONTAINER_NAME = os.getenv('CONTAINER_NAME', 'monitored-app')
METRICS_FILE = '/var/log/container_metrics.csv'
ALERTS_FILE = '/var/log/container_alerts.log'

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
            
            return {
                'cpu': cpu,
                'memory_percent': mem_percent,
                'memory_used': mem_used,
                'memory_limit': mem_limit,
                'status': 'running'
            }
    except Exception as e:
        print(f"Error getting stats: {e}")
    
    return {
        'cpu': 0,
        'memory_percent': 0,
        'memory_used': 0,
        'memory_limit': 0,
        'status': 'error'
    }

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
            height: 400px;
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
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Container Monitor Dashboard</h1>
            <p>Real-time monitoring for ''' + CONTAINER_NAME + '''</p>
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
        </div>
        
        <div class="alerts">
            <h3>Recent Alerts</h3>
            <div id="alerts-list">No alerts</div>
        </div>
        
        <div class="chart-container">
            <canvas id="metrics-chart"></canvas>
        </div>
    </div>
    
    <script>
        // Initialize Chart
        const ctx = document.getElementById('metrics-chart').getContext('2d');
        const chart = new Chart(ctx, {
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
            
            // Update chart
            fetch('/api/history')
                .then(response => response.json())
                .then(history => {
                    const timestamps = history.map(item => 
                        new Date(item.timestamp).toLocaleTimeString());
                    const cpuData = history.map(item => parseFloat(item.cpu_percent));
                    const memoryData = history.map(item => parseFloat(item.memory_percent));
                    
                    chart.data.labels = timestamps;
                    chart.data.datasets[0].data = cpuData;
                    chart.data.datasets[1].data = memoryData;
                    chart.update();
                });
        }
        
        // Update every 2 seconds
        updateDashboard();
        setInterval(updateDashboard, 2000);
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)