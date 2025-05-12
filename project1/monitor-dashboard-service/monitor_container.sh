#!/bin/bash
#
# Container Monitoring Script
# Monitors Docker container resources and application health
#
# Purpose: This script provides comprehensive monitoring for Docker containers,
# including resource usage tracking, health checks, alerting, and live visualization
#
# Dependencies: docker, curl, bc, awk, tput
# Author: Your Name
# Version: 1.0
# Last Updated: 2024
#

# ========================================
# CONFIGURATION SECTION
# ========================================

# Container name to monitor - can be overridden by environment variable
# ${variable:-default} - Use default if variable is unset or empty
# Example: CONTAINER_NAME="nginx-server" ./monitor.sh
CONTAINER_NAME="${CONTAINER_NAME:-flask-app}"

# Log file paths - adjust these based on your system requirements
LOG_FILE="/var/log/container_monitor.log"         # General monitoring logs
ALERT_LOG="/var/log/container_alerts.log"         # Alert-specific logs
METRICS_FILE="/var/log/container_metrics.csv"     # CSV file for metrics data

# Alert thresholds - these values trigger alerts when exceeded
# Set these via environment variables or modify defaults here
CPU_THRESHOLD="$CPU_THRESHOLD"                    # CPU usage percentage (e.g., 40)
MEMORY_THRESHOLD="$MEMORY_THRESHOLD"              # Memory usage percentage (e.g., 80)
RESPONSE_TIME_THRESHOLD="$RESPONSE_TIME_THRESHOLD" # Response time in milliseconds (e.g., 1000)

# ========================================
# INITIALIZATION FUNCTIONS
# ========================================

# Initialize log files and ensure they exist with proper structure
# This function is called at the start of monitoring to prepare the logging system
initialize_logs() {
    # Create log files if they don't exist
    touch "$LOG_FILE" "$ALERT_LOG" "$METRICS_FILE"
    
    # If metrics file is empty, add CSV header
    if [ ! -s "$METRICS_FILE" ]; then
        echo "timestamp,cpu_percent,memory_usage_mb,memory_percent,response_time_ms,status" > "$METRICS_FILE"
    fi
}

# ========================================
# LOGGING FUNCTIONS
# ========================================

# General logging function for all monitoring activities
# Parameters:
#   $1 - Log level (INFO, ERROR, WARNING, etc.)
#   $2 - Log message
log_message() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Log to file and display on console using tee
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# Alert-specific logging function for threshold violations
# Parameters:
#   $1 - Alert type (High CPU, Memory, etc.)
#   $2 - Detailed alert message
send_alert() {
    local alert_type="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Log alert to both alert log and console
    echo "[$timestamp] ALERT: $alert_type - $message" | tee -a "$ALERT_LOG"
    
    # Here you could add additional alert mechanisms:
    # - Send email: mail -s "Container Alert: $alert_type" admin@example.com <<< "$message"
    # - Send to Slack: curl -X POST -H 'Content-type: application/json' --data "{\"text\":\"$message\"}" YOUR_SLACK_WEBHOOK_URL
    # - Send to monitoring system: curl -X POST monitoring-api.com/alert -d "type=$alert_type&message=$message"
}

# ========================================
# CONTAINER STATUS FUNCTIONS
# ========================================

# Check if the container is currently running
# Returns: "running" if container is active, "stopped" otherwise
check_container_status() {
    # List all running containers and check if our container is among them
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "running"
    else
        echo "stopped"
    fi
}

# Get detailed container resource statistics
# Returns: Comma-separated values of CPU%, Memory MB, Memory%
get_container_stats() {
    # Get container stats in JSON format, suppress errors for missing containers
    local stats=$(docker stats --no-stream --format "{{json .}}" "$CONTAINER_NAME" 2>/dev/null)
    
    # If container doesn't exist or no stats available, return zeros
    if [ -z "$stats" ]; then
        echo "0,0,0"
        return
    fi
    
    # Extract CPU percentage from JSON (remove % sign for calculations)
    local cpu=$(echo "$stats" | grep -o '"CPUPerc":"[^"]*"' | cut -d'"' -f4 | tr -d '%')
    
    # Extract memory usage and limit from the MemUsage field
    local mem_usage=$(echo "$stats" | grep -o '"MemUsage":"[^"]*"' | cut -d'"' -f4 | cut -d'/' -f1)
    local mem_limit=$(echo "$stats" | grep -o '"MemUsage":"[^"]*"' | cut -d'"' -f4 | cut -d'/' -f2)
    
    # Convert memory values to MB (handles both MiB and GiB units)
    local mem_usage_mb=$(echo "$mem_usage" | sed 's/MiB//' | sed 's/GiB/*1024/' | bc 2>/dev/null || echo "0")
    local mem_limit_mb=$(echo "$mem_limit" | sed 's/MiB//' | sed 's/GiB/*1024/' | bc 2>/dev/null || echo "256")
    
    # Calculate memory usage percentage
    local mem_percent=0
    if [ "$mem_limit_mb" -gt 0 ]; then
        mem_percent=$(awk "BEGIN {printf \"%.2f\", ($mem_usage_mb / $mem_limit_mb) * 100}")
    fi
    
    # Return comma-separated values
    echo "$cpu,$mem_usage_mb,$mem_percent"
}

# ========================================
# APPLICATION HEALTH CHECK FUNCTIONS
# ========================================

# Check application health via HTTP endpoint
# Returns: Response time in ms and health status
check_app_health() {
    # Record start time in milliseconds
    local start_time=$(date +%s%3N)
    
    # Make HTTP request to health endpoint
    # Assumes the container exposes a /health endpoint on port 80
    # The response includes both body and HTTP status code
    local response=$(curl -s -w "\n%{http_code}" http://${CONTAINER_NAME}:80/health 2>/dev/null)
    
    # Record end time
    local end_time=$(date +%s%3N)
    
    # Extract HTTP status code (last line of response)
    local http_code=$(echo "$response" | tail -n1)
    
    # Calculate response time
    local response_time=$((end_time - start_time))
    
    # Determine health status based on HTTP code
    if [ "$http_code" = "200" ]; then
        echo "$response_time,healthy"
    else
        echo "$response_time,unhealthy"
    fi
}

# ========================================
# MAIN MONITORING FUNCTION
# ========================================

# Core monitoring function that performs all checks
monitor_container() {
    log_message "INFO" "Starting container monitoring for $CONTAINER_NAME"
    
    # Verify container exists (running or stopped)
    if ! docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_message "ERROR" "Container $CONTAINER_NAME not found"
        return 1
    fi
    
    # Check if container is running
    local status=$(check_container_status)
    if [ "$status" != "running" ]; then
        send_alert "Container Down" "Container $CONTAINER_NAME is not running"
        return 1
    fi
    
    # Collect resource statistics
    IFS=',' read -r cpu mem_usage_mb mem_percent <<< "$(get_container_stats)"
    
    # Perform health check
    IFS=',' read -r response_time app_status <<< "$(check_app_health)"
    
    # Record metrics to CSV file
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "$timestamp,$cpu,$mem_usage_mb,$mem_percent,$response_time,$app_status" >> "$METRICS_FILE"
    
    # Log current status
    log_message "INFO" "CPU: ${cpu}%, Memory: ${mem_usage_mb}MB (${mem_percent}%), Response Time: ${response_time}ms, Status: $app_status"
    
    # Check thresholds and trigger alerts if needed
    # CPU threshold check
    if (( $(echo "$cpu > $CPU_THRESHOLD" | bc -l 2>/dev/null) )); then
        send_alert "High CPU" "CPU usage is ${cpu}% (threshold: ${CPU_THRESHOLD}%)"
    fi
    
    # Memory threshold check
    if (( $(echo "$mem_percent > $MEMORY_THRESHOLD" | bc -l 2>/dev/null) )); then
        send_alert "High Memory" "Memory usage is ${mem_percent}% (threshold: ${MEMORY_THRESHOLD}%)"
    fi
    
    # Response time threshold check
    if [ "$response_time" -gt "$RESPONSE_TIME_THRESHOLD" ]; then
        send_alert "Slow Response" "Response time is ${response_time}ms (threshold: ${RESPONSE_TIME_THRESHOLD}ms)"
    fi
    
    # Application health check
    if [ "$app_status" != "healthy" ]; then
        send_alert "Application Unhealthy" "Application health check failed"
    fi
}

# ========================================
# REPORTING FUNCTIONS
# ========================================

# Generate a comprehensive monitoring report
generate_report() {
    # Create timestamped report file
    local report_file="/var/log/container_report_$(date +%Y%m%d_%H%M%S).txt"
    
    # Write report content
    {
        echo "Container Monitoring Report"
        echo "=========================="
        echo "Generated: $(date)"
        echo "Container: $CONTAINER_NAME"
        echo ""
        echo "Summary Statistics:"
        echo "-------------------"
        
        # Calculate statistics if metrics file exists
        if [ -f "$METRICS_FILE" ]; then
            # Calculate average CPU usage
            local avg_cpu=$(awk -F',' 'NR>1 {sum+=$2; count++} END {if(count>0) printf "%.2f", sum/count; else print "0"}' "$METRICS_FILE")
            
            # Calculate average memory usage percentage
            local avg_mem=$(awk -F',' 'NR>1 {sum+=$4; count++} END {if(count>0) printf "%.2f", sum/count; else print "0"}' "$METRICS_FILE")
            
            # Calculate average response time
            local avg_response=$(awk -F',' 'NR>1 {sum+=$5; count++} END {if(count>0) printf "%.0f", sum/count; else print "0"}' "$METRICS_FILE")
            
            echo "Average CPU Usage: ${avg_cpu}%"
            echo "Average Memory Usage: ${avg_mem}%"
            echo "Average Response Time: ${avg_response}ms"
            echo ""
            echo "Recent Alerts:"
            echo "--------------"
            # Show last 10 alerts
            tail -10 "$ALERT_LOG" 2>/dev/null || echo "No recent alerts"
        fi
    } > "$report_file"
    
    log_message "INFO" "Report generated: $report_file"
    echo "$report_file"
}

# ========================================
# VISUALIZATION FUNCTIONS
# ========================================

# Draw a colored progress bar based on percentage value
# Parameters:
#   $1 - Value (0-100)
#   $2 - Bar width in characters
draw_bar() {
    local value=$1
    local width=$2
    
    # Calculate filled and empty portions
    local filled=$(printf "%.0f" $(echo "$value * $width / 100" | bc -l 2>/dev/null || echo "0"))
    local empty=$((width - filled))
    
    # Select color based on value thresholds
    local color="\e[32m"  # Green (0-60%)
    if (( $(echo "$value > 80" | bc -l 2>/dev/null || echo "0") )); then
        color="\e[31m"    # Red (>80%)
    elif (( $(echo "$value > 60" | bc -l 2>/dev/null || echo "0") )); then
        color="\e[33m"    # Yellow (60-80%)
    fi
    
    # Draw the bar using Unicode block characters
    echo -en "${color}"
    printf '▓%.0s' $(seq 1 $filled)
    echo -en "\e[0m"
    printf '░%.0s' $(seq 1 $empty)
    echo ""
}

# ========================================
# LIVE MONITORING MODE
# ========================================

# Interactive live monitoring with visual display
live_monitor() {
    initialize_logs
    log_message "INFO" "Starting live monitoring mode"
    
    # Clear terminal screen
    clear
    
    # Setup clean exit on Ctrl+C
    trap 'echo -e "\n\nExiting live monitor..."; exit 0' SIGINT
    
    # Main monitoring loop
    while true; do
        # Reset cursor position to top of terminal
        tput cup 0 0
        
        # Display header with timestamp
        echo "╔════════════════════════════════════════════════════════════════════╗"
        echo "║              Container Live Monitor - $(date '+%Y-%m-%d %H:%M:%S')              ║"
        echo "╚════════════════════════════════════════════════════════════════════╝"
        echo ""
        
        # Check container status
        local status=$(check_container_status)
        if [ "$status" != "running" ]; then
            echo "🔴 Container Status: STOPPED"
            echo ""
            echo "Waiting for container to start..."
            sleep 2
            continue
        fi
        
        # Collect current metrics
        IFS=',' read -r cpu mem_usage_mb mem_percent <<< "$(get_container_stats)"
        IFS=',' read -r response_time app_status <<< "$(check_app_health)"
        
        # Display container status
        echo "🟢 Container Status: RUNNING"
        echo ""
        echo "📊 Resource Usage:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        # CPU usage visualization
        echo -n "CPU Usage:     "
        printf "%5.1f%% " "$cpu"
        draw_bar "$cpu" 50
        
        # Memory usage visualization
        echo -n "Memory Usage:  "
        printf "%5.1f%% " "$mem_percent"
        draw_bar "$mem_percent" 50
        
        # Display performance metrics
        echo ""
        echo "📈 Performance Metrics:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "Memory Used:     ${mem_usage_mb} MB"
        echo "Response Time:   ${response_time} ms"
        echo "App Health:      ${app_status^^}"  # Convert to uppercase
        
        # Alert section
        echo ""
        echo "⚠️  Alerts:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        local alerts=0
        
        # Check each threshold and display alerts
        if (( $(echo "$cpu > $CPU_THRESHOLD" | bc -l 2>/dev/null || echo "0") )); then
            echo "🔴 HIGH CPU: ${cpu}% (threshold: ${CPU_THRESHOLD}%)"
            ((alerts++))
        fi
        
        if (( $(echo "$mem_percent > $MEMORY_THRESHOLD" | bc -l 2>/dev/null || echo "0") )); then
            echo "🔴 HIGH MEMORY: ${mem_percent}% (threshold: ${MEMORY_THRESHOLD}%)"
            ((alerts++))
        fi
        
        if [ "$response_time" -gt "$RESPONSE_TIME_THRESHOLD" ]; then
            echo "🔴 SLOW RESPONSE: ${response_time}ms (threshold: ${RESPONSE_TIME_THRESHOLD}ms)"
            ((alerts++))
        fi
        
        if [ "$app_status" != "healthy" ]; then
            echo "🔴 APPLICATION UNHEALTHY"
            ((alerts++))
        fi
        
        # Show all clear if no alerts
        if [ "$alerts" -eq 0 ]; then
            echo "✅ All systems normal"
        fi
        
        # Display recent log entries
        echo ""
        echo "📋 Recent Activity:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        tail -3 "$LOG_FILE" 2>/dev/null | sed 's/^/  /'  # Indent log entries
        
        # User instructions
        echo ""
        echo "Press Ctrl+C to exit"
        
        # Perform monitoring (logs metrics)
        monitor_container
        
        # Refresh interval
        sleep 2
    done
}

# ========================================
# MAIN EXECUTION FUNCTION
# ========================================

# Main function to handle command line arguments and execute appropriate mode
main() {
    # Default to 'monitor' if no argument provided
    case "${1:-monitor}" in
        monitor)
            # Single monitoring check
            initialize_logs
            monitor_container
            ;;
        report)
            # Generate monitoring report
            generate_report
            ;;
        continuous)
            # Continuous monitoring mode (background-friendly)
            initialize_logs
            log_message "INFO" "Starting continuous monitoring (Ctrl+C to stop)"
            while true; do
                monitor_container
                sleep 60  # Check every minute
            done
            ;;
        live)
            # Interactive live monitoring with visualization
            live_monitor
            ;;
        *)
            # Display usage information for invalid arguments
            echo "Usage: $0 [monitor|report|continuous|live]"
            echo "  monitor    - Single monitoring check"
            echo "  report     - Generate monitoring report"
            echo "  continuous - Continuous monitoring (60s interval)"
            echo "  live       - Live monitoring with visual display"
            exit 1
            ;;
    esac
}

# ========================================
# SCRIPT ENTRY POINT
# ========================================

# Execute main function with all command line arguments
main "$@"