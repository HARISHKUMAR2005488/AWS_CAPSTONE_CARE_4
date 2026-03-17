"""SNS integration service."""

import boto3
from botocore.exceptions import ClientError
from flask import current_app


class SnsService:
    """Publish notifications to SNS topic."""

    def __init__(self):
        self.region = current_app.config['AWS_REGION']
        self.topic_arn = current_app.config['SNS_TOPIC_ARN']
        self.client = boto3.client('sns', region_name=self.region)

    def publish(self, subject: str, message: str) -> dict:
        if not self.topic_arn:
            raise ValueError('SNS topic ARN is not configured')

        try:
            response = self.client.publish(
                TopicArn=self.topic_arn,
                Subject=subject,
                Message=message,
            )
            return {
                'message_id': response.get('MessageId', ''),
                'topic_arn': self.topic_arn,
            }
        except ClientError as exc:
            current_app.logger.error('sns_publish_failed', exc_info=exc)
            raise
