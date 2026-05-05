"""
DynamoDB Handler — fetches audience-submitted words/phrases from AWS DynamoDB.
"""

import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class DynamoDBHandler:
    def __init__(
        self,
        region: str = "us-east-1",
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ):
        kwargs = {"region_name": region}
        if access_key and secret_key:
            kwargs["aws_access_key_id"] = access_key
            kwargs["aws_secret_access_key"] = secret_key

        try:
            self._resource = boto3.resource("dynamodb", **kwargs)
            logger.info("DynamoDB handler initialized (region: %s)", region)
        except Exception as e:
            logger.error("Failed to initialize DynamoDB: %s", e)
            self._resource = None

    def fetch_all(self, table_name: str) -> list[str]:
        """Scan the table and return all lyric/text/suggestion values."""
        if not self._resource:
            return []

        try:
            table = self._resource.Table(table_name)
            items = []
            last_key = None

            while True:
                scan_kwargs = {}
                if last_key:
                    scan_kwargs["ExclusiveStartKey"] = last_key
                response = table.scan(**scan_kwargs)
                items.extend(response.get("Items", []))
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break

            lyrics = []
            for item in items:
                for key in ("lyric", "text", "suggestion"):
                    val = item.get(key)
                    if val and isinstance(val, str) and val.strip():
                        lyrics.append(val.strip())
                        break

            logger.info("Fetched %d entries from '%s'", len(lyrics), table_name)
            return lyrics

        except ClientError as e:
            logger.error("DynamoDB fetch failed: %s", e)
            return []

    @staticmethod
    def compile_for_prompt(lyrics: list[str]) -> str:
        if not lyrics:
            return "(no audience submissions received)"
        return ", ".join(lyrics)

    def clear_table(self, table_name: str):
        """Delete all items from the table (for show reset)."""
        if not self._resource:
            return
        try:
            table = self._resource.Table(table_name)
            response = table.scan()
            key_names = [k["AttributeName"] for k in table.key_schema]
            with table.batch_writer() as batch:
                for item in response.get("Items", []):
                    key = {k: item[k] for k in key_names}
                    batch.delete_item(Key=key)
            logger.info("Cleared table '%s'", table_name)
        except Exception as e:
            logger.error("Failed to clear table '%s': %s", table_name, e)
