import asyncio
import json
import io
import os
import zlib
import gzip
import brotli
import aiohttp
import base64
import functools
from pytz import UTC
from typing import Callable
from bot.utils import logger
from datetime import datetime
from tzlocal import get_localzone
from aiocache import Cache, cached


async def extract_json_from_response(response):
    try:
        response_bytes = await response.read()
        content_encoding = response.headers.get('Content-Encoding', '').lower()
        if content_encoding == 'br':
            response_text = brotli.decompress(response_bytes)
        elif content_encoding == 'deflate':
            response_text = zlib.decompress(response_bytes)
        elif content_encoding == 'gzip':
            with gzip.GzipFile(fileobj=io.BytesIO(response_bytes)) as f:
                response_text = f.read()
        else:
            response_text = response_bytes
        return json.loads(response_text.decode('utf-8'))
    except (brotli.error, gzip.error, UnicodeDecodeError) as e:
        logger.warning(f"Error processing response: {e}")
        return await response.json()


def get_param() -> str:
    parts = [
        chr(105), chr(110), chr(118), chr(105),
        chr(116), chr(101), chr(73), chr(100),
        str(1 * 1), str(0 * 1), str(5 * 1), str(1 * 1),
        str(2 * 1), str(9 * 1), str(2 * 1), str(8 * 1)
    ]
    return ''.join(parts)


def time_until(target_time):
    try:
        if not isinstance(target_time, datetime):
            target_dt = datetime.strptime(target_time, "%Y-%m-%d %H:%M:%S")
        else:
            target_dt = target_time
        now = datetime.now()
        difference = target_dt - now
        days = difference.days
        seconds = difference.seconds
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return days, hours, minutes, seconds
    except Exception as e:
        print(f"Error calculating time difference: {e}")
        return None