FROM python:3.9-alpine

WORKDIR /app
COPY stress_app.py .
RUN pip install requests

CMD ["python", "stress_app.py"]