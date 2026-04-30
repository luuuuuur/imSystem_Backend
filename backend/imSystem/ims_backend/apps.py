from django.apps import AppConfig

class ImsBackendConfig(AppConfig):
    name = 'ims_backend'
    def ready(self):
        import load_key
        

        