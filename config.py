from os import getenv

class Config(object):
    TG_BOT_TOKEN = getenv("TG_BOT_TOKEN", "")
    APP_ID = int(getenv("APP_ID", ""))
    API_HASH = getenv("API_HASH", "")
    TG_USER_SESSION = getenv("TG_USER_SESSION", "")
    ADMINS = [x.strip("@ ") for x in str(getenv("ADMINS", "") or "").split(",") if x.strip("@ ")]
    
