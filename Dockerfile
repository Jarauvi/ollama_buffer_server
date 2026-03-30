ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM ${BUILD_FROM}
RUN apk add --no-cache python3 py3-pip
WORKDIR /app
COPY requirements.txt .
RUN pip3 install -r requirements.txt --break-system-packages
COPY . .
RUN chmod a+x /app/run.sh
CMD [ "/app/run.sh" ]