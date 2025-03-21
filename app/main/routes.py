from flask import render_template, current_app
from app.main import bp

@bp.route('/')
def index():
    """Home page route"""
    return render_template('index.html')

@bp.route('/about')
def about():
    """About page route"""
    return render_template('about.html')

@bp.route('/image-to-3d')
def image_to_3d():
    """Render the image to 3D conversion page"""
    csrf_token = current_app.security_manager.generate_csrf_token()
    return render_template('image_to_3d/upload.html', csrf_token=csrf_token)

@bp.route('/my-models')
def my_models():
    """Render the user's models page"""
    csrf_token = current_app.security_manager.generate_csrf_token()
    return render_template('my_models.html', csrf_token=csrf_token)

@bp.route('/chat')
def chat():
    """Render the customer support chat page"""
    csrf_token = current_app.security_manager.generate_csrf_token()
    return render_template('chat.html', csrf_token=csrf_token)
@bp.route('/payment/purchase')
def payment_purchase():
    """Render the payment purchase page"""
    csrf_token = current_app.security_manager.generate_csrf_token()
    return render_template('payment/purchase.html', csrf_token=csrf_token)
