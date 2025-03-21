import os
from flask import Flask
from dotenv import load_dotenv
from config import config

# Load environment variables
load_dotenv()

def create_app(config_name=None):
    # Determine config to use
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    # Create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Create necessary directories
    for path in [
        app.config['MODELS_DIR'], 
        app.config['TOKEN_DATA_PATH'], 
        app.config['PAYMENT_RECORDS_PATH'],
        app.config['UPLOADS_DIR'],
        os.path.dirname(app.config['HUNYUAN_MODEL_PATH'])
    ]:
        os.makedirs(path, exist_ok=True)
    
    # Initialize security manager
    from app.security.security_manager import SecurityManager
    app.security_manager = SecurityManager(app.config)
    
    # Initialize media service
    from app.services.media_service import MediaService
    app.media_service = MediaService(app.config, app.security_manager)
    
    # Initialize LLM service for 3D model generation
    try:
        from app.services.models import LLMService, WebCrawler
        # First create web crawler if web search is enabled
        if app.config.get('ENABLE_WEB_SEARCH', False):
            app.web_crawler = WebCrawler()
        else:
            app.web_crawler = None
            
        # Initialize LLM service
        app.llm_service = LLMService(app.config)
        app.logger.info("LLM service initialized successfully")
    except Exception as e:
        app.logger.error(f"Failed to initialize LLM service: {str(e)}")
        app.llm_service = None
    
    # Register blueprints
    from app.main import bp as main_bp
    from app.api import bp as api_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Add CSRF token to all responses
    @app.after_request
    def add_csrf_token(response):
        if response.mimetype == 'text/html':
            token = app.security_manager.generate_csrf_token()
            # Add CSRF token to window.csrfToken in JavaScript
            script = f'<script>window.csrfToken = "{token}";</script>'
            response_data = response.get_data(as_text=True)
            if '</head>' in response_data:
                modified_data = response_data.replace('</head>', f'{script}</head>')
                response.set_data(modified_data)
        return response
    
    # Add health check endpoint for LLM service
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """API endpoint to check if the service is running and model is loaded"""
        if hasattr(app, 'llm_service') and app.llm_service and hasattr(app.llm_service, 'model_loaded') and app.llm_service.model_loaded:
            return {"status": "ok", "model_loaded": True}
        elif hasattr(app, 'llm_service') and app.llm_service:
            return {"status": "degraded", "model_loaded": False}
        else:
            return {"status": "error", "model_loaded": False}
    
    return app