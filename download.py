import os
import boto3
import argparse
from botocore.exceptions import NoCredentialsError, ClientError
import sys

def download_bucket_contents(s3_client, bucket_name, local_folder):
    try:
        os.makedirs(local_folder, exist_ok=True)
        bucket_contents = s3_client.list_objects_v2(Bucket=bucket_name)
        if 'Contents' not in bucket_contents:
            print(f"The bucket {bucket_name} is empty.")
            return
        for obj in bucket_contents['Contents']:
            s3_file_path = obj['Key']
            local_file_path = os.path.join(local_folder, s3_file_path)
            local_file_dir = os.path.dirname(local_file_path)

            # Ensure the directory exists
            os.makedirs(local_file_dir, exist_ok=True)

            try:
                print(f"Downloading {s3_file_path} to {local_file_path}")
                s3_client.download_file(bucket_name, s3_file_path, local_file_path)
            except Exception as e:
                print(f"Failed to download {s3_file_path}: {e}")
    except NoCredentialsError:
        print("Credentials not available.")
        sys.exit(1)
    except ClientError as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Download contents of an S3 bucket to a local folder.")
    parser.add_argument("local_folder", help="Local folder to download to")
    parser.add_argument("access_key", help="S3 Access Key ID")
    parser.add_argument("secret_key", help="S3 Secret Access Key")
    parser.add_argument("endpoint_url", help="S3 Endpoint URL")
    parser.add_argument("bucket_name", help="S3 Bucket Name", default="book", nargs="?")

    args = parser.parse_args()

    session = boto3.session.Session()
    s3_client = session.client(
        service_name='s3',
        aws_access_key_id=args.access_key,
        aws_secret_access_key=args.secret_key,
        endpoint_url=args.endpoint_url
    )

    # Verify bucket existence
    try:
        s3_client.head_bucket(Bucket=args.bucket_name)
        download_bucket_contents(s3_client, args.bucket_name, args.local_folder)
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            print(f"The bucket {args.bucket_name} does not exist.")
        else:
            print(f"An error occurred: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()