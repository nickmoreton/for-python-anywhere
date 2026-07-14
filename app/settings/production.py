from .base import *

DEBUG = False

STORAGES["staticfiles"]["BACKEND"] = (
    "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
)

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
