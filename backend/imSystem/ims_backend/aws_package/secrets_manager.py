import boto3
import json
class Secrets:
    client = boto3.client('secretsmanager', region_name='us-east-1')
    @classmethod
    def generate_secrets(cls):
        response = cls.client.get_secret_value(SecretId='TEST_AWS_SECRETS_MANAGER')
        return json.loads(response['SecretString'])
secrets_aws = Secrets.generate_secrets()