FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV OUTPUT_DIR=/data/output
ENV GOTENBERG_URL=http://host.docker.internal:3000
ENV PUBLIC_BASE_URL=http://localhost:8080

EXPOSE 8080

CMD ["python", "app.py"]