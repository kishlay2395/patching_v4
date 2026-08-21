"""
S3 operations for the patching system.

This module contains S3 log upload functionality for the patching system.
"""

import os
import boto3
from common.logger import logger


def upload_log_to_s3(log_filename, s3_bucket, s3_key_prefix):
    """Upload the specified log file to the given S3 bucket and prefix."""
    s3_client = boto3.client('s3')
    s3_key = f"{s3_key_prefix}/{os.path.basename(log_filename)}"
    
    try:
        s3_client.upload_file(log_filename, s3_bucket, s3_key)
        logger.info(f"Log file {log_filename} uploaded to s3://{s3_bucket}/{s3_key}")
        return True
    except Exception as e:
        logger.error(f"Failed to upload log file to S3: {e}")
        return False
