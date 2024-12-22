import os
import re
import json
import jsbeautifier
import subprocess
import cloudscraper
from datetime import datetime
from requests.exceptions import Timeout, ConnectionError, SSLError, HTTPError, RequestException
from aiocache import Cache, cached
from bot.utils import logger
from bot.config import settings

session = cloudscraper.create_scraper()
session.headers.update({
    'User-Agent': "Mozilla/5.0 (Linux; Android 9; Samsung SM-G892A) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.5993.156 Mobile Safari/537.36 Telegram-Android/11.3.4 (Samsung SM-G892A; Android 9; SDK 28; AVERAGE)",
    'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    'Accept-Encoding': "utf-8",
    'sec-ch-ua': "\"Android WebView\";v=\"131\", \"Chromium\";v=\"131\", \"Not_A Brand\";v=\"24\"",
    'sec-ch-ua-mobile': "?1",
    'sec-ch-ua-platform': "\"Android\"",
    'upgrade-insecure-requests': "1",
    'x-requested-with': "org.telegram.messenger",
    'sec-fetch-site': "none",
    'sec-fetch-mode': "navigate",
    'sec-fetch-user': "?1",
    'sec-fetch-dest': "document",
    'accept-language': "en,en-US;q=0.9,bn-BD;q=0.8,bn;q=0.7",
    'priority': "u=0, i",
})
# URL's
BASE_PAGE_URL = "https://tg.vanilla-finance.com"
DETECTION_CONFIG_URL = "https://raw.githubusercontent.com/khondokerXhasan/bin/refs/heads/main/detect.json"

API_ENDPOINTS = [
    r"/dapi/v1/genesis/upload",
    r"/dapi/v1/genesis/sub/tw",
    r"/dapi/v1/genesis/create",
    r"/dapi/v1/genesis/find",
    r"/dapi/v1/rank/country",
    r"/dapi/v1/rank/bestCountry",
    r"/dapi/v1/rank/global",
    r"/dapi/v1/invite/partners",
    r"/dapi/v1/useraward",
    r"/dapi/v1/invitelist",
    r"/bapi/v1/user/level/tap-upgrade",
    r"/bapi/v1/user/level/tap",
    r"/bapi/v1/user/level/leaderboard-all",
    r"/bapi/v1/user/level-upgrade-broadcast",
    r"/bapi/v1/user/level-upgrade-list",
    r"/bapi/v1/user/level-upgrade",
    r"/bapi/v1/user/asset",
    r"/bapi/v1/user/info",
    r"/bapi/v1/user/login",
    r"/bapi/v1/options/level",
    r"/bapi/v1/options/currency",
    r"/bapi/v1/options/history/list",
    r"/bapi/v1/options/position",
    r"/bapi/v1/options/settlement",
    r"/bapi/v1/options/place",
    r"/dapi/v1/spot/currencyInfo",
    r"/bapi/v2/options/position",
    r"/bapi/v2/options/settlement",
    r"/bapi/v2/options/place",
    r"/bapi/v1/user/log",
    r"/dapi/v1/activity/banner",
    r"/bapi/v1/public/server-upgrade",
    r"/bapi/v1/user/level/manual-upgrade",
    r"/bapi/v1/user/level/leaderboard-current",
    r"/dapi/v1/deposit/acquire/trade",
    r"/dapi/v1/deposit/submit/hash",
    r"/dapi/v1/assets/deposit/detail",
    r"/dapi/v1/assets/withdrawal/detail",
    r"/bapi/v1/asset/swap/list",
    r"/bapi/v1/asset/swap/place",
    r"/dapi/v1/assets/charge",
    r"/dapi/v1/assets/charge/remaining",
    r"/dapi/v1/withdrawal/apply",
    r"/dapi/v1/assets/expend",
    r"/dapi/v1/assets/record",
    r"/dapi/v1/withdrawal/quota",
    r"/dapi/v1/deposit/address",
    r"/bapi/v1/asset/balance/history",
    r"/dapi/v1/deposit/chaintoken",
    r"/dapi/v1/assets/available",
    r"/bapi/v1/activity/timeslot/sign-info",
    r"/bapi/v1/activity/timeslot/sign-claim",
    r"/dapi/v1/activity/info",
    r"/dapi/v1/activity/report",
    r"/bapi/v1/activity/stake/detail",
    r"/bapi/v1/activity/daily-sign-claim",
    r"/bapi/v1/activity/daily-sign-config",
    r"/bapi/v1/activity/stake",
    r"/bapi/v1/activity/finish",
    r"/bapi/v1/activity/place",
    r"/bapi/v1/activity/list",
    r'apiHost:\s*["\']https://indser.vanilla-finance.com"',
    r'INVITE_LINK\s*=\s*["\']https://t.me/Vanilla_Finance_Bot/Vanillafinance["\']',
    r'WS_HOST\s*=\s*["\']wss://tg.vanilla-finance.com["\']',
    r'HOST\s*=\s*["\']https://tg.vanilla-finance.com["\']',
    r'APPID\s*=\s*["\']237a903dd511477ea4d2a2019ca7c03e["\']',
    r'SECRET_KEY\s*=\s*["\']550e23371cdb4012898efed9295bb9bc9139b19e-d9e648c18074fc2d83d540e1["\']'
]


async def fetch_js_paths(base_url):
    try:
        response = session.get(base_url)
        response.raise_for_status()
        pattern = r'src="(/.*?/index.*?\.js)"'
        matches = re.findall(pattern, response.text)
        return matches
    except Exception as e:
        logger.error(f"Error fetching JavaScript paths: {e}")
        return


async def get_base_api(url):
    try:
        logger.info("Checking for changes in api...")
        response = session.get(url)
        response.raise_for_status()
        content = response.text
        missing_endpoints = [
            pattern for pattern in API_ENDPOINTS if not re.search(pattern, content)]

        if not missing_endpoints:
            return True
        else:
            logger.error(
                f"<y>API and Endpoints Changed:</y> <c>{'<r>,</r> '.join(missing_endpoints)}</c>")
            return False

    except Exception as e:
        logger.error(f"Error fetching the JS file: {e}")
        return None


async def check_base_url(session_name):

    if settings.ADVANCED_ANTI_DETECTION:
        logger.info(f"{session_name} | 🔎 Processing advance detection...")
        return await advance_detection(BASE_PAGE_URL, DETECTION_CONFIG_URL)
    else:
        main_js_formats = await fetch_js_paths(BASE_PAGE_URL)
        if main_js_formats:
            for format_ in main_js_formats:
                logger.info(
                    f"{session_name} | Trying format: <g>{format_}</g>")
                full_url = f"{BASE_PAGE_URL.rstrip('/')}{format_}"
                result = await get_base_api(full_url)
                if result:
                    logger.info(f"{session_name} | No change in api!")
                    return True
            return False

        else:
            logger.warning(
                "Could not find any main.js format. Dumping page content for inspection:")
            try:
                response = session.get(base_url)
                print(response.text[:1000])
                return False
            except Exception as e:
                logger.error(
                    f"Error fetching the base URL for content dump: {e}")
                return False


@cached(ttl=1800, cache=Cache.MEMORY)  # Cache detect.json file for 30 minutes
async def load_detection_data(
    config_url: str,
    max_retries: int = 5,
    delay: int = 3
) -> list:
    retries = 0
    while retries < max_retries:
        try:
            response = session.get(config_url, headers={
                'User-Agent': "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36",
                'Accept': "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            })
            response.raise_for_status()
            detection_data = response.json()["vanilla-finance"]["index"]
            return [(item.split("|")[0], datetime.strptime(item.split("|")[1], '%Y-%m-%d %H:%M:%S')) for item in detection_data]
        except (Timeout, ConnectionError, SSLError, HTTPError, RequestException) as e:
            retries += 1
            logger.warning(
                f"Server error for {config_url}: {e}. Retrying ({retries}/{max_retries})")
            if retries < max_retries:
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                logger.error(
                    f"{self.session_name} | Max retries reached. DNS resolution error: {e}")
                raise  # Raise after max retries
        except Exception as e:
            logger.error(f"Error loading detection data: {e}")
            return []


async def get_js_file_last_modified(url):
    try:
        response = session.head(url)
        response.raise_for_status()
        last_modified = response.headers.get('Last-Modified')
        return datetime.strptime(last_modified, '%a, %d %b %Y %H:%M:%S %Z') if last_modified else None
    except Exception as e:
        logger.error(f"Error fetching Last-Modified header for {url}: {e}")
        return None


async def advance_detection(base_url, config_url):
    js_paths = await fetch_js_paths(base_url)
    if not js_paths:
        logger.warning("No JavaScript files found.")
        return False

    if settings.SAVE_JS_FILES:
        await save_js_files(js_paths)

    expected_files = await load_detection_data(config_url)
    if not expected_files:
        logger.warning("No expected JavaScript file data available.")
        return False

    for file_name, expected_time in expected_files:
        matching_path = next(
            (path for path in js_paths if file_name in path), None)
        if not matching_path:
            logger.warning(
                f"Expected file <y>{file_name}</y> not found in JavaScript paths.")
            filenames = [os.path.basename(path) for path in js_paths]
            logger.info(f"New files: <e>{'<r>,</r> '.join(filenames)}</e>")
            return False

        full_url = f"{base_url.rstrip('/')}{matching_path}"
        actual_time = await get_js_file_last_modified(full_url)

        if actual_time != expected_time:
            logger.warning(
                f"Mismatch for file <y>{file_name}</y>: expected <e>{expected_time}</e>, got <e>{actual_time}</e>")
            return False

    logger.info("<g>Bot is safe to run</g> ✅")
    return True


async def format_last_modified_date(last_modified_header):
    if last_modified_header:
        try:
            last_modified_date = datetime.strptime(
                last_modified_header, '%a, %d %b %Y %H:%M:%S %Z')
            return last_modified_date.strftime('%Y-%m-%d_%H-%M-%S')
        except ValueError:
            logger.warning("Could not parse Last-Modified header")
    return None


async def beautify_js(content):
    opts = jsbeautifier.default_options()
    opts.indent_size = 2
    return jsbeautifier.beautify(content, opts)


async def download_file(url, save_dir):
    filename = url.split("/")[-1]
    base_filename, extension = os.path.splitext(filename)

    response = session.get(url)
    if response.status_code != 200:
        logger.warning(
            f"Failed to download {url}, status code: {response.status_code}")
        return

    last_modified_header = response.headers.get('Last-Modified')
    last_modified_date = await format_last_modified_date(last_modified_header)

    if last_modified_date:
        filename = f"{base_filename}_{last_modified_date}{extension}"

    save_path = os.path.join(save_dir, filename)

    if os.path.exists(save_path):
        pass
    else:
        beautified_content = await beautify_js(response.text)
        with open(save_path, "w") as f:
            f.write(beautified_content)
        logger.info(f"📦 Saved <g>{url}</g> as <e>{save_path}</e>")


async def clean_up_old_files(directory, max_files=20):
    js_files = [os.path.join(directory, f)
                for f in os.listdir(directory) if f.endswith(".js")]

    if len(js_files) > max_files:
        js_files.sort(key=os.path.getmtime)

        files_to_delete = js_files[:-max_files]
        for file_path in files_to_delete:
            os.remove(file_path)
            logger.info(f"<m>Deleted old file: </m><y>{file_path}</y>")


async def save_js_files(js_paths):
    save_directory = "downloaded_js_files"

    os.makedirs(save_directory, exist_ok=True)

    for js_path in js_paths:
        full_url = f"{BASE_PAGE_URL.rstrip('/')}{js_path}"
        await download_file(full_url, save_directory)

    await clean_up_old_files(save_directory, max_files=10)


def check_for_updates():
    try:
        result = subprocess.run(
            ["git", "fetch"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output = result.stdout.strip()

        logger.info("Checking for updates...")
        status_result = subprocess.run(
            ["git", "status"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        status_output = status_result.stdout.strip()

        if "Your branch is behind" in status_output:
            logger.info("<g>New update available!</g> Use `git pull`")

            return True
        else:
            logger.info("No updates available.")
            return False
    except Exception as e:
        logger.info(f"Error checking for updates: {e}")
        return False
