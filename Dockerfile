FROM python:3.12-alpine

RUN apk add --no-cache docker-cli docker-cli-compose

WORKDIR /app

COPY app.py /app/app.py

EXPOSE 9002

CMD ["python", "/app/app.py"]
