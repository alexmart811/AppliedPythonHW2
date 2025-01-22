from dotenv import load_dotenv
import os
import logging

logging.basicConfig(level=logging.DEBUG)

aiohttp_logger = logging.getLogger("aiohttp")
aiohttp_logger.setLevel(logging.DEBUG)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWM_TOKEN = os.getenv("OWM_TOKEN")