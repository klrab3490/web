import os
import uuid
from typing import Dict, Any, Tuple, Optional
from app.services.llm_service import LLMService
from app.services.image_to_3d_service import ImageTo3DService

class ModelGenerationController:
    """Controller for 3D model generation"""
    
    def __init__(self, config: Dict[str, Any], llm_service: LLMService, image_to_3d_service: ImageTo3DService):
        self.config = config
        self.llm_service = llm_service
        self.image_to_3d_service = image_to_3d_service
        self.models_dir = config.get('MODELS_DIR', 'data/models')
        
        # Ensure models directory exists
        os.makedirs(self.models_dir, exist_ok=True)
    
    def generate_openscad_model(self, user_id: str, parameters: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Generate an OpenSCAD model
        
        Args:
            user_id: ID of the user requesting the model
            parameters: Model parameters
            
        Returns:
            Tuple of (success, result_data)
        """
        try:
            # Create prompt for the LLM
            shape = parameters.get('shape', 'cube')
            param_text = "\n".join([f"- {k}: {v}" for k, v in parameters.items()])
            prompt = f"Generate OpenSCAD code for a {shape} with: {param_text}"
            
            # Generate code
            code = self.llm_service.generate_code(prompt)
            
            # Generate model ID
            model_id = f"model_{uuid.uuid4().hex[:8]}"
            
            # Save code to file
            model_dir = os.path.join(self.models_dir, model_id)
            os.makedirs(model_dir, exist_ok=True)
            
            file_path = os.path.join(model_dir, f"{model_id}.scad")
            with open(file_path, 'w') as f:
                f.write(code)
                
            return True, {
                "model_id": model_id,
                "file_path": file_path,
                "code": code,
                "parameters": parameters
            }
            
        except Exception as e:
            return False, {"error": str(e)}
    
    def generate_3d_from_image(self, user_id: str, image_path: str, parameters: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Generate a 3D model from an image
        
        Args:
            user_id: ID of the user requesting the model
            image_path: Path to the input image
            parameters: Processing parameters
            
        Returns:
            Tuple of (success, result_data)
        """
        try:
            return self.image_to_3d_service.process_image(image_path, parameters)
        except Exception as e:
            return False, {"error": str(e)}
EOFcat > app/controllers/model_generation_controller.py << 'EOF'
import os
import uuid
from typing import Dict, Any, Tuple, Optional
from app.services.llm_service import LLMService
from app.services.image_to_3d_service import ImageTo3DService

class ModelGenerationController:
    """Controller for 3D model generation"""
    
    def __init__(self, config: Dict[str, Any], llm_service: LLMService, image_to_3d_service: ImageTo3DService):
        self.config = config
        self.llm_service = llm_service
        self.image_to_3d_service = image_to_3d_service
        self.models_dir = config.get('MODELS_DIR', 'data/models')
        
        # Ensure models directory exists
        os.makedirs(self.models_dir, exist_ok=True)
    
    def generate_openscad_model(self, user_id: str, parameters: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Generate an OpenSCAD model
        
        Args:
            user_id: ID of the user requesting the model
            parameters: Model parameters
            
        Returns:
            Tuple of (success, result_data)
        """
        try:
            # Create prompt for the LLM
            shape = parameters.get('shape', 'cube')
            param_text = "\n".join([f"- {k}: {v}" for k, v in parameters.items()])
            prompt = f"Generate OpenSCAD code for a {shape} with: {param_text}"
            
            # Generate code
            code = self.llm_service.generate_code(prompt)
            
            # Generate model ID
            model_id = f"model_{uuid.uuid4().hex[:8]}"
            
            # Save code to file
            model_dir = os.path.join(self.models_dir, model_id)
            os.makedirs(model_dir, exist_ok=True)
            
            file_path = os.path.join(model_dir, f"{model_id}.scad")
            with open(file_path, 'w') as f:
                f.write(code)
                
            return True, {
                "model_id": model_id,
                "file_path": file_path,
                "code": code,
                "parameters": parameters
            }
            
        except Exception as e:
            return False, {"error": str(e)}
    
    def generate_3d_from_image(self, user_id: str, image_path: str, parameters: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Generate a 3D model from an image
        
        Args:
            user_id: ID of the user requesting the model
            image_path: Path to the input image
            parameters: Processing parameters
            
        Returns:
            Tuple of (success, result_data)
        """
        try:
            return self.image_to_3d_service.process_image(image_path, parameters)
        except Exception as e:
            return False, {"error": str(e)}
