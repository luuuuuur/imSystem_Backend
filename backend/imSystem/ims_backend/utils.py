import pyotp
from secrets import choice
import string
from ims_backend.aws_package.s3 import s3_client
from botocore.exceptions import ClientError
from ims_backend.aws_package.secrets_manager import secrets_aws

def generate_password():
    alphabet = string.ascii_letters + string.digits
    return ''.join(choice(alphabet) for _ in range(16))
def generate_totp():
    key = pyotp.random_base32()
    totp = pyotp.TOTP(key)
    return key, totp

def get_s3_download_url(file_key, expiration=3600):
    try:
        response = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': secrets_aws["AWS_BUCKET_NAME"], 'Key': file_key},
            ExpiresIn=expiration
        )
    except ClientError:
        
        raise

    return response
