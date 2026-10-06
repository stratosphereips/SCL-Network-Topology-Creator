FROM python:3.12-alpine

RUN apk add --no-cache docker-cli docker-cli-buildx docker-cli-compose

WORKDIR /app

COPY app.py /app/app.py
COPY connections.json /app/connections.json
# federation image build sources (service + SLIPS layer) and the static attacker
COPY federation /app/federation
COPY attacker /app/attacker

EXPOSE 9002

CMD ["python", "/app/app.py"]
