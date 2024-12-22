import asyncio
import argparse
from random import randint
from typing import Any
from better_proxy import Proxy

from bot.config import settings
from bot.utils import logger
from bot.core.tapper import run_tapper, run_tapper_synchronous
from bot.core.registrator import register_sessions, get_tg_client
from bot.utils.accounts import Accounts
from bot.utils.proxy import get_proxy
from bot.utils.safe_guard import check_for_updates

__version__ = "1.0"

start_text = f"""

\x1b[38;5;27m____   ____ \x1b[38;5;162m            .__.__  .__                  __________ ___________________\x1b[0m
\x1b[38;5;27m\   \ /   /\x1b[38;5;162m____    ____ |__|  | |  | _____           \______   \\_____  \__    ___/ \x1b[0m
\x1b[38;5;155m \   Y   /\x1b[38;5;162m\__  \  /    \|  |  | |  | \__  \    ______ |    |  _/ /   |   \|    |   \x1b[0m
\x1b[38;5;155m  \     / \x1b[38;5;162m / __ \|   |  \  |  |_|  |__/ __ \_ /_____/ |    |   \/    |    \    |   \x1b[0m
\x1b[38;5;155m   \___/  \x1b[38;5;162m(____  /___|  /__|____/____(____  /         |______  /\_______  /____|   \x1b[0m
\x1b[38;5;162m               \/     \/                  \/                 \/         \/         \x1b[0m
                                                                       version: \x1b[38;5;119m{__version__}\x1b[0m
                  - by Khondoker X Hasan

Select an action:

    1. Run bot
    2. Create session
"""
if settings.GIT_UPDATE_CHECKER:
    check_for_updates()


async def process() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--action", type=int, help="Action to perform")
    parser.add_argument("-m", "--multithread", type=str,
                        help="Enable multi-threading")

    action = parser.parse_args().action
    ans = parser.parse_args().multithread

    if not action:
        print(start_text)

        while True:
            action = input("> ").strip()

            if not action.isdigit():
                logger.warning("Action must be number")
            elif action not in ["1", "2", "3"]:
                logger.warning("Action must be 1, 2 or 3")
            else:
                action = int(action)
                break

    if action == 2:
        await register_sessions()
    elif action == 1:
        if ans is None:
            while True:
                ans = input(
                    "> Do you want to run the bot with multi-thread? (y/n) : ").strip()
                if ans not in ["y", "n"]:
                    logger.warning("Answer must be y or n")
                else:
                    break

        if ans == "y":
            accounts = await Accounts().get_accounts()
            await run_tasks(accounts=accounts)

        else:
            accounts = await Accounts().get_accounts()
            await run_tapper_synchronous(accounts=accounts)


async def run_tasks(accounts: [Any, Any, list]):
    tasks = []
    for account in accounts:
        session_name, user_agent, raw_proxy = account.values()
        tg_client = await get_tg_client(session_name=session_name, proxy=raw_proxy)
        proxy = get_proxy(raw_proxy=raw_proxy)
        tasks.append(
            asyncio.create_task(
                run_tapper(
                    tg_client=tg_client,
                    user_agent=user_agent,
                    proxy=proxy
                )
            )
        )

    await asyncio.gather(*tasks)
