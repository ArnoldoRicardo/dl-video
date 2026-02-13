FROM mongo:latest

RUN apt-get update && \
    apt-get install -y mongodb-org && \
    apt-get clean
