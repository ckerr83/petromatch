FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENV SELENIUM_ENABLED=false
EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.simple_auth_main:app --host 0.0.0.0 --port ${PORT:-8080}"]
