# syntax=docker/dockerfile:1.7
ARG APT_DEBIAN_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian
ARG APT_SECURITY_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian-security

FROM python:3.13-slim-bookworm AS build-image

ARG APT_DEBIAN_MIRROR
ARG APT_SECURITY_MIRROR

RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i "s|http://deb.debian.org/debian|$APT_DEBIAN_MIRROR|g; s|http://deb.debian.org/debian-security|$APT_SECURITY_MIRROR|g; s|http://security.debian.org/debian-security|$APT_SECURITY_MIRROR|g" /etc/apt/sources.list.d/debian.sources; \
    fi && \
    if [ -f /etc/apt/sources.list ]; then \
        sed -i "s|http://deb.debian.org/debian|$APT_DEBIAN_MIRROR|g; s|http://deb.debian.org/debian-security|$APT_SECURITY_MIRROR|g; s|http://security.debian.org/debian-security|$APT_SECURITY_MIRROR|g" /etc/apt/sources.list; \
    fi && \
    apt-get update -y && \
    apt-get install -y --no-install-recommends wget xz-utils unzip

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

ARG NPM_REGISTRY=https://registry.npmmirror.com

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json frontend/yarn.lock ./
COPY frontend/packages/scripts/ ./packages/scripts/
RUN --mount=type=cache,target=/root/.npm \
    npm config set registry "$NPM_REGISTRY" && \
    npm ci --legacy-peer-deps --cache /root/.npm && \
    cd packages/scripts && \
    npm ci --legacy-peer-deps --cache /root/.npm && \
    npm run build
COPY frontend/ ./
RUN npm run dist

FROM python:3.13-slim-bookworm AS runtime-deps

SHELL ["/bin/bash", "-c"]

ARG APT_DEBIAN_MIRROR
ARG APT_SECURITY_MIRROR
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV CELERY_APP='cms'
ENV VIRTUAL_ENV=/home/mediacms.io
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PIP_INDEX_URL=$PIP_INDEX_URL
ENV UV_INDEX_URL=$UV_INDEX_URL

RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i "s|http://deb.debian.org/debian|$APT_DEBIAN_MIRROR|g; s|http://deb.debian.org/debian-security|$APT_SECURITY_MIRROR|g; s|http://security.debian.org/debian-security|$APT_SECURITY_MIRROR|g" /etc/apt/sources.list.d/debian.sources; \
    fi && \
    if [ -f /etc/apt/sources.list ]; then \
        sed -i "s|http://deb.debian.org/debian|$APT_DEBIAN_MIRROR|g; s|http://deb.debian.org/debian-security|$APT_SECURITY_MIRROR|g; s|http://security.debian.org/debian-security|$APT_SECURITY_MIRROR|g" /etc/apt/sources.list; \
    fi && \
    apt-get update -y && \
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
        libpq-dev

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
    uv pip install --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.tuna.tsinghua.edu.cn/simple torch && \
    uv pip install -r requirements-full.txt && \
    uv pip check

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
