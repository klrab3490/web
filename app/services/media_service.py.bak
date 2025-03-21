import os
import uuid
import imghdr
from werkzeug.utils import secure_filename
from typing import Dict, Any, Optional, Tuple
import logging

class MediaService:
    """Service for handling media uploads and processing"""
    
    def __init__(self, config: Dict[str, Any], security_manager):
        self.logger = logging.getLogger("media_service")
        self.config = config
        self.security_manager = security_manager
        self.uploads_dir = config.get("UPLOADS_DIR", "data/uploads")
        
        # Ensure uploads directory exists
        os.makedirs(self.uploads_dir, exist_ok=True)
        
        # Allowed image types
        self.allowed_extensions = {'png', 'jpg', 'jpeg', 'webp'}
        self.max_file_size = config.get("MAX_IMAGE_SIZE", 10 * 1024 * 1024)  # 10MB default
    
    def save_uploaded_image(self, file, user_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Save an uploaded image file
        
        Args:
            file: The uploaded file object
            user_id: ID of the user uploading the file
            
        Returns:
            Tuple of (success, result_data)
        """
        try:
            if not file:
                return False, {"error": "No file provided"}
            
            # Check file size
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            
            if file_size > self.max_file_size:
                return False, {"error": f"File too large. Maximum size is {self.max_file_size / 1024 / 1024}MB"}
            
            # Verify it's a valid image
            file_content = file.read(1024)  # Read first 1KB to check file type
            file.seek(0)
            file_type = imghdr.what(None, file_content)
            
            if not file_type or file_type not in self.allowed_extensions:
                return False, {"error": "Invalid image format. Allowed formats: PNG, JPEG, WebP"}
            
            # Create a secure filename
            original_filename = secure_filename(file.filename)
            file_ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else file_type
            new_filename = f"{uuid.uuid4().hex}.{file_ext}"
            
            # Create user directory if it doesn't exist
            user_dir = os.path.join(self.uploads_dir, user_id)
            os.makedirs(user_dir, exist_ok=True)
            
            # Create a secure path and save the file
            is_secure, file_path = self.security_manager.secure_path(user_dir, new_filename)
            
            if not is_secure:
                return False, {"error": "Security error: Invalid file path"}
            
            file.save(file_path)
            
            self.logger.info(f"Image uploaded: {file_path}")
            
            return True, {
                "file_id": new_filename,
                "file_path": file_path,
                "file_size": file_size,
                "file_type": file_type,
                "original_name": original_filename
            }
            
        except Exception as e:
            self.logger.error(f"Error saving uploaded image: {str(e)}")
            return False, {"error": str(e)}
    
    def get_user_images(self, user_id: str) -> Dict[str, Any]:
        """Get list of images uploaded by a user"""
        try:
            user_dir = os.path.join(self.uploads_dir, user_id)
            
            if not os.path.exists(user_dir):
                return {"images": []}
            
            images = []
            for filename in os.listdir(user_dir):
                file_path = os.path.join(user_dir, filename)
                if os.path.isfile(file_path) and self._is_valid_image(file_path):
                    file_stats = os.stat(file_path)
                    images.append({
                        "file_id": filename,
                        "file_path": file_path,
                        "file_size": file_stats.st_size,
                        "uploaded_at": file_stats.st_mtime
                    })
            
            return {"images": images}
            
        except Exception as e:
            self.logger.error(f"Error getting user images: {str(e)}")
            return {"error": str(e), "images": []}
    
    def _is_valid_image(self, file_path: str) -> bool:
        """Check if a file is a valid image"""
        try:
            with open(file_path, 'rb') as f:
                file_type = imghdr.what(f)
                return file_type in self.allowed_extensions
        except:
            return False
