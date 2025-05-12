

cd ~/devops-bootcamp/may-bootcamp/class2/project/app

docker-compose up --build

# or 

docker-compose up -d

# Access the app

Main application: http://localhost:8080

Monitoring dashboard: http://localhost:8000

# CPU-intensive stress
docker-compose run --rm -e STRESS_LEVEL=cpu-intensive stress-generator

# Memory-intensive stress
docker-compose run --rm -e STRESS_LEVEL=memory-intensive stress-generator

# Extreme stress (everything)
docker-compose run --rm -e STRESS_LEVEL=extreme stress-generator





# Alerting system considerations
 we can have alert notification configured in different ways

- Add email sending directly in the bash script by adding a function
- bash can cal a hook that can trigger the alert
- Create a alert service (recommended)
- Integrate it with dashboard service

-> Recommended one is with seperate service

- Decoupled Architecture - Separates monitoring from alerting
- Rate Limiting - Prevents email spam during sustained issues
- Alert Aggregation - Groups related alerts into single emails
- Reliability - Can retry failed email sends
- Easy Configuration - All email settings in one place
- Scalability - Can easily add other notification channels (Slack, SMS, etc.)

-> Production Considerations

- Email Sandbox: AWS SES starts in sandbox mode - verify recipient emails or request production access
- Secrets Management: Use Docker secrets or AWS Secrets Manager for credentials
- Email Templates: Consider using SES templates for better formatted emails
- Monitoring: Add health checks for the alert service itself