import hashlib
import hmac
import uuid
import re
import html
import logging
import os
from typing import Dict, Any, List, Tuple, Optional, Callable
import time
from functools import wraps
import threading
from datetime import datetime, timedelta
import json
import jwt
from flask import request, session, abort, Response, g

class SecurityManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.rate_limiters = {}
        self.ip_blocklist = set()
        self.session_store = {}
        self.secret_key = config.get("SECRET_KEY", os.urandom(32).hex())
        self.jwt_secret = config.get("JWT_SECRET", os.urandom(32).hex())
        self.rate_limit_lock = threading.Lock()
        self.input_validators = self._initialize_validators()
        self.logger = self._setup_secure_logger()

    def _initialize_validators(self) -> Dict[str, Callable]:
        """Initialize input validators for different data types"""
        return {
            "alphanumeric": lambda s: bool(re.match(r'^[a-zA-Z0-9_-]+$', str(s))),
            "email": lambda s: bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', str(s))),
            "username": lambda s: bool(re.match(r'^[a-zA-Z0-9_]{3,30}$', str(s))),
            "url": lambda s: bool(re.match(r'^https?://[^\s/$.?#].[^\s]*$', str(s))),
            "integer": lambda s: isinstance(s, int) or (isinstance(s, str) and s.isdigit()),
            "float": lambda s: isinstance(s, (int, float)) or (isinstance(s, str) and self._is_float(str(s))),
            "boolean": lambda s: isinstance(s, bool) or (isinstance(s, str) and s.lower() in ['true', 'false', '0', '1']),
            "uuid": lambda s: bool(re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', str(s))),
            "safe_path": lambda s: '..' not in str(s) and not str(s).startswith('/') and not any(c in str(s) for c in ['\\', ':', '*', '?', '"', '<', '>', '|'])
        }

    def _is_float(self, value: str) -> bool:
        try:
            float(value)
            return True
        except ValueError:
            return False

    def _setup_secure_logger(self) -> logging.Logger:
        """Set up a logger with sensitive data filtering"""
        logger = logging.getLogger("security")
        logger.setLevel(logging.INFO)
        
        # Create a filter to redact sensitive information
        class SensitiveDataFilter(logging.Filter):
            def filter(self, record):
                if hasattr(record, 'msg') and isinstance(record.msg, str):
                    # Redact sensitive patterns like keys, tokens, credentials
                    patterns = [
                        (r'(api[_-]?key|secret[_-]?key|password|token|credential)["\']?\s*[:=]\s*["\']?([^"\';\s]+)', r'\1=REDACTED'),
                        (r'(razorpay[_-]?signature=)([^&\s]+)', r'\1REDACTED'),
                        (r'(Authorization:?\s+Bearer\s+)(\S+)', r'\1REDACTED'),
                    ]
                    for pattern, replacement in patterns:
                        record.msg = re.sub(pattern, replacement, record.msg, flags=re.IGNORECASE)
                return True
        
        # Set up handler with the filter
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        handler.addFilter(SensitiveDataFilter())
        logger.addHandler(handler)
        
        return logger

    # === Input Validation ===
    def validate_input(self, value: Any, validation_type: str) -> bool:
        """Validate input against a specific validator"""
        validator = self.input_validators.get(validation_type)
        if not validator:
            self.logger.warning(f"No validator found for type: {validation_type}")
            return False
        return validator(value)

    def sanitize_input(self, value: str) -> str:
        """Sanitize input string to prevent XSS"""
        if not isinstance(value, str):
            return value
        return html.escape(value)

    def sanitize_inputs(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize all string values in a dictionary"""
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.sanitize_input(value)
            elif isinstance(value, dict):
                result[key] = self.sanitize_inputs(value)
            elif isinstance(value, list):
                result[key] = [
                    self.sanitize_inputs(item) if isinstance(item, dict)
                    else self.sanitize_input(item) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    # === Rate Limiting ===
    def apply_rate_limit(self, key: str, limit: int, window: int) -> Tuple[bool, Optional[int]]:
        """
        Apply rate limiting to a specific key (e.g., IP address, user ID)
        Returns (allowed, retry_after_seconds)
        """
        with self.rate_limit_lock:
            now = time.time()
            
            # Initialize or get rate limiter for this key
            if key not in self.rate_limiters:
                self.rate_limiters[key] = {
                    "requests": [],
                    "blocked_until": 0
                }
            
            limiter = self.rate_limiters[key]
            
            # Check if currently blocked
            if limiter["blocked_until"] > now:
                retry_after = int(limiter["blocked_until"] - now)
                return False, retry_after
            
            # Clean up old requests outside the window
            limiter["requests"] = [t for t in limiter["requests"] if now - t <= window]
            
            # Check rate limit
            if len(limiter["requests"]) >= limit:
                # Block for double the window time
                limiter["blocked_until"] = now + (window * 2)
                self.logger.warning(f"Rate limit exceeded for {key}. Blocked for {window * 2}s")
                return False, window * 2
            
            # Add current request
            limiter["requests"].append(now)
            return True, None

    def rate_limit_decorator(self, limit: int, window: int):
        """
        Decorator for Flask routes to apply rate limiting
        Usage: @security_manager.rate_limit_decorator(5, 60)
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                # Get client IP
                client_ip = request.remote_addr
                
                # Apply rate limit
                allowed, retry_after = self.apply_rate_limit(client_ip, limit, window)
                if not allowed:
                    headers = {
                        'Retry-After': str(retry_after),
                        'X-RateLimit-Limit': str(limit),
                        'X-RateLimit-Reset': str(int(time.time() + retry_after))
                    }
                    self.logger.info(f"Rate limiting applied to {client_ip}")
                    return Response("Rate limit exceeded", status=429, headers=headers)
                
                return f(*args, **kwargs)
            return decorated_function
        return decorator

    # === CSRF Protection ===
    def generate_csrf_token(self) -> str:
        """Generate a CSRF token and store it in session"""
        if 'csrf_token' not in session:
            session['csrf_token'] = os.urandom(32).hex()
        return session['csrf_token']

    def verify_csrf_token(self, token: str) -> bool:
        """Verify the CSRF token against the one in session"""
        return 'csrf_token' in session and session['csrf_token'] == token

# Make sure the csrf_protect method can be called directly on a function:
def csrf_protect(self):
    """Decorator for CSRF protection on POST/PUT/DELETE routes"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.method in ['POST', 'PUT', 'DELETE']:
                # Get token from form, JSON or headers
                token = None
                if request.is_json:
                    token = request.json.get('csrf_token')
                elif request.form:
                    token = request.form.get('csrf_token')
                else:
                    token = request.headers.get('X-CSRF-Token')
                
                if not token or not self.verify_csrf_token(token):
                    self.logger.warning("CSRF validation failed")
                    abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

    # === Secure Path Operations ===
    def secure_path(self, base_path: str, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        Ensure file path doesn't escape the base directory
        Returns (is_secure, normalized_path)
        """
        if not self.validate_input(file_path, "safe_path"):
            return False, None
            
        # Normalize the path to prevent directory traversal
        norm_path = os.path.normpath(os.path.join(base_path, file_path))
        
        # Check if the normalized path is still under the base path
        if not norm_path.startswith(os.path.normpath(base_path)):
            self.logger.warning(f"Path traversal attempt: {file_path}")
            return False, None
            
        return True, norm_path
