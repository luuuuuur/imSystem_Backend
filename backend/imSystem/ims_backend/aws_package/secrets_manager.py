import boto3
import json
class Secrets:
    _client = boto3.client('secretsmanager', region_name='us-east-1')
    _secrets = None
    @classmethod
    def generate_secrets(cls):
        if cls._secrets is None:
            response = cls._client.get_secret_value(SecretId='TEST_AWS_SECRETS_MANAGER')
            cls._secrets = json.loads(response['SecretString'])
        return cls._secrets
class Secrets_API:
    _client = boto3.client('secretsmanager', region_name='us-east-1')
    _credentials = None
    @classmethod
    def load_secrets_api(cls):
        if cls._credentials is None:
            response = cls._client.get_secret_value(SecretId='ims/firebase_service_account')
            cls._credentials = json.loads(response['SecretString'])
        return cls._credentials