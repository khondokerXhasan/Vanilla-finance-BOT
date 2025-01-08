import aiohttp
import asyncio
import traceback
from time import time
from better_proxy import Proxy
from urllib.parse import unquote, quote
from datetime import datetime, timedelta
from typing import Any, Callable, Optional, Union
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector as http_connector
from aiohttp_socks import ProxyConnector as socks_connector
from random import randint, choices, uniform, choices
from aiohttp import ClientSession, ClientTimeout, ClientConnectorError

from pyrogram import Client
from pyrogram.raw.functions import account
from pyrogram.raw.functions.messages import RequestAppWebView
from pyrogram.raw.types import InputBotAppShortName, InputNotifyPeer, InputPeerNotifySettings
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait, RPCError, UserAlreadyParticipant, UserNotParticipant, UserDeactivatedBan, UserRestricted, PeerIdInvalid

from bot.utils import logger
from .headers import get_headers
from bot.config import settings
from bot.utils.proxy import get_proxy
from bot.exceptions import InvalidSession
from bot.core.agents import extract_chrome_version
from bot.core.registrator import get_tg_client
from bot.utils.safe_guard import check_base_url
from bot.utils.helper import extract_json_from_response, get_param, time_until
from bot.utils.sign_generator import create_signature
from bot.utils.websocket_handler import WebSocketHandler

BASE_API = "https://tg.vanilla-finance.com"

ws_url = "wss://tg.vanilla-finance.com/dapi/ws/v1/assets"
login_api = f"{BASE_API}/bapi/v1/user/login"
level_info_api = f"{BASE_API}/bapi/v1/options/level"
user_asset_api = f"{BASE_API}/bapi/v1/user/asset"
user_info_api = f"{BASE_API}/bapi/v1/user/info"
sign_info_api = f"{BASE_API}/bapi/v1/activity/timeslot/sign-info"
sign_claim_api = f"{BASE_API}/bapi/v1/activity/timeslot/sign-claim"
task_list_api = f"{BASE_API}/bapi/v1/activity/list"
chain_sign_info_api = f"{BASE_API}/bapi/v1/activity/chain/sign-info"
daily_sign_config_api = f"{BASE_API}/bapi/v1/activity/daily-sign-config"
daily_sign_claim_api = f"{BASE_API}/bapi/v1/activity/daily-sign-claim"
place_order_api = f"{BASE_API}/bapi/v2/options/place"
activity_list_api = f"{BASE_API}/bapi/v1/activity/list"
complete_task_api = f"{BASE_API}/bapi/v1/activity/place"
expend_asset_api = f"{BASE_API}/dapi/v1/assets/expend"
remaining_charge_api = f"{BASE_API}/dapi/v1/assets/charge/remaining"
charge_asset_api = f"{BASE_API}/dapi/v1/assets/charge"
manual_upgrade_api = f"{BASE_API}/bapi/v1/user/level/manual-upgrade"
tap_level_info_api = f"{BASE_API}/bapi/v1/user/level/tap"
level_upgrade_api = f"{BASE_API}/bapi/v1/user/level-upgrade"


class Tapper:
    def __init__(
        self, tg_client: Client,
        multi_thread: bool
    ) -> None:
        self.multi_thread = multi_thread
        self.tg_client = tg_client
        self.session_name = tg_client.name
        self.bot_username = "Vanilla_Finance_Bot"
        self.short_name = "Vanillafinance"
        self.my_ref = get_param()
        self.secret_key = settings.VANILLA_SECRET_KEY
        self.app_id = app_id = settings.VANILLA_APP_ID
        self.peer = None
        self.lock = asyncio.Lock()

    async def get_tg_web_data(
        self,
        proxy: str | None
    ) -> str:
        proxy_dict = await self._parse_proxy(proxy)
        self.tg_client.proxy = proxy_dict
        try:
            async with self.tg_client:
                self.peer = await self.resolve_peer_with_retry(chat_id=self.bot_username, username=self.bot_username)
                ref_id = str(settings.REF_ID)
                refer_id = choices([ref_id, self.my_ref], weights=[70, 30], k=1)[
                    0]  # this is sensitive data don’t change it (if ydk)
                self.refer_id = refer_id.split('inviteId')[1]
                web_view = await self.tg_client.invoke(
                    RequestAppWebView(
                        peer=self.peer,
                        platform='android',
                        app=InputBotAppShortName(
                            bot_id=self.peer,
                            short_name=self.short_name
                        ),
                        write_allowed=True,
                        start_param=self.refer_id
                    )
                )
                auth_url = web_view.url
                return await self._extract_tg_web_data(auth_url)

        except InvalidSession as error:
            raise error
        except UserDeactivated:
            logger.error(
                f"<light-yellow>{self.session_name}</light-yellow> | Your Telegram account has been deactivated. You may need to reactivate it.")
            await asyncio.sleep(delay=3)
        except UserDeactivatedBan:
            logger.error(
                f"<light-yellow>{self.session_name}</light-yellow> | Your Telegram account has been banned. Contact Telegram support for assistance.")
            await asyncio.sleep(delay=3)
        except UserRestricted as e:
            logger.error(
                f"<light-yellow>{self.session_name}</light-yellow> | Your account is restricted. Details: {e}", exc_info=True)
            await asyncio.sleep(delay=3)
        except Unauthorized:
            logger.error(
                f"<light-yellow>{self.session_name}</light-yellow> | Session is Unauthorized. Check your API_ID and API_HASH")
            await asyncio.sleep(delay=3)
        except Exception as error:
            logger.error(
                f"<light-yellow>{self.session_name}</light-yellow> | Unknown error during Authorization: {error}")
            await asyncio.sleep(delay=3)

    async def _extract_tg_web_data(self, auth_url: str) -> str:
        tg_web_data = unquote(
            string=unquote(
                string=auth_url.split('tgWebAppData=')[
                    1].split('&tgWebAppVersion')[0]
            )
        )
        self.tg_account_info = await self.tg_client.get_me()
        tg_web_data_parts = tg_web_data.split('&')

        data_dict = {part.split('=')[0]: unquote(
            part.split('=')[1]) for part in tg_web_data_parts}
        return f"user={quote(data_dict['user'])}&chat_instance={data_dict['chat_instance']}&chat_type={data_dict['chat_type']}&start_param={data_dict['start_param']}&auth_date={data_dict['auth_date']}&signature={data_dict['signature']}&hash={data_dict['hash']}"

    async def check_proxy(
        self,
        http_client: CloudflareScraper,
        proxy: str
    ) -> None:
        try:
            response = await http_client.get(url='https://ipinfo.io/json', timeout=ClientTimeout(total=20), ssl=settings.ENABLE_SSL)
            response.raise_for_status()
            response_json = await extract_json_from_response(response=response)
            ip = response_json.get('ip', 'NO')
            country = response_json.get('country', 'NO')
            logger.info(
                f"{self.session_name} | Proxy IP: <g>{ip}</g> | Country : <g>{country}</g>")
        except (asyncio.TimeoutError, ClientConnectorError) as e:
            logger.error(
                f"<light-yellow>{self.session_name}</light-yellow> | Network Connection error or Proxy is not online")
        except Exception as error:
            logger.error(
                f"<light-yellow>{self.session_name}</light-yellow> | Proxy: {proxy} | Error: {error}")

    async def _parse_proxy(
        self,
        proxy: str | None
    ) -> dict | None:

        if proxy:
            parsed = Proxy.from_str(proxy)
            return {
                'scheme': parsed.protocol,
                'hostname': parsed.host,
                'port': parsed.port,
                'username': parsed.login,
                'password': parsed.password
            }
        return None

    async def resolve_peer_with_retry(
        self,
        chat_id: int | str,
        username: str,
        max_retries: int = 5
    ):
        retries = 0
        peer = None
        while retries < max_retries:
            try:
                # Try resolving the peer
                peer = await self.tg_client.resolve_peer(chat_id)
                break

            except (KeyError, ValueError, PeerIdInvalid) as e:
                # Handle invalid peer ID or other exceptions
                logger.warning(
                    f"{self.session_name} | Error resolving peer: <y>{str(e)}</y>. Retrying in <e>3</e> seconds.")
                await asyncio.sleep(3)
                retries += 1

            except FloodWait as error:
                # Handle FloodWait error
                logger.warning(
                    f"{self.session_name} | FloodWait error | Retrying in <e>{error.value + 15}</e> seconds.")
                await asyncio.sleep(error.value + 15)
                retries += 1

                peer_found = await self.get_dialog(username=username)
                if peer_found:
                    peer = await self.tg_client.resolve_peer(chat_id)
                    break
        if not peer:
            logger.error(
                f"{self.session_name} | Could not resolve peer for <y>{username}</e> after <e>{retries}</e> retries.")

        return peer

    async def get_dialog(
        self,
        username: str
    ) -> bool:
        peer_found = False
        async for dialog in self.tg_client.get_dialogs():
            if dialog.chat and dialog.chat.username == username:
                peer_found = True
                break
        return peer_found

    async def mute_and_archive_chat(
        self,
        chat,
        peer,
        username: str
    ) -> None:
        try:
            # Mute notifications
            await self.tg_client.invoke(
                account.UpdateNotifySettings(
                    peer=InputNotifyPeer(peer=peer),
                    settings=InputPeerNotifySettings(mute_until=2147483647)
                )
            )
            logger.info(
                f"{self.session_name} | Successfully muted chat <g>{chat.title}</g> for channel <y>{username}</y>")

            # Archive the chat
            await asyncio.sleep(delay=5)
            if settings.ARCHIVE_CHANNELS:
                await self.tg_client.archive_chats(chat_ids=[chat.id])
                logger.info(
                    f"{self.session_name} | Channel <g>{chat.title}</g> successfully archived for channel <y>{username}</y>")
        except RPCError as e:
            logger.error(
                f"<light-yellow>{self.session_name}</light-yellow> | Error muting or archiving chat <g>{chat.title}</g>: {e}", exc_info=True)

    async def join_tg_channel(
        self,
        link: str
    ) -> None:
        async with self.tg_client:
            try:
                parsed_link = link if 'https://t.me/+' in link else link[13:]
                username = parsed_link if "/" not in parsed_link else parsed_link.split("/")[
                    0]
                try:
                    chat = await self.tg_client.join_chat(username)
                    chat_id = chat.id
                    logger.info(
                        f"{self.session_name} | Successfully joined to <g>{chat.title}</g>")

                except UserAlreadyParticipant:
                    chat = await self.tg_client.get_chat(username)
                    chat_id = chat.id
                    logger.info(
                        f"{self.session_name} | Chat <y>{username}</y> already joined")

                except RPCError:
                    logger.info(
                        f"{self.session_name} | Channel <y>{username}</y> not found")
                    raise
                await asyncio.sleep(delay=5)

                peer = await self.resolve_peer_with_retry(chat_id, username)

                # Proceed only if peer was resolved successfully
                if peer:
                    await self.mute_and_archive_chat(chat, peer, username)

            except UserDeactivated:
                logger.error(
                    f"<light-yellow>{self.session_name}</light-yellow> | Your Telegram account has been deactivated. You may need to reactivate it.")
                await asyncio.sleep(delay=3)
            except UserDeactivatedBan:
                logger.error(
                    f"<light-yellow>{self.session_name}</light-yellow> | Your Telegram account has been banned. Contact Telegram support for assistance.")
                await asyncio.sleep(delay=3)
            except UserRestricted as e:
                logger.error(
                    f"<light-yellow>{self.session_name}</light-yellow> | Your account is restricted. Details: {e}", exc_info=True)
                await asyncio.sleep(delay=3)
            except AuthKeyUnregistered:
                logger.error(
                    f"<light-yellow>{self.session_name}</light-yellow> | Authorization key is unregistered. Please log in again.")
                await asyncio.sleep(delay=3)
            except Unauthorized:
                logger.error(
                    f"<light-yellow>{self.session_name}</light-yellow> | Session is Unauthorized. Check your API_ID and API_HASH")
                await asyncio.sleep(delay=3)
            except Exception as error:
                logger.error(
                    f"<light-yellow>{self.session_name}</light-yellow> | Error while join tg channel: {error} {link}")
                await asyncio.sleep(delay=3)

    async def change_name(
        self,
        symbol: str
    ) -> bool:
        async with self.tg_client:
            try:
                me = await self.tg_client.get_me()
                first_name = me.first_name
                last_name = me.last_name if me.last_name else ''
                tg_name = f"{me.first_name or ''} {me.last_name or ''}".strip()

                if symbol not in tg_name:
                    changed_name = f'{first_name}{symbol}'
                    await self.tg_client.update_profile(first_name=changed_name)
                    logger.info(
                        f"{self.session_name} | First name changed <g>{first_name}</g> to <g>{changed_name}</g>")
                    await asyncio.sleep(delay=randint(20, 30))
                return True
            except Exception as error:
                logger.error(
                    f"<light-yellow>{self.session_name}</light-yellow> | Error while changing tg name : {error}")
                return False

    async def create_telegram_username(
        first_name: str,
        last_name: str
    ) -> str:
        base_name = f"{first_name}{last_name}"
        # Remove non-alphanumeric characters
        base_name = re.sub(r'[^a-zA-Z0-9]', '', base_name)
        if len(base_name) < 5:
            logger.warning(
                f"{self.session_name} | Base name is too short, must be at least 5 characters long.")
            base_name = f"{base_name}{base_name}"

        while True:
            random_number = random.randint(1000, 9999)
            new_username = f"{base_name.lower()}{random_number}"

            if not (5 <= len(new_username) <= 32):  # Check length of generated username
                logger.warning(
                    f"{self.session_name} | Generated username <y>{new_username}</y> is invalid due to length.")
                continue

            try:
                await self.tg_client.set_username(new_username)
                logger.info(
                    f"{self.session_name} | Updated username: <g>{new_username}</g>")
                await asyncio.sleep(2)  # Sleep to prevent rate limit
                return new_username
            except UsernameOccupied:
                logger.info(
                    f"{self.session_name} | Username <y>{new_username}</y> is already taken. Regenerating...")
            except FloodWait as e:
                logger.warning(
                    f"{self.session_name} | Flood wait error: Wait for <e>{e.value + 20}</e> seconds.")
                # Wait for the specified duration
                await asyncio.sleep(e.value + 20)
            except Exception as e:
                logger.error(
                    f"{self.session_name} | Error while checking username: {e}")
                logger.warning(
                    f"{self.session_name} | Failed to check or update username. Please try again.")
                return f"hasan_{base_name}"

    async def make_request(
        self,
        http_client: CloudflareScraper,
        method: str,
        url: str,
        params: Optional[dict] = None,
        payload: Optional[dict] = None,
        max_retries: int = 10,
        delay: int = 10,
        timeout: int = 50,
        ssl: bool = settings.ENABLE_SSL,
        sleep: int = 1
    ) -> Optional[Union[dict | list | int | str | bool]]:
        retries = 0
        while retries < max_retries:
            try:
                async with self.lock:
                    app_sign = create_signature(
                        self.secret_key, params, payload)
                    http_client.headers['x-vanilla-appid'] = self.app_id
                    http_client.headers['x-vanilla-appsign'] = app_sign
                    await asyncio.sleep(sleep)
                    response = await http_client.request(
                        method=method.upper(),
                        url=url,
                        params=params,
                        json=payload,
                        timeout=ClientTimeout(total=timeout),
                        ssl=ssl
                    )

                    if response.status == 200:
                        return await extract_json_from_response(response=response)
                    else:
                        retries += 1
                        logger.warning(
                            f"{self.session_name} | Request to <c>{url}</c> failed: <r>{response.status}</r>, retrying... (<g>{retries}</g>/<r>{max_retries}</r>)")
                        await asyncio.sleep(delay)
                        delay *= 2
            except (asyncio.TimeoutError) as e:
                retries += 1
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
            except (ClientConnectorError) as e:
                retries += 1
                logger.warning(
                    f"{self.session_name} | Network Connection Error: {e}, retrying... (<g>{retries}</g>/<r>{max_retries}</r>)", exc_info=True)
                await asyncio.sleep(delay)
                delay *= 2
            except Exception as e:
                # traceback.print_exc()
                logger.warning(
                    f"{self.session_name} | Unknown error while making request to <y>{url}</y>: {e}", exc_info=True)
                return None
        return None

    async def login(
        self,
        http_client: CloudflareScraper,
    ) -> Optional[dict]:
        user_id = int(self.tg_account_info.id)
        first_name = self.tg_account_info.first_name or ""
        last_name = self.tg_account_info.last_name or ""
        username = self.tg_account_info.username or (await self.create_telegram_username(first_name, last_name))
        payload = {
            "clientUserId": user_id,
            "firstName": first_name,
            "lastName": last_name,
            "userName": username,
            "inviteId": str(self.refer_id)
        }
        params = {"timestamp": int(time() * 1000)}
        response = await self.make_request(http_client=http_client, method="POST", url=login_api, params=params, payload=payload)
        user_info = response.get('data', {})

        return user_info

    async def user_info(
        self,
        http_client: CloudflareScraper,
        user_id: int
    ) -> Optional[dict]:
        params = {
            "userId": user_id,
            "timestamp": int(time() * 1000)
        }
        response = await self.make_request(http_client=http_client, method="GET", url=user_info_api, params=params)
        # print(response)
        return response.get('data', {})

    async def user_asset(
        self,
        http_client: CloudflareScraper,
        user_id: int
    ) -> Optional[list]:
        params = {
            "userId": user_id,
            "timestamp": int(time() * 1000)
        }
        response = await self.make_request(http_client=http_client, method="GET", url=user_asset_api, params=params)
        return response.get('data', [])

    async def sign_info(
        self,
        http_client: CloudflareScraper,
        user_id: int
    ) -> Optional[dict]:
        params = {
            "userId": user_id,
            "timestamp": int(time() * 1000)
        }
        response = await self.make_request(http_client=http_client, method="GET", url=sign_info_api, params=params)
        return response.get('data', {})

    async def claim_signin(
        self,
        http_client: CloudflareScraper,
        user_id: int
    ) -> Optional[list]:
        params = {"timestamp": int(time() * 1000)}
        payload = {"userId": user_id}
        response = await self.make_request(http_client=http_client, method="POST", url=sign_claim_api, params=params, payload=payload, sleep=5)
        if response.get('code', 0) == 0:
            return True
        return False

    async def chain_sign_info(
        self,
        http_client: CloudflareScraper,
        user_id: int
    ) -> Optional[list]:
        params = {
            "userId": user_id,
            "timestamp": int(time() * 1000)
        }
        response = await self.make_request(http_client=http_client, method="GET", url=chain_sign_info_api, params=params)
        return response.get('data', {})

    async def daily_sign_config(
        self,
        http_client: CloudflareScraper
    ) -> Optional[list]:
        params = {"timestamp": int(time() * 1000)}
        response = await self.make_request(http_client=http_client, method="GET", url=daily_sign_config_api, params=params)
        return response.get('data', [])

    async def claim_daily_signin(
        self,
        http_client: CloudflareScraper,
        user_id: int
    ) -> Optional[dict]:
        params = {"timestamp": int(time() * 1000)}
        payload = {"userId": user_id}
        response = await self.make_request(http_client=http_client, method="POST", url=daily_sign_claim_api, params=params, payload=payload, sleep=5)
        return response.get('data', {})

    async def activity_list(
        self,
        http_client: CloudflareScraper,
        user_id: int
    ) -> Optional[list]:
        params = {
            "userId": user_id,
            "type": "MISSING",
            "timestamp": int(time() * 1000)
        }
        response = await self.make_request(http_client=http_client, method="GET", url=activity_list_api, params=params)
        return response.get('data', [])

    async def complete_task(
        self,
        http_client: CloudflareScraper,
        user_id: int,
        task_id: int
    ) -> Optional[bool]:
        params = {"timestamp": int(time() * 1000)}
        payload = {
            "userId": user_id,
            "taskId": task_id
        }
        response = await self.make_request(http_client=http_client, method="POST", url=complete_task_api, params=params, payload=payload)
        if response.get('code', 0) == 0:
            return True
        return False

    async def expend_asset(
        self,
        http_client: CloudflareScraper,
        user_id: int,
        tap: int,
        sleep: int = 2,
    ) -> Optional[dict]:
        params = {"timestamp": int(time() * 1000)}
        payload = {
            "userId": str(user_id),
            "quantity": str(tap)
        }
        response = await self.make_request(http_client=http_client, method="POST", url=expend_asset_api, params=params, payload=payload, sleep=sleep)
        return response

    async def charge_asset(
        self,
        http_client: CloudflareScraper,
        user_id: int
    ) -> Optional[dict]:
        params = {
            "userId": user_id,
            "timestamp": int(time() * 1000)
        }
        response = await self.make_request(http_client=http_client, method="GET", url=charge_asset_api, params=params)
        return response

    async def charge_remaining(
        self,
        http_client: CloudflareScraper,
        user_id: int
    ) -> Optional[dict]:
        params = {
            "userId": user_id,
            "timestamp": int(time() * 1000)
        }
        response = await self.make_request(http_client=http_client, method="GET", url=remaining_charge_api, params=params)
        return response.get('data', {})

    async def level_data(
        self,
        http_client: CloudflareScraper
    ) -> Optional[list]:
        params = {"timestamp": int(time() * 1000)}
        response = await self.make_request(http_client=http_client, method="GET", url=level_info_api, params=params)
        return response.get('data', [])

    async def upgrade_manual(
        self,
        http_client: CloudflareScraper,
        user_id: int
    ) -> Optional[list]:
        params = {"timestamp": int(time() * 1000)}
        payload = {"userId": str(user_id)}
        response = await self.make_request(http_client=http_client, method="POST", url=manual_upgrade_api, params=params, payload=payload)
        # print(response)
        return response

    async def upgrade_level(
        self,
        http_client: CloudflareScraper,
        user_id: int
    ) -> Optional[list]:
        params = {"timestamp": int(time() * 1000)}
        payload = {"userId": str(user_id)}
        response = await self.make_request(http_client=http_client, method="POST", url=level_upgrade_api, params=params, payload=payload, sleep=6)
        # print(response)
        return response

    async def run(
        self,
        user_agent: str,
        proxy: str | None
    ) -> None:
        if settings.USE_RANDOM_DELAY_IN_RUN:
            random_delay = randint(
                settings.START_DELAY[0], settings.START_DELAY[1])
            logger.info(
                f"{self.session_name} | 🕚 wait <c>{random_delay}</c> second before starting...")
            await asyncio.sleep(random_delay)

        proxy_conn = (
            socks_connector.from_url(proxy) if proxy and 'socks' in proxy else
            http_connector.from_url(proxy) if proxy and 'http' in proxy else
            (logger.warning(f"{self.session_name} | Proxy protocol not recognized. Proceeding without proxy.") or None) if proxy else
            None
        )
        headers = get_headers()
        headers["User-Agent"] = user_agent
        chrome_ver = extract_chrome_version(
            user_agent=headers['User-Agent']).split('.')[0]
        headers['Sec-Ch-Ua'] = f'"Chromium";v="{chrome_ver}", "Android WebView";v="{chrome_ver}", "Not?A_Brand";v="24"'

        timeout = ClientTimeout(total=60)
        async with CloudflareScraper(headers=headers, connector=proxy_conn, trust_env=True, auto_decompress=False, timeout=timeout) as http_client:

            if proxy:
                await self.check_proxy(http_client=http_client, proxy=proxy)

            while True:
                can_run = True
                try:
                    sleep_time = 360
                    if await check_base_url(self.session_name) is False:
                        can_run = False
                        if settings.ADVANCED_ANTI_DETECTION:
                            logger.warning(
                                "<y>Detected index js file change. Contact me to check if it's safe to continue</y>: <g>https://t.me/scripts_hub</g>")
                            return sleep_time

                        else:
                            logger.warning(
                                "<y>Detected api change! Stopped the bot for safety. Contact me here to update the bot</y>: <g>https://t.me/scripts_hub</g>")
                            return sleep_time

                    end_at = 3600*3
                    if can_run:
                        tg_web_data = await self.get_tg_web_data(proxy=proxy)
                        if tg_web_data is None:
                            logger.warning(
                                f"{self.session_name} | retrieving telegram web data failed")
                            return
                        http_client.headers['authorization'] = f"tma {tg_web_data}"

                        ### Login ###
                        login = await self.login(http_client=http_client)
                        user_id = login.get('userId', None)
                        if login.get('isNewUser', False):
                            logger.success(
                                f"{self.session_name} | 🥳 <g>Account created successfully!</g> - ID: <e>{user_id}</e>")
                        else:
                            logger.info(
                                f"{self.session_name} | 🔐 <green>Account login Successfully</green>")

                        ### Keeping alive using websocket ###
                        websocket_handler = WebSocketHandler(
                            session_name=self.session_name, raw_proxy=proxy)
                        subscribe_message = {
                            "id": "AssetsTopic",
                            "event": "sub",
                            "topic": "AssetsTopic",
                            "params": {"binary": True, "userId": str(user_id)}
                        }
                        await websocket_handler.connect_websocket(ws_url, subscribe_message, user_agent)

                        ### user info ###
                        user_info = await self.user_info(http_client=http_client, user_id=user_id)
                        user_level = int(user_info.get('level'))
                        treading_status = user_info.get('claimStatus', None)
                        duration_days = user_info.get('durationDays', 0)
                        logger.info(f"{self.session_name} | Level: <g>{user_info.get('level', None)}</g> - TapLevel: <g>{user_info.get('tapLevel', None)}</g> - Account type : <g>{login.get('type', None)}</g> - Streak: <g>{user_info.get('durationDays', None)}</g>")

                        ### User all assets ###
                        user_asset = await self.user_asset(http_client=http_client, user_id=user_id)
                        message = "All Balance:"
                        for asset in user_asset:
                            amount = float(asset.get('amount', 0.00))
                            currency = asset.get('currency', 'Not Found')
                            message += f" - <g>{amount}</g> {currency}" if int(
                                amount) != 0 else ""
                        logger.info(f"{self.session_name} | {message}")

                        ### Daily Login Bonuse ###
                        sign_info = await self.sign_info(http_client=http_client, user_id=user_id)
                        if sign_info:
                            next_reward = sign_info.get(
                                'nextRewardTimestamp', 0)
                            isAvailable = sign_info.get('available', False)
                            amount = int(sign_info.get('amount', 0))
                            if isAvailable:
                                claim_data = await self.claim_signin(http_client=http_client, user_id=user_id)
                                if claim_data:
                                    logger.info(
                                        f"{self.session_name} | 🎊 <g>Successfully claimed signIn reward</g> | rewarded: <g>+{amount} Suger</g>")
                                else:
                                    logger.info(
                                        f"{self.session_name} | <y>Claiming signIn reward failed</y>")
                            else:
                                target_time = datetime.fromtimestamp(
                                    next_reward / 1000)
                                days, hours, minutes, seconds = time_until(
                                    target_time)

                                logger.info(
                                    f"{self.session_name} | Sign-In Reward already claimed, next claim at: <g>{days}</g> days, <g>{hours}</g> hours, <g>{minutes}</g> minutes, <g>{seconds}</g> seconds")

                        ### Daily login 14 days loop task ###
                        daily_sign_info = await self.chain_sign_info(http_client=http_client, user_id=user_id)
                        daily_sign_config = await self.daily_sign_config(http_client=http_client)
                        isComplete = daily_sign_info.get('isComplete', True)

                        if not isComplete and treading_status in ["WAIT_CLAIM", "NOT_TRADE"]:
                            reward = float(next((_['reward'] for _ in daily_sign_config if int(
                                _['day']) == duration_days+1), 0))
                            if treading_status == "NOT_TRADE":
                                await self.expend_asset(http_client=http_client, user_id=user_id, tap=1)
                            claim_daily = await self.claim_daily_signin(http_client=http_client, user_id=user_id)
                            if claim_daily:
                                status = claim_daily.get('claimStatus', None)
                                # print(claim_daily)
                                if status == "CLAIMED":
                                    logger.info(
                                        f"{self.session_name} | 🎉<g>Successfully claimed daily reward</g> | rewarded: <g>+{reward} SUGAR</g>")
                                elif status == "claim-not-satisfy":
                                    logger.info(
                                        f"{self.session_name} | Daily reward not claimed, first you have to trade something</y>")
                                else:
                                    logger.info(
                                        f"{self.session_name} | <y>Daily reward failed</g>")

                        ########## Process Task ###########
                        task_list = await self.activity_list(http_client=http_client, user_id=user_id)
                        for task in task_list:
                            if not task.get('isComplete'):
                                task_id = task.get('taskId')
                                title = task.get('title', None)
                                reward = task.get('reward', 0)
                                currency = task.get('rewardCcy', None)
                                logger.info(
                                    f"{self.session_name} | 🕦 Wait <e>30</e> seconds before starting <g>{title}</g>")
                                await asyncio.sleep(30)
                                complete_task = await self.complete_task(http_client=http_client, user_id=user_id, task_id=task_id)
                                if complete_task:
                                    logger.info(
                                        f"{self.session_name} | 🎉 Successfully task <g>{title}</g> Completed | rewarded: <g>{reward} {currency}</g>")
                                else:
                                    logger.info(
                                        f"{self.session_name} | <y>Task {title} not completed</y>")

                        #### Upgrade level with cost of SUGER ####
                        if settings.UPGRADE_LEVEL_WITH_SUGER:
                            upgrade = await self.upgrade_level(http_client=http_client, user_id=user_id)
                            if upgrade and upgrade.get('code') == 0:
                                logger.info(
                                    f"{self.session_name} | Successfully upgraded level from <g>LV-{user_level}</g> to <g>LV-{user_level+1}</g>")

                        ##### Tap Tap #####
                        if settings.AUTO_TAP:
                            while True:
                                user_info = await self.user_info(http_client=http_client, user_id=user_id)
                                user_level = int(user_info.get('level'))
                                tap_level = int(user_info.get('tapLevel'))
                                total_tapped = int(user_info.get('volume'))
                                level_data = await self.level_data(http_client=http_client)
                                level_cfg = next(_ for _ in level_data if int(
                                    _['level']) == user_level)
                                cost_up = int(level_cfg["costUp"])
                                cost_down = int(level_cfg["costDown"])
                                refill_speed = int(level_cfg["speedPerHour"])
                                required_tap = cost_up - cost_down
                                till_tapped = total_tapped - cost_down
                                ano = required_tap - till_tapped

                                user_asset = await self.user_asset(http_client=http_client, user_id=user_id)
                                available_tap = int(
                                    float(next((_['amount'] for _ in user_asset if _['currency'] == 'CONE'), 0)))
                                clt_tap = randint(
                                    settings.TAP_COUNT[0], settings.TAP_COUNT[1])

                                tap_amount_ = clt_tap if ano > clt_tap else ano
                                tap_amount = tap_amount_ if available_tap > tap_amount_ else available_tap

                                charge_remaining = await self.charge_remaining(http_client=http_client, user_id=user_id)
                                available_charge = charge_remaining.get(
                                    "remaining")

                                if available_tap > 3 * user_level and till_tapped != required_tap:
                                    
                                    tap_min, tap_max = settings.TAP_COUNT
                                    range_factor = (tap_max - tap_min) / 100
                                    sleep_ = uniform(2 * range_factor, 6 * range_factor)
                                    tap_tap = await self.expend_asset(http_client=http_client, user_id=user_id, tap=tap_amount, sleep=round(sleep_, 2))
                                    user_info = await self.user_info(http_client=http_client, user_id=user_id)

                                    level_data = await self.level_data(http_client=http_client)

                                    user_level = int(user_info.get('level'))
                                    tap_level = int(user_info.get('tapLevel'))
                                    total_tapped = int(user_info.get('volume'))
                                    level_cfg = next(_ for _ in level_data if int(
                                        _['level']) == user_level)
                                    cost_up = int(level_cfg["costUp"])
                                    cost_down = int(level_cfg["costDown"])
                                    refill_speed = int(
                                        level_cfg["speedPerHour"])
                                    required_tap = cost_up - cost_down

                                    till_tapped = total_tapped - cost_down

                                    user_asset = await self.user_asset(http_client=http_client, user_id=user_id)
                                    available_tap = int(
                                        float(next((_['amount'] for _ in user_asset if _['currency'] == 'CONE'), 0)))

                                    if tap_tap.get('message') == "":
                                        logger.info(
                                            f"{self.session_name} | Successfully tapped <g>{tap_amount}</g> - progress: <g>{till_tapped}</g>/<r>{required_tap}</r> - available tap: <g>{available_tap}</g>")

                                elif till_tapped == required_tap:
                                    upgrade_level = await self.upgrade_manual(http_client=http_client, user_id=user_id)
                                    if upgrade_level and upgrade_level.get('code') == 0:
                                        logger.info(
                                            f"{self.session_name} | Successfully upgraded level from <g>LV-{user_level}</g> to <g>LV-{user_level+1}</g>")
                                    else:
                                        logger.warning(
                                            f"{self.session_name} | upgrading level failed. response: {upgrade_level}")
                                elif available_tap < 20 and available_charge != 0:
                                    user_charge = await self.charge_asset(http_client=http_client, user_id=user_id)
                                    if user_charge.get('code') == 200:
                                        logger.info(
                                            f"{self.session_name} | Successfully used charge booster | available charge : <g>{user_charge['data'].get('remaining')}</g>")
                                else:
                                    break
                        ### Disconnect websocket connection ###
                        await websocket_handler.close_websocket()

                    if self.multi_thread is True:
                        sleep = round(end_at / 60) + randint(5, 9)
                        logger.info(
                            f"{self.session_name} | 🕦 Sleep <y>{sleep}</y> min")
                        await asyncio.sleep(sleep * 60)
                    else:
                        logger.info(
                            f"{self.session_name} | <m>==== Completed ====</m>")
                        await asyncio.sleep(3)
                        return round(end_at / 60)
                except InvalidSession as error:
                    raise error
                except (KeyboardInterrupt, RuntimeError):
                    pass
                except Exception as error:
                    traceback.print_exc()
                    logger.error(
                        f"<light-yellow>{self.session_name}</light-yellow> | Unknown error: {error}")
                    await asyncio.sleep(delay=randint(60, 120))


async def run_tapper(tg_client: Client, user_agent: str, proxy: str | None):
    try:
        await Tapper(
            tg_client=tg_client,
            multi_thread=True
        ).run(
            user_agent=user_agent,
            proxy=proxy,
        )
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")


async def run_tapper_synchronous(accounts: list[dict]):
    while True:
        for account in accounts:
            try:
                session_name, user_agent, raw_proxy = account.values()
                tg_client = await get_tg_client(session_name=session_name, proxy=raw_proxy)
                proxy = get_proxy(raw_proxy=raw_proxy)

                _ = await Tapper(
                    tg_client=tg_client,
                    multi_thread=False
                ).run(
                    proxy=proxy,
                    user_agent=user_agent,
                )

                sleep = min(_ or 0, (_ or 0) + randint(5, 9))

            except InvalidSession:
                logger.error(f"{tg_client.name} | Invalid Session")

        logger.info(f"Sleep <red>{round(sleep, 1)}</red> minutes")
        await asyncio.sleep(sleep * 60)
