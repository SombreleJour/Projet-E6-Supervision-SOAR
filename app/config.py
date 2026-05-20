import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://supervision_user:password@localhost:5432/supervision_db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    FLASK_ENV = os.getenv('FLASK_ENV', 'production')

    PRTG_BASE_URL = os.getenv('PRTG_BASE_URL', 'http://172.16.1.5:443')
    PRTG_USERNAME = os.getenv('PRTG_USERNAME', 'prtgadmin')
    PRTG_PASSWORD = os.getenv('PRTG_PASSWORD', '')
    PRTG_PASSHASH = os.getenv('PRTG_PASSHASH', '')

    WAZUH_API_URL = os.getenv('WAZUH_API_URL', 'https://172.16.1.10:55000')
    WAZUH_USER = os.getenv('WAZUH_USER', 'wazuh-wui')
    WAZUH_PASSWORD = os.getenv('WAZUH_PASSWORD', '')

    IOT_API_TOKEN = os.getenv('IOT_API_TOKEN', '')

    TEMP_MAX = float(os.getenv('TEMP_MAX', '35.0'))
    TEMP_MIN = float(os.getenv('TEMP_MIN', '10.0'))
    HUM_MAX = float(os.getenv('HUM_MAX', '80.0'))
    HUM_MIN = float(os.getenv('HUM_MIN', '20.0'))

    SOAR_THRESHOLD = os.getenv('SOAR_THRESHOLD', 'high')
    PFSENSE_URL = os.getenv('PFSENSE_URL', 'https://172.16.1.1')
    PFSENSE_USER = os.getenv('PFSENSE_USER', 'admin')
    PFSENSE_PASSWORD = os.getenv('PFSENSE_PASSWORD', '')
