# syntax=docker/dockerfile:1.7
FROM python:3.13.5-slim-bookworm AS build-image

RUN apt-get update -y && \
    apt-get install -y --no-install-recommends wget xz-utils unzip && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get purge --auto-remove && \
    apt-get clean

RUN wget -q https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz

RUN mkdir -p ffmpeg-tmp && \
    tar -xf ffmpeg-release-amd64-static.tar.xz --strip-components 1 -C ffmpeg-tmp && \
    cp -v ffmpeg-tmp/ffmpeg ffmpeg-tmp/ffprobe ffmpeg-tmp/qt-faststart /usr/local/bin && \
    rm -rf ffmpeg-tmp ffmpeg-release-amd64-static.tar.xz

RUN mkdir -p /home/mediacms.io/bento4 && \
    wget -q --tries=5 --waitretry=10 --timeout=30 https://www.bok.net/Bento4/binaries/Bento4-SDK-1-6-0-637.x86_64-unknown-linux.zip && \
    unzip Bento4-SDK-1-6-0-637.x86_64-unknown-linux.zip -d /home/mediacms.io/bento4 && \
    mv /home/mediacms.io/bento4/Bento4-SDK-1-6-0-637.x86_64-unknown-linux/* /home/mediacms.io/bento4/ && \
    rm -rf /home/mediacms.io/bento4/Bento4-SDK-1-6-0-637.x86_64-unknown-linux && \
    rm -rf /home/mediacms.io/bento4/docs && \
    rm Bento4-SDK-1-6-0-637.x86_64-unknown-linux.zip

FROM node:20-bookworm-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/yarn.lock ./
COPY frontend/packages/scripts/ ./packages/scripts/
RUN --mount=type=cache,target=/root/.npm \
    npm install --legacy-peer-deps --cache /root/.npm && \
    cd packages/scripts && \
    npm install --legacy-peer-deps --cache /root/.npm && \
    npm run build
COPY frontend/ ./
RUN npm run dist

FROM python:3.13.5-slim-bookworm AS runtime-deps

SHELL ["/bin/bash", "-c"]

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV CELERY_APP='cms'
ENV VIRTUAL_ENV=/home/mediacms.io
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN apt-get update -y && \
    apt-get -y upgrade && \
    apt-get install --no-install-recommends -y \
        supervisor \
        nginx \
        imagemagick \
        procps \
        build-essential \
        pkg-config \
        zlib1g-dev \
        zlib1g \
        libxml2-dev \
        libxmlsec1-dev \
        libxmlsec1-openssl \
        libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /home/mediacms.io/mediacms/{logs} && \
    cd /home/mediacms.io && \
    python3 -m venv $VIRTUAL_ENV

COPY requirements.txt requirements-dev.txt ./

ARG DEVELOPMENT_MODE=False
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/root/.cache/uv \
    pip install uv && \
    uv pip install --no-binary lxml --no-binary xmlsec -r requirements.txt && \
    uv pip check && \
    if [ "$DEVELOPMENT_MODE" = "True" ]; then \
        echo "Installing development dependencies..." && \
        uv pip install -r requirements-dev.txt; \
    fi && \
    apt-get purge -y --auto-remove \
        build-essential \
        pkg-config \
        libxml2-dev \
        libxmlsec1-dev \
        libpq-dev

COPY --from=build-image /usr/local/bin/ffmpeg /usr/local/bin/ffmpeg
COPY --from=build-image /usr/local/bin/ffprobe /usr/local/bin/ffprobe
COPY --from=build-image /usr/local/bin/qt-faststart /usr/local/bin/qt-faststart
COPY --from=build-image /home/mediacms.io/bento4 /home/mediacms.io/bento4
COPY deploy/docker/policy.xml /etc/ImageMagick-6/policy.xml

ENV ENABLE_UWSGI='yes' \
    ENABLE_NGINX='yes' \
    ENABLE_CELERY_BEAT='yes' \
    ENABLE_CELERY_SHORT='yes' \
    ENABLE_CELERY_LONG='yes' \
    ENABLE_MIGRATIONS='yes'

EXPOSE 9000 80

FROM runtime-deps AS base

COPY . /home/mediacms.io/mediacms
COPY --from=frontend-build /app/frontend/dist/static/ /home/mediacms.io/mediacms/static/
COPY --from=frontend-build /app/frontend/dist/static/ /home/mediacms.io/mediacms/frontend/dist/static/
RUN mkdir -p /home/mediacms.io/mediacms/static_image && \
    cp -a /home/mediacms.io/mediacms/static/. /home/mediacms.io/mediacms/static_image/
WORKDIR /home/mediacms.io/mediacms
RUN chmod +x ./deploy/docker/entrypoint.sh
ENTRYPOINT ["./deploy/docker/entrypoint.sh"]
CMD ["./deploy/docker/start.sh"]

FROM runtime-deps AS full-deps

COPY requirements-full.txt ./
RUN mkdir -p /root/.cache/ && \
    chmod go+rwx /root/ && \
    chmod go+rwx /root/.cache/
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/root/.cache/uv \
    uv pip install -r requirements-full.txt && \
    uv pip install dashscope PyMuPDF python-docx python-pptx openpyxl

FROM full-deps AS full

COPY . /home/mediacms.io/mediacms
COPY --from=frontend-build /app/frontend/dist/static/ /home/mediacms.io/mediacms/static/
COPY --from=frontend-build /app/frontend/dist/static/ /home/mediacms.io/mediacms/frontend/dist/static/
RUN mkdir -p /home/mediacms.io/mediacms/static_image && \
    cp -a /home/mediacms.io/mediacms/static/. /home/mediacms.io/mediacms/static_image/
WORKDIR /home/mediacms.io/mediacms
RUN chmod +x ./deploy/docker/entrypoint.sh
ENTRYPOINT ["./deploy/docker/entrypoint.sh"]
CMD ["./deploy/docker/start.sh"]
