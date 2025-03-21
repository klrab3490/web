import os

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('APP_SECRET_KEY', os.urandom(32).hex())
    JWT_SECRET = os.environ.get('JWT_SECRET', os.urandom(32).hex())
    RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
    RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
    FREE_GENERATIONS = 5
    MODELS_DIR = os.environ.get("MODELS_DIR", "data/models")
    TOKEN_DATA_PATH = 'data/tokens'
    PAYMENT_RECORDS_PATH = 'data/payments'
    UPLOADS_DIR = os.environ.get("UPLOADS_DIR", "data/uploads")
    MAX_IMAGE_SIZE = int(os.environ.get("MAX_IMAGE_SIZE", 10 * 1024 * 1024))  # 10MB
    
    # Hunyuan model configuration
    HUNYUAN_MODEL_PATH = os.environ.get('HUNYUAN_MODEL_PATH', 'app/models/hunyuan_model')
    HUNYUAN_API_KEY = os.environ.get('HUNYUAN_API_KEY', '')
    HUNYUAN_API_URL = os.environ.get('HUNYUAN_API_URL', '')
    HUNYUAN_USE_LOCAL = os.environ.get('HUNYUAN_USE_LOCAL', 'False').lower() == 'true'
    
    # Mistral LLM configuration for 3D model generation
    MISTRAL_MODEL_NAME = os.environ.get("MISTRAL_MODEL_NAME", "mistralai/Mistral-7B-Instruct-v0.1")
    MISTRAL_TOKENIZER_NAME = os.environ.get("MISTRAL_TOKENIZER_NAME", None)
    MISTRAL_MAX_LENGTH = int(os.environ.get("MISTRAL_MAX_LENGTH", "1024"))
    MISTRAL_LOAD_8BIT = os.environ.get("MISTRAL_LOAD_8BIT", "True").lower() == "true"
    
    # OpenSCAD configuration
    OPENSCAD_BINARY = os.environ.get("OPENSCAD_BINARY", None)  # Will be auto-detected if not set
    ENABLE_3D_PREVIEW = os.environ.get("ENABLE_3D_PREVIEW", "True").lower() == "true"
    
    # Web search for templates
    SERP_API_KEY = os.environ.get("SERP_API_KEY", "")
    ENABLE_WEB_SEARCH = os.environ.get("ENABLE_WEB_SEARCH", "False").lower() == "true"
    
    # 3D model rendering settings
    MODEL_PREVIEW_SIZE = (800, 600)
    MODEL_PREVIEW_QUALITY = 90
    STL_GENERATION_ENABLED = True

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    # Use lighter model for development if specified
    MISTRAL_MODEL_NAME = os.environ.get("DEV_MISTRAL_MODEL_NAME", Config.MISTRAL_MODEL_NAME)
    # Optionally disable web search in development
    ENABLE_WEB_SEARCH = os.environ.get("DEV_ENABLE_WEB_SEARCH", "False").lower() == "true"

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    LOG_LEVEL = 'INFO'
    # Ensure we have proper security in production
    SECRET_KEY = os.environ.get('APP_SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("No SECRET_KEY set for production environment")
    # Use high quality model in production
    MISTRAL_MODEL_NAME = os.environ.get("PROD_MISTRAL_MODEL_NAME", Config.MISTRAL_MODEL_NAME)
    # Optimize for production use
    MISTRAL_LOAD_8BIT = os.environ.get("PROD_MISTRAL_LOAD_8BIT", "True").lower() == "true"
    # Web search in production if API key is available
    ENABLE_WEB_SEARCH = os.environ.get("PROD_ENABLE_WEB_SEARCH", "True" if Config.SERP_API_KEY else "False").lower() == "true"

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}