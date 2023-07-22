import os
import logging

class Config(object):
    TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
    APP_ID = int(os.environ.get("APP_ID", ""))
    API_HASH = os.environ.get("API_HASH", "")
    TG_USER_SESSION = os.environ.get("TG_USER_SESSION", "")
    FILE_CAPTION = os.environ.get('FILE_CAPTION', '<code>{file_name}</code>')
    APPROVAL_CNL = -1001592628992
def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
