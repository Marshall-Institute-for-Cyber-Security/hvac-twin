# syntax=docker/dockerfile:1
#
# One image, two services (see compose.yaml): `plant` runs hvac_twin.hmi
# (the twin + its Modbus slave + the HMI HTTP/WS API, all one process,
# same as bare-metal); `attack-console` runs hvac_twin.console. Only the
# `command:` differs between them.
#
# DigiTwin is a public repo, so this repo's own pyproject.toml
# ([tool.uv.sources]) resolves it straight from GitHub -- `uv sync` just
# needs network access and a git client during the build, nothing local.
FROM python:3.12-slim AS base

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /root/HVAC
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY examples ./examples

RUN uv sync --extra modbus --extra console --no-dev

ENV PATH="/root/HVAC/.venv/bin:${PATH}"
