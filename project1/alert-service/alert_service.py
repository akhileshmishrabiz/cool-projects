#!/usr/bin/env python3
import os
import time
import json
import boto3
from datetime import datetime, timedelta
import threading
from collections import defaultdict

class AlertService:
    def __init__(self):
        # AWS SES Configuration
        self.ses_client = boto3.client(
            'ses',
            region_name=os.getenv('AWS_REGION', 'us-east-1'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        
        # Email configuration
        self.sender_email = os.getenv('SENDER_EMAIL', 'monitoring@yourdomain.com')
        self.recipient_emails = os.getenv('RECIPIENT_EMAILS', '').split(',')
        
        # Alert configuration
        self.alert_log = os.getenv('ALERT_LOG', '/var/log/container_alerts.log')
        
        # State directory for writable files
        self.state_dir = '/app/state'
        os.makedirs(self.state_dir, exist_ok=True)
        self.processed_alerts_file = os.path.join(self.state_dir, 'processed_alerts.json')
        
        self.check_interval = int(os.getenv('CHECK_INTERVAL', '30'))  # seconds
        
        # Rate limiting
        self.alert_cooldown = int(os.getenv('ALERT_COOLDOWN', '300'))  # 5 minutes
        self.last_alert_times = defaultdict(lambda: datetime.min)
        self.alert_counts = defaultdict(int)
        
        # Alert aggregation
        self.alert_buffer = defaultdict(list)
        self.buffer_timeout = int(os.getenv('BUFFER_TIMEOUT', '60'))  # seconds
        
        # Load processed alerts
        self.processed_alerts = self.load_processed_alerts()
    
    def load_processed_alerts(self):
        """Load already processed alerts to avoid duplicates"""
        if os.path.exists(self.processed_alerts_file):
            try:
                with open(self.processed_alerts_file, 'r') as f:
                    return set(json.load(f))
            except:
                return set()
        return set()
    
    def save_processed_alerts(self):
        """Save processed alerts to file"""
        try:
            with open(self.processed_alerts_file, 'w') as f:
                json.dump(list(self.processed_alerts), f)
        except Exception as e:
            print(f"Warning: Could not save processed alerts: {e}")
    
    def parse_alert_line(self, line):
        """Parse alert line from log file"""
        try:
            # Expected format: [2024-03-20 10:15:30] ALERT: High CPU - CPU usage is 85% (threshold: 40%)
            parts = line.strip().split('] ALERT: ', 1)
            if len(parts) != 2:
                return None
            
            timestamp_str = parts[0].strip('[')
            alert_content = parts[1]
            
            # Split alert type and message
            alert_parts = alert_content.split(' - ', 1)
            if len(alert_parts) != 2:
                return None
            
            return {
                'timestamp': timestamp_str,
                'alert_type': alert_parts[0],
                'message': alert_parts[1],
                'line': line.strip()
            }
        except Exception as e:
            print(f"Error parsing alert line: {e}")
            return None
    
    def should_send_alert(self, alert_type):
        """Check if alert should be sent based on rate limiting"""
        now = datetime.now()
        last_sent = self.last_alert_times[alert_type]
        
        if (now - last_sent).total_seconds() < self.alert_cooldown:
            return False
        
        return True
    
    def format_email_body(self, alerts):
        """Format email body with alert details"""
        body = f"""
Container Monitoring Alert Summary
==================================

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Container: {os.getenv('CONTAINER_NAME', 'monitored-app')}

Alerts Detected:
---------------
"""
        
        # Group alerts by type
        alerts_by_type = defaultdict(list)
        for alert in alerts:
            alerts_by_type[alert['alert_type']].append(alert)
        
        for alert_type, type_alerts in alerts_by_type.items():
            body += f"\n{alert_type} ({len(type_alerts)} occurrences):\n"
            for alert in type_alerts[-5:]:  # Show last 5 of each type
                body += f"  - [{alert['timestamp']}] {alert['message']}\n"
            if len(type_alerts) > 5:
                body += f"  ... and {len(type_alerts) - 5} more\n"
        
        body += f"""
Action Required:
---------------
Please check the container status and take appropriate action.

Dashboard: http://localhost:8000
Application: http://localhost:8080

Alert Frequency:
---------------
"""
        for alert_type, count in self.alert_counts.items():
            body += f"  - {alert_type}: {count} alerts in last hour\n"
        
        return body
    
    def send_email(self, subject, body):
        """Send email using AWS SES"""
        try:
            response = self.ses_client.send_email(
                Source=self.sender_email,
                Destination={
                    'ToAddresses': self.recipient_emails
                },
                Message={
                    'Subject': {
                        'Data': subject,
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Text': {
                            'Data': body,
                            'Charset': 'UTF-8'
                        }
                    }
                }
            )
            print(f"Email sent successfully: {response['MessageId']}")
            return True
        except Exception as e:
            print(f"Error sending email: {e}")
            return False
    
    def process_alerts(self):
        """Process new alerts from log file"""
        if not os.path.exists(self.alert_log):
            return
        
        new_alerts = []
        
        try:
            with open(self.alert_log, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and line not in self.processed_alerts:
                        alert = self.parse_alert_line(line)
                        if alert:
                            new_alerts.append(alert)
                            self.processed_alerts.add(line)
                            
                            # Update alert counts
                            self.alert_counts[alert['alert_type']] += 1
        except Exception as e:
            print(f"Error reading alert log: {e}")
            return
        
        # Buffer alerts for aggregation
        for alert in new_alerts:
            self.alert_buffer[alert['alert_type']].append(alert)
        
        # Check if we should send buffered alerts
        self.check_and_send_buffered_alerts()
        
        # Save processed alerts
        self.save_processed_alerts()
    
    def check_and_send_buffered_alerts(self):
        """Check and send buffered alerts"""
        now = datetime.now()
        alerts_to_send = []
        
        for alert_type, alerts in list(self.alert_buffer.items()):
            if not alerts:
                continue
            
            # Check if we should send this alert type
            if not self.should_send_alert(alert_type):
                continue
            
            # Check if buffer timeout reached or critical alert
            first_alert_time = datetime.strptime(alerts[0]['timestamp'], '%Y-%m-%d %H:%M:%S')
            time_diff = (now - first_alert_time).total_seconds()
            
            if (time_diff >= self.buffer_timeout or 
                alert_type in ['Container Down', 'Application Unhealthy'] or 
                len(alerts) >= 5):
                
                alerts_to_send.extend(alerts)
                self.last_alert_times[alert_type] = now
                self.alert_buffer[alert_type] = []
        
        if alerts_to_send:
            # Determine email subject based on severity
            critical_alerts = [a for a in alerts_to_send if a['alert_type'] in ['Container Down', 'Application Unhealthy']]
            if critical_alerts:
                subject = f"🚨 CRITICAL: {os.getenv('CONTAINER_NAME', 'Container')} Alert"
            else:
                subject = f"⚠️ WARNING: {os.getenv('CONTAINER_NAME', 'Container')} Alert"
            
            body = self.format_email_body(alerts_to_send)
            self.send_email(subject, body)
    
    def cleanup_old_counts(self):
        """Clean up old alert counts (keep last hour only)"""
        one_hour_ago = datetime.now() - timedelta(hours=1)
        # This is simplified - in production you'd track timestamps for each alert
        # For now, we'll just reset counts periodically
        if hasattr(self, 'last_cleanup') and (datetime.now() - self.last_cleanup).total_seconds() > 3600:
            self.alert_counts.clear()
            self.last_cleanup = datetime.now()
        elif not hasattr(self, 'last_cleanup'):
            self.last_cleanup = datetime.now()
    
    def run(self):
        """Main service loop"""
        print(f"Alert Service started. Monitoring {self.alert_log}")
        print(f"Sending alerts to: {', '.join(self.recipient_emails)}")
        print(f"State directory: {self.state_dir}")
        
        while True:
            try:
                self.process_alerts()
                self.cleanup_old_counts()
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                print("Alert service stopped")
                break
            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(self.check_interval)

if __name__ == "__main__":
    # Check required environment variables
    required_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'SENDER_EMAIL', 'RECIPIENT_EMAILS']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("Required variables:")
        print("  AWS_ACCESS_KEY_ID - AWS access key for SES")
        print("  AWS_SECRET_ACCESS_KEY - AWS secret key")
        print("  SENDER_EMAIL - Verified sender email in SES")
        print("  RECIPIENT_EMAILS - Comma-separated list of recipient emails")
        exit(1)
    
    service = AlertService()
    service.run()