from django.apps import AppConfig
class ImsBackendConfig(AppConfig):
    name = 'ims_backend'
    def ready(self):
        from ims_backend.aws_package.secrets_manager import Secrets
        self.secrets_aws = Secrets._secrets