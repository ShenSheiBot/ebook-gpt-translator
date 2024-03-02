import os
import boto3
import argparse
from botocore.exceptions import NoCredentialsError, ClientError
import sys
import time

def upload_directory(s3_client, local_folder, bucket_name, s3_folder):
    for root, dirs, files in os.walk(local_folder):
        for filename in files:
            local_path = os.path.join(root, filename)
            relative_path = os.path.relpath(local_path, local_folder)
            s3_path = os.path.join(s3_folder, relative_path)

            try:
                print(f"Uploading {local_path} to {s3_path}")
                s3_client.upload_file(local_path, bucket_name, s3_path)
            except NoCredentialsError:
                print("Credentials not available.")
                sys.exit(1)
            except ClientError as e:
                print(f"Failed to upload {local_path} to {s3_path}: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")

def main():
    parser = argparse.ArgumentParser(description="Upload a local directory to an S3 bucket.")
    parser.add_argument("local_folder", help="Local folder to upload")
    parser.add_argument("s3_folder", help="S3 folder to upload to")
    parser.add_argument("access_key", help="S3 Access Key ID")
    parser.add_argument("secret_key", help="S3 Secret Access Key")
    parser.add_argument("endpoint_url", help="S3 Endpoint URL")
    parser.add_argument("--bucket_name", help="S3 Bucket Name", default="book")
    parser.add_argument("--final", action="store_true", help="Run upload once and then quit")

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
    except ClientError as e:
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            print(f"The bucket {args.bucket_name} does not exist.")
            sys.exit(1)
        else:
            print(f"An error occurred: {e}")
            sys.exit(1)

    if args.final:
        upload_directory(s3_client, args.local_folder, args.bucket_name, args.s3_folder)
        print("Upload complete. Exiting.")
    else:
        while True:
            upload_directory(s3_client, args.local_folder, args.bucket_name, args.s3_folder)
            print("Waiting 5 minutes before next sync...")
            time.sleep(300)  # Sleep for 5 minutes

if __name__ == "__main__":
    main()
