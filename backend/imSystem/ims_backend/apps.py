from django.apps import AppConfig
class ImsBackendConfig(AppConfig):
    name = 'ims_backend'
    def ready(self):
        from ims_backend.aws_package.s3 import s3_client
        from ims_backend.aws_package.secrets_manager import secrets_aws
        self.s3_client = s3_client
        self.secrets_aws = secrets_aws