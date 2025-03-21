import os

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('APP_SECRET_KEY', os.urandom(32).hex())
    JWT_SECRET = os.environ.get('JWT_SECRET', os.urandom(32).hex())
    RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
    RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
    FREE_GENERATIONS = 5
    MODELS_DIR = 'data/models'
    TOKEN_DATA_PATH = 'data/tokens'
    PAYMENT_RECORDS_PATH = 'data/payments'
    UPLOADS_DIR = 'data/uploads'
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    
    # Hunyuan model configuration
    HUNYUAN_MODEL_PATH = os.environ.get('HUNYUAN_MODEL_PATH', 'app/models/hunyuan_model')
    HUNYUAN_API_KEY = os.environ.get('HUNYUAN_API_KEY', '')
    HUNYUAN_API_URL = os.environ.get('HUNYUAN_API_URL', '')
    HUNYUAN_USE_LOCAL = os.environ.get('HUNYUAN_USE_LOCAL', 'False').lower() == 'true'

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    LOG_LEVEL = 'INFO'

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
