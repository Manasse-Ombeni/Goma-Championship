# config/settings.py
import os
import dj_database_url
from pathlib import Path
from dotenv import load_dotenv

# Charge le fichier .env en local (ignoré sur Render)
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# --- SÉCURITÉ ---
# Sur Render on mettra une vraie clé dans les variables d'environnement
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-goma-competition-dev-key')

# True en local, False sur Render
DEBUG = os.getenv('DEBUG', 'True') == 'True'

# Autorise tout en dev, sur Render on mettra ton domaine
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')

# --- APPLICATIONS ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'competition',
]

# --- MIDDLEWARE ---
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Sert les fichiers statiques sur Render
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]

WSGI_APPLICATION = 'config.wsgi.application'

# --- BASE DE DONNÉES ---
# En local = SQLite, sur Render = PostgreSQL automatique
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600
    )
}

# --- MOTS DE PASSE ---
AUTH_PASSWORD_VALIDATORS = []

# --- LANGUE ---
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Lubumbashi'
USE_I18N = True
USE_TZ = True

# --- FICHIERS STATIQUES ---
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'  # où Render va collecter
STATICFILES_DIRS = [BASE_DIR / 'static']

# Pour WhiteNoise
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- AUTH ---
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/manager/'
LOGOUT_REDIRECT_URL = '/'