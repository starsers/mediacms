import os

FRONTEND_HOST = os.getenv('FRONTEND_HOST', 'http://localhost')
PORTAL_NAME = os.getenv('PORTAL_NAME', 'MediaCMS')
REDIS_LOCATION = os.getenv('REDIS_LOCATION', 'redis://redis:6379/1')

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv('POSTGRES_NAME', 'mediacms'),
        "HOST": os.getenv('POSTGRES_HOST', 'db'),
        "PORT": os.getenv('POSTGRES_PORT', '5432'),
        "USER": os.getenv('POSTGRES_USER', 'mediacms'),
        "PASSWORD": os.getenv('POSTGRES_PASSWORD', 'mediacms'),
        "OPTIONS": {'pool': True},
    }
}

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_LOCATION,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# CELERY STUFF
BROKER_URL = REDIS_LOCATION
CELERY_RESULT_BACKEND = BROKER_URL

MP4HLS_COMMAND = "/home/mediacms.io/bento4/bin/mp4hls"

USE_VIDEOCAPTIONER_TRANSCRIBE = os.getenv('USE_VIDEOCAPTIONER_TRANSCRIBE', 'False') == 'True'
VIDEOCAPTIONER_COMMAND = os.getenv('VIDEOCAPTIONER_COMMAND', 'videocaptioner')
VIDEOCAPTIONER_ASR = os.getenv('VIDEOCAPTIONER_ASR', 'bijian')
VIDEOCAPTIONER_LANGUAGE = os.getenv('VIDEOCAPTIONER_LANGUAGE', 'auto')
VIDEOCAPTIONER_SUBTITLE_LANGUAGE_CODE = os.getenv('VIDEOCAPTIONER_SUBTITLE_LANGUAGE_CODE', 'zh-Hans')
VIDEOCAPTIONER_SUBTITLE_LANGUAGE_TITLE = os.getenv('VIDEOCAPTIONER_SUBTITLE_LANGUAGE_TITLE', '简体中文')

DEBUG = os.getenv('DEBUG', 'False') == 'True'
