from flask import jsonify, request, session, g, current_app, abort, Response
import uuid
import time
from datetime import datetime
from functools import wraps
from app.api import bp
from app.services.llm_service import LLMService
from app.security.security_manager import SecurityManager

# Chat sessions storage
chat_sessions = {}

# Create empty variables for services that will be initialized in the context
_security_manager = None
_llm_service = None

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

# Helper to get user ID
def get_user_id():
    """Get or create a user ID for the current session"""
    if 'user_id' not in session:
        session['user_id'] = f"user_{uuid.uuid4().hex[:8]}"
    return session['user_id']

@bp.route('/chat/start', methods=['POST'])
@csrf_protect_decorator()
@rate_limit_decorator(10, 60)  # 10 requests per minute
def start_chat():
    """Start a new chat session"""
    try:
        # Create a new chat session
        session_id = f"chat_{uuid.uuid4().hex[:8]}"
        user_id = get_user_id()
        
        chat_sessions[session_id] = {
            "user_id": user_id,
            "history": [],
            "created_at": datetime.now().isoformat()
        }
        
        # Return the session ID
        return jsonify({
            "success": True,
            "session_id": session_id,
            "welcome_message": "Hello! How can I help you with 3D model generation today?"
        })
        
    except Exception as e:
        get_security_manager().logger.error(f"Error in start_chat: {str(e)}")
        return jsonify({"error": "Failed to start chat session"}), 500

@bp.route('/chat/message', methods=['POST'])
@csrf_protect_decorator()
@rate_limit_decorator(20, 60)  # 20 requests per minute
def send_message():
    """Send a message in a chat session"""
    try:
        security_manager = get_security_manager()
        llm_service = get_llm_service()
        
        # Get and validate data
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request data"}), 400
            
        # Check for required fields
        if 'message' not in data or 'session_id' not in data:
            return jsonify({"error": "Message and session ID are required"}), 400
            
        # Sanitize inputs
        sanitized_data = security_manager.sanitize_inputs(data)
        message = sanitized_data['message']
        session_id = sanitized_data['session_id']
        
        # Check if the session exists
        if session_id not in chat_sessions:
            return jsonify({"error": "Chat session not found"}), 404
            
        # Get the chat history
        chat_session = chat_sessions[session_id]
        
        # Add user message to history
        chat_session["history"].append({
            "role": "user",
            "content": message
        })
        
        # Generate response with LLM
        response = llm_service.chat_with_customer(message, chat_session["history"])
        
        # Add assistant response to history
        chat_session["history"].append({
            "role": "assistant",
            "content": response
        })
        
        # Return the assistant's response
        return jsonify({
            "success": True,
            "response": response
        })
        
    except Exception as e:
        get_security_manager().logger.error(f"Error in send_message: {str(e)}")
        return jsonify({"error": "Failed to process message"}), 500

@bp.route('/chat/history/<session_id>', methods=['GET'])
@rate_limit_decorator(10, 60)  # 10 requests per minute
def get_chat_history(session_id):
    """Get chat history for a session"""
    try:
        security_manager = get_security_manager()
        
        # Validate session ID format
        if not security_manager.validate_input(session_id, "alphanumeric"):
            return jsonify({"error": "Invalid session ID format"}), 400
            
        # Check if the session exists
        if session_id not in chat_sessions:
            return jsonify({"error": "Chat session not found"}), 404
            
        # Get the chat history
        chat_session = chat_sessions[session_id]
        
        # Return the chat history
        return jsonify({
            "success": True,
            "history": chat_session["history"]
        })
        
    except Exception as e:
        get_security_manager().logger.error(f"Error in get_chat_history: {str(e)}")
        return jsonify({"error": "Failed to retrieve chat history"}), 500