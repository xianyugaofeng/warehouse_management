class Config:
    SECRET_KEY = '123456'
    DEBUG = False

class Development(Config):
    DEBUG = False

class ProductionConfig(Config):
    DEBUG = False

