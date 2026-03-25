from os import environ

class Config(object):
    TG_BOT_TOKEN = environ.get("TG_BOT_TOKEN", "")
    APP_ID = int(environ.get("APP_ID", ""))
    API_HASH = environ.get("API_HASH", "")
    TG_USER_SESSION = environ.get("TG_USER_SESSION", "")
    FILE_CAPTION = environ.get('FILE_CAPTION', '<code>{file_name}</code>')
    ADMINS = [x.strip("@ ") for x in str(environ.get("ADMINS", "") or "").split(",") if x.strip("@ ")]
    STATUS_CHAT_GROUP_ID = -1003194225143
    STATUS_CHANNEL_ID = -1001631481154
    STATUS_CHANNEL_MSG_ID = 15
    
