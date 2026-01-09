
FROM python:3.11-slim

WORKDIR /app

COPY requirements.gateway.txt .
RUN pip install --no-cache-dir -r requirements.gateway.txt

COPY . .

# Expose Gateway Port
EXPOSE 8000
# Expose Mock Port (optional)
EXPOSE 8001

CMD ["python", "gateway.py"]
