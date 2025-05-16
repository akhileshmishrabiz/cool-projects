# Container Monitoring System

A comprehensive solution for monitoring Docker containers with real-time metrics visualization, alerts, and performance tracking.

## Overview

This project demonstrates a complete container monitoring solution that provides real-time insights into container health, performance metrics, and system status. The system consists of multiple components working together to collect, process, visualize, and alert on container metrics.

## What This Project Demonstrates

- **Real-time Container Monitoring**: Track CPU, memory usage, and application response time
- **Visual Dashboard**: Interactive charts for performance visualization
- **Status Tracking**: Clear visualization of container uptime/downtime periods
- **Alert System**: Real-time alerts for performance issues and health check failures
- **Email Notifications**: Configurable email alerts for critical issues
- **Stress Testing**: Simulate different load scenarios to test monitoring effectiveness

## Architecture and Flow

The system consists of the following components:

1. **Web Application (flask-app)**
   - A Flask-based web application that serves as the monitored target
   - Includes endpoints that can generate CPU, memory, and database load
   - Provides a /health endpoint for status checking

2. **Monitoring Dashboard (app-monitor)**
   - Collects container metrics using Docker API
   - Processes and stores metrics data
   - Provides a real-time web dashboard for visualization
   - Detects threshold violations and generates alerts

3. **Alert Service**
   - Monitors alert logs for critical issues
   - Aggregates and filters alerts to prevent notification spam
   - Sends email notifications using AWS SES

4. **Stress Generator**
   - Creates configurable loads on the web application
   - Supports different stress profiles (CPU-intensive, memory-intensive, etc.)
   - Helps demonstrate monitoring and alert functionality

5. **Database (PostgreSQL)**
   - Stores application data and metrics
   - Used by the web application for database-intensive operations

## Data Flow

1. The monitoring service collects metrics from Docker at regular intervals
2. Metrics are processed and stored in CSV files and in-memory data structures
3. When thresholds are exceeded, alerts are written to the alert log
4. The dashboard visualizes current and historical metrics through charts
5. The alert service detects new alerts and sends email notifications
6. The stress generator creates load to demonstrate how the system responds

## Key Features

### Dashboard Features

- **Container Status**: Shows if the container is running or stopped
- **CPU Usage**: Real-time CPU percentage with visual gauge
- **Memory Usage**: Memory consumption with percentage and absolute values
- **Response Time**: Application response time in milliseconds
- **Uptime Tracking**: Binary up/down visualization showing exactly when the container was unavailable
- **Latency Chart**: Historical view of response times
- **Resource Metrics**: Combined view of CPU and memory usage trends
- **Alert Display**: Most recent alerts with timestamps

### Alert System Features

- **Threshold-Based Alerts**: Triggers on high CPU, memory, slow response, and health check failures
- **Email Notifications**: Configurable delivery to multiple recipients
- **Alert Aggregation**: Groups similar alerts to prevent notification spam
- **Alert Buffering**: Configurable delay to collect related alerts before sending
- **Rate Limiting**: Cooldown period to prevent excessive notifications
- **Prioritization**: Critical alerts (like container down) bypass aggregation delay

## Setup and Usage

### Prerequisites

- Docker and Docker Compose
- AWS account with SES access (for email alerts)

### Environment Setup

1. Create a `.env` file based on the provided `.env-sample`:

```
# AWS SES Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_key_here
AWS_REGION=ap-south-1

# Email Configuration
SENDER_EMAIL=monitoring@yourdomain.com
RECIPIENT_EMAILS=admin@yourdomain.com,devops@yourdomain.com

# Optional: Alert Configuration (uncomment to override defaults)
# CHECK_INTERVAL=30        # How often to check for new alerts (seconds)
# ALERT_COOLDOWN=300      # Minimum time between similar alerts (seconds)
# BUFFER_TIMEOUT=60       # Time to buffer alerts before sending (seconds)
```

### Starting the System

1. Clone the repository and navigate to the project directory
2. Start the entire stack:
   ```bash
   docker-compose up --build
   ```
   
   Alternatively, run in detached mode:
   ```bash
   docker-compose up -d
   ```

### Accessing the Services

- **Main Application**: http://localhost:8080
- **Monitoring Dashboard**: http://localhost:8001

### Testing Different Load Scenarios

You can generate different types of stress on the system to see how the monitoring responds:

```bash
# CPU-intensive stress
docker-compose run --rm -e STRESS_LEVEL=cpu-intensive stress-generator

# Memory-intensive stress
docker-compose run --rm -e STRESS_LEVEL=memory-intensive stress-generator

# Extreme stress (high load on everything)
docker-compose run --rm -e STRESS_LEVEL=extreme stress-generator
```

## Alert Configuration

The alert service can be configured through environment variables:

- `CHECK_INTERVAL`: How often to check for new alerts (seconds)
- `ALERT_COOLDOWN`: Minimum time between similar alerts (seconds)
- `BUFFER_TIMEOUT`: Time to buffer alerts before sending (seconds)

Threshold values can be configured in the docker-compose.yaml file:

```yaml
monitor:
  environment:
    - CPU_THRESHOLD="40"        # Alert when CPU exceeds this percentage
    - MEMORY_THRESHOLD="50"     # Alert when memory exceeds this percentage
    - RESPONSE_TIME_THRESHOLD=1000  # Alert when response time exceeds this (ms)
```

## Production Considerations

For production deployment, consider the following:

- **Email Sandbox**: AWS SES starts in sandbox mode - verify recipient emails or request production access
- **Secrets Management**: Use Docker secrets or AWS Secrets Manager for credentials
- **Email Templates**: Consider using SES templates for better formatted emails
- **Monitoring**: Add health checks for the alert service itself
- **Persistence**: Mount volumes for logs and metrics to persist between restarts
- **Security**: Run containers with minimal permissions
- **Scaling**: Deploy multiple monitoring instances for high availability

## Troubleshooting

If you encounter issues:

1. Check container logs:
   ```bash
   docker-compose logs monitor
   docker-compose logs alert-service
   ```

2. Verify that the monitored container is running:
   ```bash
   docker ps | grep flask-app
   ```

3. Test the application health endpoint directly:
   ```bash
   curl http://localhost:8080/health
   ```

4. Check alert logs:
   ```bash
   cat logs/container_alerts.log
   ```

## Customization

The system can be customized by:

1. Modifying alert thresholds in docker-compose.yaml
2. Adjusting the dashboard UI in dashboard.py
3. Adding new metrics collection in monitor_container.sh
4. Creating custom stress patterns in stress_app.py

## License

[MIT License](LICENSE)
