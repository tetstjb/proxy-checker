FROM python:3.13-slim

RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    ca-certificates

RUN curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | bash

RUN apt-get install -y speedtest

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
