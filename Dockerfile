# CAVEAT: changing this file need to be approved by SRE team.

FROM docker.yektanet.tech/base/python:3.9-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENTRYPOINT ["python3", "main.py"]
