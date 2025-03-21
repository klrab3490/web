import time
from flask import Response, abort
from flask import jsonify, request, session, g, send_file, current_app
import uuid
import os
from werkzeug.utils import secure_filename
from app.security.security_manager import SecurityManager
from app.services.llm_service import LLMService
from app.services.image_to_3d_service import ImageTo3DService
from app.services.media_service import MediaService
from app.api import bp
from functools import wraps

# Session storage for models
model_sessions = {}

# Create empty variables for services that will be initialized in the context
_security_manager = None
_llm_service = None
_image_to_3d_service = None
_media_service = None

def get_security_manager():
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager(current_app.config)
    return _security_manager

def get_llm_service():
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

def get_image_to_3d_service():
    global _image_to_3d_service
    if _image_to_3d_service is None:
        _image_to_3d_service = ImageTo3DService(current_app.config)
    return _image_to_3d_service

def get_media_service():
    global _media_service
    if _media_service is None:
        _media_service = MediaService(current_app.config, get_security_manager())
    return _media_service

# Helper to get user ID
def get_user_id():
    """Get or create a user ID for the current session"""
    if 'user_id' not in session:
        session['user_id'] = f"user_{uuid.uuid4().hex[:8]}"
    return session['user_id']

# Custom decorators to apply security functions
def csrf_protect_decorator():
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            security_manager = get_security_manager()
            # Get token from form, JSON or headers
            token = None
            if request.is_json:
                token = request.json.get('csrf_token')
            elif request.form:
                token = request.form.get('csrf_token')
            else:
                token = request.headers.get('X-CSRF-Token')
            
            if request.method in ['POST', 'PUT', 'DELETE']:
                if not token or not security_manager.verify_csrf_token(token):
                    security_manager.logger.warning("CSRF validation failed")
                    abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def rate_limit_decorator(limit, window):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            security_manager = get_security_manager()
            
            # Get client IP
            client_ip = request.remote_addr
            
            # Apply rate limit
            allowed, retry_after = security_manager.apply_rate_limit(client_ip, limit, window)
            if not allowed:
                headers = {
                    'Retry-After': str(retry_after),
                    'X-RateLimit-Limit': str(limit),
                    'X-RateLimit-Reset': str(int(time.time() + retry_after))
                }
                security_manager.logger.info(f"Rate limiting applied to {client_ip}")
                return Response("Rate limit exceeded", status=429, headers=headers)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@bp.before_request
def before_request():
    """Run before each API request"""
    g.user_id = get_user_id()

@bp.route('/generate', methods=['POST'])
@csrf_protect_decorator()
@rate_limit_decorator(10, 60)  # 10 requests per minute
def generate_model():
    """Generate a 3D model based on parameters"""
    try:
        security_manager = get_security_manager()
        llm_service = get_llm_service()
        
        # Get and validate data
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request data"}), 400
            
        # Check for required fields
        if 'model_type' not in data:
            return jsonify({"error": "Model type is required"}), 400
            
        # Sanitize inputs
        sanitized_data = security_manager.sanitize_inputs(data)
        
        # Get user and session IDs
        user_id = g.user_id
        session_id = sanitized_data.get('session_id', str(uuid.uuid4()))
        
        # Process model parameters
        model_type = sanitized_data['model_type']
        parameters = sanitized_data.get('parameters', {})
        
        # For now, we'll generate OpenSCAD code directly
        if model_type == 'openscad':
            # Create prompt for the LLM
            param_text = "\n".join([f"- {k}: {v}" for k, v in parameters.items()])
            prompt = f"Generate OpenSCAD code for a {model_type} model with: {param_text}"
            
            # Generate code
            code = llm_service.generate_code(prompt)
            
            # Store in session
            if session_id not in model_sessions:
                model_sessions[session_id] = {
                    "user_id": user_id,
                    "models": []
                }
                
            # Generate model ID
            model_id = f"model_{uuid.uuid4().hex[:8]}"
            
            # Save code to file
            models_dir = current_app.config['MODELS_DIR']
            os.makedirs(models_dir, exist_ok=True)
            
            is_secure, file_path = security_manager.secure_path(
                models_dir,
                f"{model_id}.scad"
            )
            
            if not is_secure:
                return jsonify({"error": "Invalid model ID format"}), 400
                
            with open(file_path, 'w') as f:
                f.write(code)
                
            # Create model data
            model_data = {
                "model_id": model_id,
                "model_type": "openscad",
                "file_path": file_path,
                "code": code,
                "parameters": parameters
            }
            
            # Add to session
            model_sessions[session_id]["models"].append(model_data)
            
            # Return success response
            return jsonify({
                "success": True,
                "model": {
                    "model_id": model_id,
                    "model_type": "openscad",
                    "code_preview": code[:200] + ("..." if len(code) > 200 else "")
                },
                "session_id": session_id
            })
        else:
            return jsonify({"error": f"Unsupported model type: {model_type}"}), 400
            
    except Exception as e:
        get_security_manager().logger.error(f"Error in generate_model: {str(e)}")
        return jsonify({"error": "An error occurred processing your request"}), 500

@bp.route('/model/<model_id>', methods=['GET'])
@rate_limit_decorator(20, 60)  # 20 requests per minute
def get_model(model_id):
    """Get a generated model by ID"""
    try:
        security_manager = get_security_manager()
        
        # Validate model ID format
        if not security_manager.validate_input(model_id, "alphanumeric"):
            return jsonify({"error": "Invalid model ID format"}), 400
            
        # Find model in sessions
        for session_id, session_data in model_sessions.items():
            for model in session_data["models"]:
                if model["model_id"] == model_id:
                    # Return model data
                    return jsonify({
                        "success": True,
                        "model": {
                            "model_id": model["model_id"],
                            "model_type": model["model_type"],
                            "code": model["code"],
                            "parameters": model["parameters"]
                        }
                    })
                    
        # Model not found
        return jsonify({"error": "Model not found"}), 404
        
    except Exception as e:
        get_security_manager().logger.error(f"Error in get_model: {str(e)}")
        return jsonify({"error": "An error occurred processing your request"}), 500

@bp.route('/upload-image', methods=['POST'])
@csrf_protect_decorator()
@rate_limit_decorator(5, 60)  # 5 requests per minute
def upload_image():
    """Upload an image for 3D processing"""
    try:
        security_manager = get_security_manager()
        media_service = get_media_service()
        
        # Check if file is present
        if 'image' not in request.files:
            return jsonify({"error": "No image file provided"}), 400
            
        file = request.files['image']
        if file.filename == '':
            return jsonify({"error": "No image selected"}), 400
            
        # Get user ID
        user_id = g.user_id
        
        # Save the uploaded image
        success, result = media_service.save_uploaded_image(file, user_id)
        
        if not success:
            return jsonify({"error": result.get("error", "Failed to upload image")}), 400
            
        # Return success response with file info
        return jsonify({
            "success": True,
            "file_id": result["file_id"],
            "file_size": result["file_size"],
            "file_type": result["file_type"]
        })
            
    except Exception as e:
        get_security_manager().logger.error(f"Error in upload_image: {str(e)}")
        return jsonify({"error": "An error occurred processing your upload"}), 500

@bp.route('/user-images', methods=['GET'])
@rate_limit_decorator(10, 60)  # 10 requests per minute
def get_user_images():
    """Get list of images uploaded by the user"""
    try:
        user_id = g.user_id
        media_service = get_media_service()
        result = media_service.get_user_images(user_id)
        
        if "error" in result:
            return jsonify({"error": result["error"]}), 500
            
        return jsonify({"success": True, "images": result["images"]})
            
    except Exception as e:
        get_security_manager().logger.error(f"Error in get_user_images: {str(e)}")
        return jsonify({"error": "An error occurred retrieving your images"}), 500

@bp.route('/generate-3d-from-image', methods=['POST'])
@csrf_protect_decorator()
@rate_limit_decorator(2, 60)  # 2 requests per minute (resource-intensive)
def generate_3d_from_image():
    """Generate a 3D model from an uploaded image"""
    try:
        # Get services
        security_manager = get_security_manager()
        image_to_3d_service = get_image_to_3d_service()
        
        # Get and validate data
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request data"}), 400
            
        # Check for required fields
        if 'file_id' not in data:
            return jsonify({"error": "File ID is required"}), 400
            
        # Sanitize inputs
        sanitized_data = security_manager.sanitize_inputs(data)
        
        # Get user ID
        user_id = g.user_id
        
        # Get file path
        file_id = sanitized_data['file_id']
        user_uploads_dir = os.path.join(current_app.config.get('UPLOADS_DIR', 'data/uploads'), user_id)
        
        # Create secure path
        is_secure, file_path = security_manager.secure_path(user_uploads_dir, file_id)
        
        if not is_secure or not os.path.exists(file_path):
            return jsonify({"error": "Invalid or missing file"}), 400
        
        # Extract processing parameters
        params = sanitized_data.get('parameters', {})
        
        # Process the image
        success, result = image_to_3d_service.process_image(file_path, params)
        
        if not success:
            return jsonify({"error": result.get("error", "Failed to process image")}), 400
            
        # Return success response
        return jsonify({
            "success": True,
            "model_id": result["model_id"],
            "parameters": params,
            "processing_time": result["processing_time"]
        })
            
    except Exception as e:
        get_security_manager().logger.error(f"Error in generate_3d_from_image: {str(e)}")
        return jsonify({"error": "An error occurred processing your image"}), 500

@bp.route('/3d-model/<model_id>', methods=['GET'])
@rate_limit_decorator(20, 60)  # 20 requests per minute
def get_3d_model(model_id):
    """Get a generated 3D model by ID"""
    try:
        security_manager = get_security_manager()
        
        # Validate model ID format
        if not security_manager.validate_input(model_id, "alphanumeric"):
            return jsonify({"error": "Invalid model ID format"}), 400
            
        # Get model directory
        models_dir = current_app.config.get('MODELS_DIR', 'data/models')
        model_dir = os.path.join(models_dir, model_id)
        
        if not os.path.exists(model_dir):
            return jsonify({"error": "Model not found"}), 404
            
        # Get available formats
        formats = {}
        for ext in ['obj', 'stl', 'glb']:
            file_path = os.path.join(model_dir, f"{model_id}.{ext}")
            if os.path.exists(file_path):
                formats[ext] = f"/api/download-model/{model_id}/{ext}"
                
        # Check for preview image
        preview_path = os.path.join(model_dir, "preview.png")
        preview_url = f"/api/model-preview/{model_id}" if os.path.exists(preview_path) else None
        
        # Return model metadata
        return jsonify({
            "success": True,
            "model_id": model_id,
            "formats": formats,
            "preview_url": preview_url
        })
            
    except Exception as e:
        get_security_manager().logger.error(f"Error in get_3d_model: {str(e)}")
        return jsonify({"error": "An error occurred retrieving the model"}), 500

@bp.route('/download-model/<model_id>/<format>', methods=['GET'])
@rate_limit_decorator(10, 60)  # 10 requests per minute
def download_model(model_id, format):
    """Download a 3D model in the specified format"""
    try:
        security_manager = get_security_manager()
        
        # Validate model ID and format
        if not security_manager.validate_input(model_id, "alphanumeric"):
            return jsonify({"error": "Invalid model ID format"}), 400
            
        if format not in ['obj', 'stl', 'glb']:
            return jsonify({"error": "Invalid format"}), 400
            
        # Get model file path
        models_dir = current_app.config.get('MODELS_DIR', 'data/models')
        file_path = os.path.join(models_dir, model_id, f"{model_id}.{format}")
        
        if not os.path.exists(file_path):
            return jsonify({"error": "Model file not found"}), 404
            
        # Return the file
        return send_file(
            file_path,
            as_attachment=True,
            download_name=f"{model_id}.{format}",
            mimetype=f"model/{format}"
        )
            
    except Exception as e:
        get_security_manager().logger.error(f"Error in download_model: {str(e)}")
        return jsonify({"error": "An error occurred downloading the model"}), 500

@bp.route('/model-preview/<model_id>', methods=['GET'])
@rate_limit_decorator(20, 60)  # 20 requests per minute
def get_model_preview(model_id):
    """Get a preview image of a 3D model"""
    try:
        security_manager = get_security_manager()
        
        # Validate model ID
        if not security_manager.validate_input(model_id, "alphanumeric"):
            return jsonify({"error": "Invalid model ID format"}), 400
            
        # Get preview image path
        models_dir = current_app.config.get('MODELS_DIR', 'data/models')
        preview_path = os.path.join(models_dir, model_id, "preview.png")
        
        if not os.path.exists(preview_path):
            return jsonify({"error": "Preview not found"}), 404
            
        # Return the image
        return send_file(preview_path, mimetype="image/png")
            
    except Exception as e:
        get_security_manager().logger.error(f"Error in get_model_preview: {str(e)}")
        return jsonify({"error": "An error occurred retrieving the preview"}), 500