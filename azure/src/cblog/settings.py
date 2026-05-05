"""
Django settings for cblog project — Azure deployment version.
AWS S3 / RDS → Azure Blob Storage / Azure Database for MySQL Flexible Server
"""

from pathlib import Path
from decouple import config
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = [
    '',  # add your App Service hostname here, e.g. azure-capstone-app.azurewebsites.net
    '',  # add your custom domain here, e.g. www.yourdomain.com
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # my_apps
    'blog.apps.BlogConfig',
    'users.apps.UsersConfig',
    # third party
    'crispy_forms',
    'storages',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # serves local static during development
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'cblog.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR, "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'cblog.wsgi.application'


# Database — Azure Database for MySQL Flexible Server
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': '',        # database name in Azure MySQL is written here (e.g. database1)
        'USER': '',        # database admin username is written here (e.g. admin)
        'PASSWORD': config('PASSWORD'),  # written in src/.env — do NOT put it here
        'HOST': '',        # Azure MySQL server FQDN is written here
                           # e.g. azure-capstone-mysql.mysql.database.azure.com
        'PORT': '3306',    # MySQL port
        'OPTIONS': {
            'ssl': {'ssl-ca': '/etc/ssl/certs/DigiCertGlobalRootCA.crt.pem'},
        },
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True


CRISPY_TEMPLATE_PACK = 'bootstrap4'
LOGIN_REDIRECT_URL = "blog:list"
LOGIN_URL = "login"


# ── Azure Blob Storage — equivalent of AWS S3 + storages.py ─────────────────
# Picture and media files are kept in Azure Blob Storage.
# Write your storage account name and key below.
# storages.py class AzureMediaStorage handles the 'media' container.

AZURE_ACCOUNT_NAME = ''   # please enter your Azure Storage Account name
                          # e.g. azurecapstoneblob<yourname>

AZURE_ACCOUNT_KEY  = config('AZURE_STORAGE_KEY')  # written in src/.env — do NOT put it here

AZURE_CUSTOM_DOMAIN = f'{AZURE_ACCOUNT_NAME}.blob.core.windows.net'

AZURE_LOCATION = 'static'   # equivalent of AWS_LOCATION = 'static'

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

# Static files served from Azure Blob 'static' container
# Equivalent of: STATIC_URL = 'https://%s/%s/' % (AWS_S3_CUSTOM_DOMAIN, AWS_LOCATION)
STATIC_URL = f'https://{AZURE_CUSTOM_DOMAIN}/static/'
STATICFILES_STORAGE = 'storages.backends.azure_storage.AzureStorage'   # equivalent of S3Boto3Storage

# Media (user-upload) files served from Azure Blob 'media' container
# Equivalent of: DEFAULT_FILE_STORAGE = 'cblog.storages.MediaStore'
DEFAULT_FILE_STORAGE = 'cblog.storages.AzureMediaStorage'
MEDIA_URL = f'https://{AZURE_CUSTOM_DOMAIN}/media/'

# Azure Storage
AZURE_ACCOUNT_NAME = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
AZURE_ACCOUNT_KEY = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")

DEFAULT_FILE_STORAGE = "cblog.storages.AzureMediaStorage"

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
    }
}
