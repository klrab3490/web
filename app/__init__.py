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
    
    return app