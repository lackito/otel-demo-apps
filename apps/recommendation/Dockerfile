FROM docker.io/library/python:3.14.6-alpine3.23@sha256:b165067c5afc37fa5608a3c05609cc3d51aafd808a30fbfd822ee594fef55ad4 AS build-venv

COPY requirements.txt requirements.txt

RUN python -m venv venv && \
    venv/bin/pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements.txt

RUN venv/bin/opentelemetry-bootstrap -a install

FROM docker.io/library/python:3.14.6-alpine3.23@sha256:b165067c5afc37fa5608a3c05609cc3d51aafd808a30fbfd822ee594fef55ad4

COPY --from=build-venv /venv/ /venv/

WORKDIR /app

COPY demo_pb2_grpc.py .
COPY demo_pb2.py .
COPY logger.py .
COPY metrics.py .
COPY recommendation_server.py .

# Include Python thread stacks if a native dependency crashes.
ENV PYTHONFAULTHANDLER=1

EXPOSE 8080

ENTRYPOINT ["/venv/bin/opentelemetry-instrument", "/venv/bin/python", "recommendation_server.py"]
