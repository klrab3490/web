from flask import Blueprint

bp = Blueprint('api', __name__)

from app.api import routes
from app.api import chat_routes  # Add this line