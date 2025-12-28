class Config:
    SECRET_KEY = '123456'
    DEBUG = False

class DevelopmentConfig(Config):
    DEBUG = False

class ProductionConfig(Config):
    DEBUG = False

config = {
    'default': Config,
    'development': DevelopmentConfig,
    'production': ProductionConfig
}