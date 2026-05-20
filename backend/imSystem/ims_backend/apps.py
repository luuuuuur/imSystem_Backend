from django.apps import AppConfig
from backend_config.settings import(Secrets,secrets)
from cryptography.hazmat.primitives.serialization import load_pem_private_key
class ImsBackendConfig(AppConfig):
    name = 'ims_backend'
    def ready(self):
        global GLOBAL_PRIVATE_KEY
        GLOBAL_PRIVATE_KEY = Secrets.secret_key()
        load_pem_private_key(GLOBAL_PRIVATE_KEY, password=secrets["PASSWORD_KEY"])

        