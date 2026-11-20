FROM debian:trixie-slim

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        cython3 \
        gcc \
        make \
        python3 \
        python3-build \
        python3-dev \
        python3-matplotlib \
        python3-setuptools \
        python3-wheel \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY . /src
RUN make build
