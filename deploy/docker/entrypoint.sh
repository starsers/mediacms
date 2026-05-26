#!/bin/bash
set -e

# forward request and error logs to docker log collector
ln -sf /dev/stdout /var/log/nginx/access.log && ln -sf /dev/stderr /var/log/nginx/error.log && \
ln -sf /dev/stdout /var/log/nginx/mediacms.io.access.log && ln -sf /dev/stderr /var/log/nginx/mediacms.io.error.log

cp /home/mediacms.io/mediacms/deploy/docker/local_settings.py /home/mediacms.io/mediacms/cms/local_settings.py


mkdir -p /home/mediacms.io/mediacms/{logs,media_files/hls}
touch /home/mediacms.io/mediacms/logs/debug.log

mkdir -p /var/run/mediacms
chown www-data:www-data /var/run/mediacms

TARGET_GID=$(stat -c "%g" /home/mediacms.io/mediacms/)

EXISTS=$(cat /etc/group | grep $TARGET_GID | wc -l)

# Create new group using target GID and add www-data user
if [ $EXISTS == "0" ]; then
    groupadd -g $TARGET_GID tempgroup
    usermod -a -G tempgroup www-data
else
    # GID exists, find group name and add
    GROUP=$(getent group $TARGET_GID | cut -d: -f1)
    usermod -a -G $GROUP www-data
fi

CHOWN_PATHS=${CHOWN_PATHS:-"/home/mediacms.io/mediacms/logs /home/mediacms.io/mediacms/media_files /var/run/mediacms"}
if [ "${CHOWN_PROJECT_TREE:-no}" = "yes" ]; then
    find /home/mediacms.io/mediacms ! \( -path "*.git*" -o -name "package-lock.json" \) -exec chown www-data:$TARGET_GID {} + 2>/dev/null || true
else
    for path in $CHOWN_PATHS; do
        [ -e "$path" ] && chown -R www-data:$TARGET_GID "$path" 2>/dev/null || true
    done
fi

chmod +x /home/mediacms.io/mediacms/deploy/docker/start.sh /home/mediacms.io/mediacms/deploy/docker/prestart.sh

if [ "${ENABLE_REQUIREMENTS_SYNC:-no}" = "yes" ]; then
    cd /home/mediacms.io/mediacms
    REQUIREMENTS_SYNC_FILES=${REQUIREMENTS_SYNC_FILES:-"requirements.txt"}
    REQUIREMENTS_SYNC_MARKER=${REQUIREMENTS_SYNC_MARKER:-"/home/mediacms.io/.requirements-sync.sha256"}
    CURRENT_REQUIREMENTS_HASH=$(sha256sum $REQUIREMENTS_SYNC_FILES 2>/dev/null | sha256sum | awk '{print $1}')
    PREVIOUS_REQUIREMENTS_HASH=""
    [ -s "$REQUIREMENTS_SYNC_MARKER" ] && PREVIOUS_REQUIREMENTS_HASH=$(cat "$REQUIREMENTS_SYNC_MARKER")
    if [ -n "$CURRENT_REQUIREMENTS_HASH" ] && [ "$CURRENT_REQUIREMENTS_HASH" != "$PREVIOUS_REQUIREMENTS_HASH" ]; then
        echo "entrypoint.sh: syncing Python packages from $REQUIREMENTS_SYNC_FILES"
        if command -v uv >/dev/null 2>&1; then
            uv pip install --no-binary lxml --no-binary xmlsec $(for file in $REQUIREMENTS_SYNC_FILES; do printf ' -r %s' "$file"; done)
            uv pip check
        else
            python -m pip install $(for file in $REQUIREMENTS_SYNC_FILES; do printf ' -r %s' "$file"; done)
            python -m pip check
        fi
        echo "$CURRENT_REQUIREMENTS_HASH" > "$REQUIREMENTS_SYNC_MARKER"
    else
        echo "entrypoint.sh: Python packages already match $REQUIREMENTS_SYNC_FILES"
    fi
fi

# Generate or read SECRET_KEY once, shared across all containers via the
# host-mounted project volume. Atomic create-or-read so parallel container
# starts (web + celery_worker + celery_beat + migrations) can't race.
# Uses `mkdir` as the lock primitive (POSIX-atomic, no dependency on flock).
SECRET_KEY_FILE="${SECRET_KEY_FILE:-/home/mediacms.io/mediacms/.secret_key}"
SECRET_KEY_LOCK="${SECRET_KEY_FILE}.lock"

if [ -z "${SECRET_KEY:-}" ]; then
    if [ ! -s "$SECRET_KEY_FILE" ]; then
        # Spin-acquire the lock. mkdir is atomic; first caller wins, others retry.
        while ! mkdir "$SECRET_KEY_LOCK" 2>/dev/null; do
            sleep 0.2
        done
        # Re-check inside the lock: another container may have just written it.
        if [ ! -s "$SECRET_KEY_FILE" ]; then
            python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())' > "$SECRET_KEY_FILE"
            chown www-data:www-data "$SECRET_KEY_FILE"
            chmod 600 "$SECRET_KEY_FILE"
            echo "entrypoint.sh: generated new SECRET_KEY at $SECRET_KEY_FILE"
        fi
        rmdir "$SECRET_KEY_LOCK"
    fi
    export SECRET_KEY="$(cat "$SECRET_KEY_FILE")"
fi

exec "$@"
