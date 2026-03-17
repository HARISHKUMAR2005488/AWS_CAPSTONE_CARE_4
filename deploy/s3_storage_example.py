"""S3 storage helper example for production use.

This file is intentionally standalone so you can copy required pieces
into your Flask app module or services package.
"""

import os
from datetime import datetime
from werkzeug.utils import secure_filename

try:
    import boto3
except ImportError as exc:
    raise RuntimeError("boto3 is required for S3 uploads") from exc


ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def upload_to_s3(file_obj, user_id: int) -> dict:
    if not file_obj or not file_obj.filename:
        raise ValueError("No file provided")

    original_name = secure_filename(file_obj.filename)
    if not _allowed(original_name):
        raise ValueError("Allowed formats: pdf, jpg, jpeg, png")

    region = os.getenv("AWS_REGION", "us-east-1")
    bucket = os.getenv("AWS_S3_BUCKET")
    if not bucket:
        raise ValueError("AWS_S3_BUCKET is not configured")

    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    key = f"reports/{user_id}/{user_id}_{ts}_{original_name}"

    s3 = boto3.client("s3", region_name=region)
    file_obj.stream.seek(0)
    s3.upload_fileobj(
        file_obj,
        bucket,
        key,
        ExtraArgs={"ContentType": file_obj.mimetype or "application/octet-stream"},
    )

    file_url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"
    return {
        "file_name": original_name,
        "file_path": key,
        "file_url": file_url,
    }
