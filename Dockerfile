FROM python:3.12.3-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install ytarchive
RUN curl -L https://github.com/Kethsar/ytarchive/releases/download/latest/ytarchive_linux_amd64 -o /usr/local/bin/ytarchive \
    && chmod +x /usr/local/bin/ytarchive

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]