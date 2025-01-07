# [![Static Badge](https://img.shields.io/badge/Telegram-Bot%20Link-Link?style=for-the-badge&logo=Telegram&logoColor=white&logoSize=auto&color=blue)](https://t.me/Vanilla_Finance_Bot/Vanillafinance?startapp=inviteId10512928)

## Vanilla Finance Bot

> **Recommendation**: Use **Python 3.10**

---

# Features
| Feature                           | Supported |
|-----------------------------------|:---------:|
| Multithreading                    |     ✅     |
| Proxy binding to session (adv)    |     ✅     |
| User-Agent binding to session     |     ✅     |
| Support for `.session` files      |     ✅     |
| Auto registration in bot          |     ✅     |
| Auto-tasks                        |     ✅     |
| Daily rewards                     |     ✅     |
| Auto tap                |     ✅     |
| Auto upgrade level                |     ✅     |
| Advanced anti-detection           |     ✅     |

---

## [Settings](https://github.com/khondokerXhasan/Vanilla-finance-BOT/blob/master/.env-example/)
| Setting                  | Description                                                                                               | Default Value           |
|--------------------------|-----------------------------------------------------------------------------------------------------------|-------------------------|
| **API_ID / API_HASH**    | Platform data from which to run the Telegram session.                                                     | Required for operation  |
| **USE_RANDOM_DELAY_IN_RUN** | Enables random delays during task execution to avoid detection.                                           | `True`                 |
| **START_DELAY**          | Delay (in seconds) between session starts.                                                               | `[30, 60]`             |
| **AUTO_TAP**             | Enable or disable automatic tap.                                                                         | `True`                 |
| **TAP_COUNT**            | Range for the number of taps.                                                                            | `[80, 100]`            |
| **UPGRADE_LEVEL_WITH_SUGER** | Enable or disable upgrading level with sugar.                                                        | `False`                |
| **AUTO_TASK**            | Enable or disable automatic task execution.                                                              | `True`                 |
| **REF_ID**               | Referral ID.                                                                                             | `''`    |
| **SAVE_JS_FILES**        | Save JavaScript files (experimental).                                                                    | `False`                |
| **ADVANCED_ANTI_DETECTION** | Enable advanced anti-detection measures.                                                              | `True`                 |
| **ENABLE_SSL**           | Enable or disable SSL.                                                                                   | `True`                 |
| **USE_PROXY_FROM_FILE**  | Use proxy from file.                                                                                     | `False`                |
| **GIT_UPDATE_CHECKER**   | Enable Git update checker.                                                                               | `True`                 |
---
## Quick Start 📚

To install dependencies and run the bot quickly, use the provided batch file (`run.bat`) for Windows or the shell script (`run.sh`) for Linux.

### Prerequisites
Ensure you have **Python 3.10 or Greater** installed.

### Obtaining API Keys
1. Go to [my.telegram.org](https://my.telegram.org) and log in.
2. Under **API development tools**, create a new application to get your `API_ID` and `API_HASH`, and add these to your `.env` file.

---

## Installation

### Clone the Repository
```shell
git clone https://github.com/khondokerXhasan/Vanilla-finance-BOT
cd Vanilla-finance-BOT
```

Then you can do automatic installation by typing:

Windows:
```shell
run.bat
```

Linux:
```shell
run.sh
```

# Linux manual installation
```shell
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
cp .env-example .env
nano .env  # Here you must specify your API_ID and API_HASH, the rest is taken by default
python3 main.py
```

You can also use arguments for quick start, for example:
```shell
~/Vanilla-finance-BOT >>> python3 main.py --action (1/2)
# Or
~/Vanilla-finance-BOT >>> python3 main.py -a (1/2)

# 1 - Run clicker
# 2 - Creates a session
```

# Windows manual installation
```shell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env-example .env
# Here you must specify your API_ID and API_HASH, the rest is taken by default
python main.py
```

You can also use arguments for quick start, for example:
```shell
~/Vanilla-finance-BOT >>> python main.py --action (1/2)
# Or
~/Vanilla-finance-BOT >>> python main.py -a (1/2)

# 1 - Run clicker
# 2 - Creates a session
```

## Usage
1. **First Launch**: Create a session with the `--action 2` option. This will create a `sessions` folder for storing all accounts and an `accounts.json` configuration file.
2. **Existing Sessions**: If you already have sessions, add them to the `sessions` folder and run the bot with the clicker mode.

### Example of `accounts.json`
```json
[
  {
    "session_name": "name_example",
    "user_agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.165 Mobile Safari/537.36",
    "proxy": "type://user:pass:ip:port"  // "proxy": "" if no proxy
  }
]
```

### Contacts

[Join our Telegram Channel](https://t.me/scripts_hub)
