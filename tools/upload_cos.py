#!/usr/bin/env python3
"""Upload a local file to Tencent COS."""
# pyright: reportMissingImports=false

from __future__ import annotations

import argparse
import os
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload local file to Tencent COS")
    parser.add_argument("--file", required=True, help="Local file path")
    parser.add_argument("--bucket", required=True, help="COS bucket name, e.g. my-bucket-1250000000")
    parser.add_argument("--region", required=True, help="COS region, e.g. ap-shanghai")
    parser.add_argument("--secret-id", required=True, help="Tencent SecretId")
    parser.add_argument("--secret-key", required=True, help="Tencent SecretKey")
    parser.add_argument("--key", required=True, help="Object key in bucket, e.g. modsync/packages/stable.zip")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not os.path.isfile(args.file):
        print(f"[ERROR] Local file does not exist: {args.file}")
        return 1

    try:
        from qcloud_cos import CosConfig, CosS3Client
    except Exception as exc:
        print("[ERROR] qcloud_cos module not available. Please install cos-python-sdk-v5.")
        print(f"[ERROR] Import detail: {exc}")
        return 2

    object_key = args.key.replace("\\", "/")
    if object_key.startswith("/"):
        object_key = object_key[1:]

    config = CosConfig(
        Region=args.region,
        SecretId=args.secret_id,
        SecretKey=args.secret_key,
        Scheme="https",
    )
    client = CosS3Client(config)

    try:
        resp = client.upload_file(
            Bucket=args.bucket,
            LocalFilePath=args.file,
            Key=object_key,
            PartSize=10,
            MAXThread=5,
            EnableMD5=False,
        )
    except Exception as exc:
        print(f"[ERROR] COS upload failed: {exc}")
        return 1

    etag = resp.get("ETag", "") if isinstance(resp, dict) else ""
    print(f"[OK] Uploaded to cos://{args.bucket}/{object_key}")
    if etag:
        print(f"[OK] ETag: {etag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
