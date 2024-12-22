import asyncio
import websockets
import json
import time
from bot.utils import logger
import os
import base64


def generate_sec_websocket_key() -> str:
    random_bytes = os.urandom(16)
    return base64.b64encode(random_bytes).decode('utf-8')


class WebSocketHandler:
    def __init__(self, session_name: str, raw_proxy: str = None):
        self.session_name = session_name
        self.websocket = None
        self.ping_task = None
        self.receive_task = None
        self.proxy_url = raw_proxy

    async def send_ping(self):
        while True:
            try:
                ping_message = {"ping": int(time.time() * 1000)}
                if self.websocket and self.websocket.open:
                    await self.websocket.send(json.dumps(ping_message))
                await asyncio.sleep(6)
            except websockets.exceptions.ConnectionClosed:
                logger.error(
                    f"{self.session_name} | WebSocket connection closed while sending ping.")
                break
            except Exception as e:
                logger.error(f"{self.session_name} | Error in ping task: {e}")
                break

    async def receive_messages(self):
        try:
            while True:
                message = await self.websocket.recv()
        except websockets.exceptions.ConnectionClosed as e:
            pass
        except Exception as e:
            logger.error(
                f"{self.session_name} | Error while receiving messages: {e}")

    async def connect_websocket(self, ws_url: str, subscribe_message: dict, user_agent: str):
        if self.websocket is not None and self.websocket.open:
            logger.info(f"{self.session_name} | WebSocket already connected.")
            return

        try:
            key = generate_sec_websocket_key()
            headers = {
                "Host": "tg.vanilla-finance.com",
                "Connection": "Upgrade",
                "Pragma": "no-cache",
                "Cache-Control": "no-cache",
                "User-Agent": user_agent,
                "Upgrade": "websocket",
                "Origin": "https://tg.vanilla-finance.com",
                "Sec-WebSocket-Version": "13",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "en,en-US;q=0.9,bn-BD;q=0.8,bn;q=0.7",
                "Sec-WebSocket-Key": key,
                "Sec-WebSocket-Extensions": "permessage-deflate; client_max_window_bits"
            }

            connect_kwargs = {
                "extra_headers": headers,
                "open_timeout": 30,  # Connection timeout in seconds
                "ping_interval": None,  # Disable automatic ping
                "ping_timeout": None,  # Disable automatic ping timeout
                "close_timeout": 10,  # Timeout for closing the connection
            }

            if self.proxy_url:
                connect_kwargs["proxy"] = self.proxy_url

            try:
                self.websocket = await asyncio.wait_for(
                    websockets.connect(ws_url, **connect_kwargs),
                    timeout=30  # Overall connection timeout
                )
                logger.info(
                    f"{self.session_name} | <g>Connected to WebSocket server</g>")

                await self.websocket.send(json.dumps(subscribe_message))

                self.ping_task = asyncio.create_task(self.send_ping())
                self.receive_task = asyncio.create_task(
                    self.receive_messages())

            except asyncio.TimeoutError:
                logger.error(
                    f"{self.session_name} | Connection timeout while connecting to WebSocket")
                if self.websocket:
                    await self.websocket.close()
                    self.websocket = None
                raise

        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.InvalidStatusCode) as e:
            logger.error(
                f"{self.session_name} | WebSocket connection closed unexpectedly: {e}")
            if self.websocket:
                await self.websocket.close()
                self.websocket = None
            await asyncio.sleep(5)
            logger.info(f"{self.session_name} | Attempting to reconnect...")
            await self.connect_websocket(ws_url, subscribe_message, user_agent)

        except Exception as e:
            logger.error(
                f"{self.session_name} | Error connecting to WebSocket: {str(e)}")
            if self.websocket:
                await self.websocket.close()
                self.websocket = None
            await asyncio.sleep(5)
            logger.info(f"{self.session_name} | Attempting to reconnect...")
            await self.connect_websocket(ws_url, subscribe_message, user_agent)

    async def close_websocket(self):
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.error(
                    f"{self.session_name} | Error while closing WebSocket: {e}")

        if self.ping_task:
            self.ping_task.cancel()
        if self.receive_task:
            self.receive_task.cancel()

    async def connect_with_retry(self, ws_url: str, subscribe_message: dict, user_agent: str, max_retries: int = 3):
        """Connect to WebSocket with retry mechanism"""
        retries = 0
        while retries < max_retries:
            try:
                await self.connect_websocket(ws_url, subscribe_message, user_agent)
                return True
            except Exception as e:
                retries += 1
                logger.error(
                    f"{self.session_name} | Connection attempt {retries} failed: {str(e)}")
                if retries < max_retries:
                    wait_time = 5 * retries  # Incremental backoff
                    logger.info(
                        f"{self.session_name} | Waiting {wait_time} seconds before next retry...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"{self.session_name} | Max retries ({max_retries}) reached. Connection failed.")
                    return False
