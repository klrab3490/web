import os
import re
import uuid
import imghdr
import logging
import torch
import tempfile
import subprocess
from typing import Dict, Any, Optional, List, Tuple
from werkzeug.utils import secure_filename
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
import requests
from bs4 import BeautifulSoup

class SecurityManager:
    """Simple security manager for path operations"""
    
    def secure_path(self, directory: str, filename: str) -> Tuple[bool, str]:
        """
        Ensure the path is secure and doesn't contain path traversal attempts
        
        Args:
            directory: Base directory
            filename: Filename to validate
            
        Returns:
            Tuple of (is_secure, full_path)
        """
        # Security check: normalize path and ensure it doesn't escape the directory
        filename = secure_filename(filename)
        full_path = os.path.normpath(os.path.join(directory, filename))
        
        # Check if the normalized path is still under the directory
        if not full_path.startswith(os.path.abspath(directory) + os.sep):
            return False, ""
            
        return True, full_path

class MediaService:
    """Service for handling media uploads and processing"""
    
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger("media_service")
        self.config = config
        self.security_manager = SecurityManager()
        self.uploads_dir = config.get("UPLOADS_DIR", "data/uploads")
        self.models_dir = config.get("MODELS_DIR", "data/models")
        
        # Ensure directories exist
        os.makedirs(self.uploads_dir, exist_ok=True)
        os.makedirs(self.models_dir, exist_ok=True)
        
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
            
    def save_model(self, openscad_code: str, user_id: str, model_name: str = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Save OpenSCAD model code and generate a preview
        
        Args:
            openscad_code: The OpenSCAD code
            user_id: ID of the user saving the model
            model_name: Optional name for the model
            
        Returns:
            Tuple of (success, result_data)
        """
        try:
            # Create user model directory if it doesn't exist
            user_dir = os.path.join(self.models_dir, user_id)
            os.makedirs(user_dir, exist_ok=True)
            
            # Generate a unique model ID if name not provided
            if not model_name:
                model_name = f"model_{uuid.uuid4().hex[:8]}"
            else:
                model_name = secure_filename(model_name)
                
            # Ensure the model name has a .scad extension
            if not model_name.endswith('.scad'):
                model_name += '.scad'
                
            # Create a secure path
            is_secure, model_path = self.security_manager.secure_path(user_dir, model_name)
            
            if not is_secure:
                return False, {"error": "Security error: Invalid model path"}
                
            # Save the OpenSCAD code
            with open(model_path, 'w') as f:
                f.write(openscad_code)
                
            # Generate preview image if OpenSCAD is available
            preview_path = model_path.replace('.scad', '.png')
            preview_generated = self._generate_preview(model_path, preview_path)
            
            # Generate STL file if OpenSCAD is available
            stl_path = model_path.replace('.scad', '.stl')
            stl_generated = self._generate_stl(model_path, stl_path)
            
            self.logger.info(f"Model saved: {model_path}")
            
            return True, {
                "model_id": os.path.basename(model_path),
                "model_path": model_path,
                "preview_path": preview_path if preview_generated else None,
                "stl_path": stl_path if stl_generated else None,
                "code": openscad_code
            }
            
        except Exception as e:
            self.logger.error(f"Error saving model: {str(e)}")
            return False, {"error": str(e)}
            
    def get_user_models(self, user_id: str) -> Dict[str, Any]:
        """Get list of models created by a user"""
        try:
            user_dir = os.path.join(self.models_dir, user_id)
            
            if not os.path.exists(user_dir):
                return {"models": []}
                
            models = []
            for filename in os.listdir(user_dir):
                if filename.endswith('.scad'):
                    file_path = os.path.join(user_dir, filename)
                    if os.path.isfile(file_path):
                        file_stats = os.stat(file_path)
                        
                        # Check for preview image
                        preview_path = file_path.replace('.scad', '.png')
                        has_preview = os.path.isfile(preview_path)
                        
                        # Check for STL file
                        stl_path = file_path.replace('.scad', '.stl')
                        has_stl = os.path.isfile(stl_path)
                        
                        models.append({
                            "model_id": filename,
                            "model_path": file_path,
                            "preview_path": preview_path if has_preview else None,
                            "stl_path": stl_path if has_stl else None,
                            "created_at": file_stats.st_mtime
                        })
            
            return {"models": models}
            
        except Exception as e:
            self.logger.error(f"Error getting user models: {str(e)}")
            return {"error": str(e), "models": []}
            
    def _generate_preview(self, scad_path: str, output_path: str) -> bool:
        """Generate a preview image of a SCAD model using OpenSCAD"""
        try:
            # Check if OpenSCAD is installed
            openscad_bin = self._find_openscad_binary()
            if not openscad_bin:
                self.logger.warning("OpenSCAD not found, skipping preview generation")
                return False
                
            # Generate the preview
            cmd = [
                openscad_bin,
                "-o", output_path,
                "--camera=0,0,0,55,0,25,100",
                "--colorscheme=Tomorrow Night",
                "--imgsize=800,600",
                scad_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"Error generating preview: {result.stderr}")
                return False
                
            return os.path.exists(output_path)
            
        except Exception as e:
            self.logger.error(f"Error generating preview: {str(e)}")
            return False
            
    def _generate_stl(self, scad_path: str, output_path: str) -> bool:
        """Generate an STL file from a SCAD model using OpenSCAD"""
        try:
            # Check if OpenSCAD is installed
            openscad_bin = self._find_openscad_binary()
            if not openscad_bin:
                self.logger.warning("OpenSCAD not found, skipping STL generation")
                return False
                
            # Generate the STL
            cmd = [
                openscad_bin,
                "-o", output_path,
                scad_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"Error generating STL: {result.stderr}")
                return False
                
            return os.path.exists(output_path)
            
        except Exception as e:
            self.logger.error(f"Error generating STL: {str(e)}")
            return False
            
    def _find_openscad_binary(self) -> Optional[str]:
        """Find the OpenSCAD binary path"""
        # Check common locations
        common_paths = [
            "/usr/bin/openscad",
            "/usr/local/bin/openscad",
            "C:\\Program Files\\OpenSCAD\\openscad.exe",
            "C:\\Program Files (x86)\\OpenSCAD\\openscad.exe"
        ]
        
        for path in common_paths:
            if os.path.isfile(path):
                return path
                
        # Try to find in PATH
        try:
            result = subprocess.run(["which", "openscad"], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
            
        return None

class WebCrawler:
    """Simple web crawler to search for OpenSCAD templates and parameters online"""
    
    def __init__(self):
        self.logger = logging.getLogger("web_crawler")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        # Known OpenSCAD template repositories
        self.template_sites = [
            "https://www.openscad.org/documentation.html",
            "https://github.com/openscad/MCAD",
            "https://www.thingiverse.com/search?q=openscad",
            "https://www.printables.com/search/models?q=openscad"
        ]
        # Cache for templates
        self.template_cache = {}
        
    def search_for_template(self, query: str) -> Dict[str, Any]:
        """
        Search for OpenSCAD templates online based on query
        
        Args:
            query: Search query for template
            
        Returns:
            Dictionary with template code and source information
        """
        self.logger.info(f"Searching for OpenSCAD template: {query}")
        
        # Check cache first
        cache_key = query.lower().strip()
        if cache_key in self.template_cache:
            self.logger.info(f"Template found in cache for: {query}")
            return self.template_cache[cache_key]
        
        # Try to find template through search engines
        try:
            # First try a general search
            search_query = f"openscad {query} template code example"
            results = self._search_web(search_query)
            
            if results:
                # Extract code from search results
                for result in results[:3]:  # Try top 3 results
                    url = result.get("url", "")
                    if url:
                        code = self._extract_code_from_page(url, query)
                        if code:
                            template_data = {
                                "code": code,
                                "source": url,
                                "parameters": self._extract_parameters(code)
                            }
                            # Cache the result
                            self.template_cache[cache_key] = template_data
                            return template_data
            
            # If no results from search, try the known template sites
            for site in self.template_sites:
                code = self._extract_code_from_page(site, query)
                if code:
                    template_data = {
                        "code": code,
                        "source": site,
                        "parameters": self._extract_parameters(code)
                    }
                    # Cache the result
                    self.template_cache[cache_key] = template_data
                    return template_data
                    
            # No template found
            self.logger.warning(f"No template found for: {query}")
            return {"code": "", "source": "", "parameters": {}}
            
        except Exception as e:
            self.logger.error(f"Error searching for template: {str(e)}")
            return {"code": "", "source": "", "parameters": {}}
    
    def _search_web(self, query: str) -> List[Dict[str, str]]:
        """
        Use a search engine API to find relevant pages
        """
        try:
            # Using SerpAPI or similar search API (you need to set up API key in environment vars)
            api_key = os.environ.get("SERP_API_KEY", "")
            
            # If API key is provided, use SerpAPI
            if api_key:
                search_url = "https://serpapi.com/search"
                params = {
                    "q": query,
                    "api_key": api_key,
                    "engine": "google"
                }
                
                response = requests.get(search_url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    organic_results = data.get("organic_results", [])
                    return organic_results
            
            # Fallback to a basic search for OpenSCAD examples
            self.logger.warning("No SerpAPI key provided or API error, using fallback search results")
            return [
                {"title": "OpenSCAD Examples", "url": "https://www.openscad.org/examples.html"},
                {"title": "OpenSCAD Cheatsheet", "url": "https://www.openscad.org/cheatsheet/"},
                {"title": "OpenSCAD User Manual", "url": "https://en.wikibooks.org/wiki/OpenSCAD_User_Manual"}
            ]
            
        except Exception as e:
            self.logger.error(f"Error in web search: {str(e)}")
            return []
    
    def _extract_code_from_page(self, url: str, query: str) -> str:
        """
        Retrieve a page and extract OpenSCAD code from it
        """
        try:
            # Make request to URL
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                return ""
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for code blocks
            code_blocks = soup.select('pre, code')
            
            # Check each code block for OpenSCAD code
            for block in code_blocks:
                code_text = block.get_text()
                
                # Check if it contains OpenSCAD keywords
                if self._is_openscad_code(code_text):
                    # Check if the code relates to the query
                    if self._code_matches_query(code_text, query):
                        return code_text.strip()
            
            return ""
            
        except Exception as e:
            self.logger.error(f"Error extracting code from {url}: {str(e)}")
            return ""
    
    def _is_openscad_code(self, text: str) -> bool:
        """Check if text contains OpenSCAD code by looking for typical keywords"""
        openscad_keywords = [
            "module", "function", "cube", "sphere", "cylinder", 
            "polyhedron", "union", "difference", "intersection"
        ]
        
        text_lower = text.lower()
        # Check for presence of OpenSCAD keywords
        keyword_count = sum(1 for keyword in openscad_keywords if keyword in text_lower)
        
        # Check for OpenSCAD syntax patterns
        has_syntax = (
            re.search(r'module\s+\w+\s*\(', text) or
            re.search(r'function\s+\w+\s*\(', text) or
            re.search(r'cube\s*\(\s*\[', text) or
            re.search(r'sphere\s*\(\s*r\s*=', text) or
            re.search(r'cylinder\s*\(\s*h\s*=', text)
        )
        
        return keyword_count >= 2 or has_syntax
    
    def _code_matches_query(self, code: str, query: str) -> bool:
        """Check if code matches the search query"""
        # Split query into keywords
        keywords = query.lower().split()
        code_lower = code.lower()
        
        # Check if the code contains all the keywords
        matches = [keyword for keyword in keywords if keyword in code_lower]
        
        # If more than half the keywords match, consider it relevant
        return len(matches) >= len(keywords) / 2
    
    def _extract_parameters(self, code: str) -> Dict[str, Any]:
        """
        Extract parameter names and default values from OpenSCAD code
        """
        parameters = {}
        
        # Look for variable assignments
        var_pattern = r'(\w+)\s*=\s*([^;]+);'
        for match in re.finditer(var_pattern, code):
            param_name = match.group(1)
            param_value = match.group(2).strip()
            
            # Skip variables that look like internal calculations
            if param_name in ['i', 'j', 'x', 'y', 'z', 'temp', 'tmp', 'result']:
                continue
                
            # Try to determine parameter type
            param_type = "number"  # Default type
            if param_value.lower() in ['true', 'false']:
                param_type = "boolean"
            elif param_value.startswith('"') or param_value.startswith("'"):
                param_type = "string"
            elif "[" in param_value:
                param_type = "array"
            
            parameters[param_name] = {
                "default": param_value,
                "type": param_type
            }
        
        # Look for module parameters
        module_pattern = r'module\s+\w+\s*\((.*?)\)'
        for match in re.finditer(module_pattern, code, re.DOTALL):
            params_str = match.group(1).strip()
            if not params_str:
                continue
                
            # Split by commas, but handle default values
            param_items = []
            current_item = ""
            parenthesis_level = 0
            
            for char in params_str:
                if char == '(' or char == '[':
                    parenthesis_level += 1
                    current_item += char
                elif char == ')' or char == ']':
                    parenthesis_level -= 1
                    current_item += char
                elif char == ',' and parenthesis_level == 0:
                    param_items.append(current_item.strip())
                    current_item = ""
                else:
                    current_item += char
                    
            if current_item:
                param_items.append(current_item.strip())
                
            # Process each parameter
            for param in param_items:
                parts = param.split('=', 1)
                param_name = parts[0].strip()
                
                # Skip empty names
                if not param_name:
                    continue
                    
                # Extract default value if present
                if len(parts) > 1:
                    param_value = parts[1].strip()
                    
                    # Determine parameter type
                    param_type = "number"  # Default type
                    if param_value.lower() in ['true', 'false']:
                        param_type = "boolean"
                    elif param_value.startswith('"') or param_value.startswith("'"):
                        param_type = "string"
                    elif "[" in param_value:
                        param_type = "array"
                        
                    parameters[param_name] = {
                        "default": param_value,
                        "type": param_type
                    }
                else:
                    # No default value
                    parameters[param_name] = {
                        "default": "",
                        "type": "unknown"
                    }
        
        return parameters


class LLMService:
    """Service for generating OpenSCAD code and providing customer support using Mistral"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.logger = logging.getLogger("llm_service")
        
        if config is None:
            config = {}
            
        # Model configuration - can be set in environment variables or config
        self.model_name = config.get("MODEL_NAME", os.environ.get("MISTRAL_MODEL_NAME", "D:/mistral"))
        self.tokenizer_name = config.get("TOKENIZER_NAME", os.environ.get("MISTRAL_TOKENIZER_NAME", self.model_name))
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.max_length = int(config.get("MAX_LENGTH", os.environ.get("MISTRAL_MAX_LENGTH", "1024")))
        self.load_8bit = config.get("LOAD_8BIT", os.environ.get("MISTRAL_LOAD_8BIT", "True").lower() == "true")
        
        # Enhanced GPU configuration
        if self.device == "cuda":
            # Memory optimization for GPU
            torch.cuda.empty_cache()
            # Check for half-precision support
            self.use_half_precision = torch.cuda.is_available() and torch.cuda.get_device_capability()[0] >= 7
            self.logger.info(f"Using GPU with {'half' if self.use_half_precision else 'full'} precision")
        else:
            self.use_half_precision = False
            self.logger.info("Using CPU")
        
        # Create web crawler
        self.web_crawler = WebCrawler()
        
        # Initialize media service for handling files and 3D model generation
        self.media_service = MediaService(config)
        
        # Load model and tokenizer
        self._load_model()
        
        # Personas
        self.customer_service_persona = """
        You are a helpful customer support assistant for a 3D model generation service named '3D Model Generator'.
        Your goal is to help users understand how to use the service, explain features, and guide them through
        any issues they might encounter.
        
        Key features of the service:
        1. Generate 3D models using OpenSCAD code
        2. Convert images to 3D models using AI
        3. Download models in various formats (STL, OBJ)
        4. Token-based system for model generation
        
        When a user wants to create a 3D model, ask them specific questions about what they want to create, 
        including dimensions and other parameters that would be needed to generate the model.
        
        Be polite, concise, and helpful. If you don't know an answer, don't make things up.
        Always maintain a professional but friendly tone.
        """
        
        self.openscad_coder_persona = """
        You are an expert in OpenSCAD programming. Your task is to create detailed and well-commented OpenSCAD code
        based on user requirements. You follow best practices and create parametric designs whenever possible.
        
        OpenSCAD is a programming language for creating solid 3D CAD models. It uses a declarative approach
        where you describe the 3D object you want to create, rather than describing the steps to create it.
        
        Follow these guidelines:
        1. Always include clear comments in your code
        2. Use variables for all key parameters
        3. Create modular designs with reusable modules
        4. Include sensible default values for parameters
        5. Return only the OpenSCAD code without explanations or markdown
        """
        
        # User state for tracking conversations
        self.user_states = {}
        
        # Load fallback templates in case model fails
        self.templates = {
            "cube": "cube([${width}, ${height}, ${depth}]);",
            "sphere": "sphere(r=${radius});",
            "cylinder": "cylinder(h=${height}, r=${radius});"
        }
    
    def _load_model(self):
        """Load the Mistral model from Hugging Face with GPU optimization"""
        try:
            self.logger.info(f"Loading Mistral model from {self.model_name} on {self.device}")
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.tokenizer_name)
            
            # Load model with appropriate quantization and precision
            model_kwargs = {}
            if self.device == "cuda":
                if self.load_8bit:
                    model_kwargs["load_in_8bit"] = True
                    self.logger.info("Using 8-bit quantization")
                elif self.use_half_precision:
                    model_kwargs["torch_dtype"] = torch.float16
                    self.logger.info("Using half precision (float16)")
            
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                device_map="auto" if self.device == "cuda" else None,
                **model_kwargs
            )
            
            # Create pipeline for easier inference
            self.text_generator = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device_map="auto" if self.device == "cuda" else -1
            )
            
            self.logger.info("Mistral model loaded successfully")
            self.model_loaded = True
            
        except Exception as e:
            self.logger.error(f"Error loading Mistral model: {str(e)}")
            self.model_loaded = False
            raise
    
    def generate_code(self, prompt: str, parameters: Dict[str, Any] = None, user_id: str = None) -> Dict[str, Any]:
        """
        Generate OpenSCAD code based on a prompt using Mistral and web search
        
        Args:
            prompt: The prompt describing what to generate
            parameters: User-provided parameters to customize the model
            user_id: Optional user ID for saving the model
            
        Returns:
            Dictionary with code, source, parameters, and model paths
        """
        self.logger.info(f"Generating OpenSCAD code for: {prompt}")
        
        try:
            # First search for templates online
            template_result = self.web_crawler.search_for_template(prompt)
            
            # If template found, use it as base and apply parameters
            if template_result["code"]:
                self.logger.info(f"Found template from: {template_result['source']}")
                
                if parameters:
                    # Apply user parameters to the template
                    code = self._apply_parameters(template_result["code"], parameters)
                    result = {
                        "code": code,
                        "source": template_result["source"],
                        "parameters": template_result["parameters"]
                    }
                else:
                    # Return the template as is
                    result = template_result
            
            # If no template found or failed, use Mistral to generate code
            elif not self.model_loaded:
                fallback_code = self._fallback_generation(prompt, parameters)
                result = {
                    "code": fallback_code,
                    "source": "Generated by fallback system",
                    "parameters": self.web_crawler._extract_parameters(fallback_code)
                }
            else:
                # Create a properly formatted prompt for code generation
                formatted_prompt = self._format_prompt_for_instruct(
                    self.openscad_coder_persona,
                    f"Create OpenSCAD code for: {prompt}"
                )
                
                # Generate the response
                response = self._generate_text(formatted_prompt)
                
                # Extract only the code (remove any markdown code blocks or explanations)
                code = self._extract_code(response)
                
                if code.strip():
                    # Apply parameters if any
                    if parameters:
                        code = self._apply_parameters(code, parameters)
                        
                    extracted_params = self.web_crawler._extract_parameters(code)
                    result = {
                        "code": code,
                        "source": "Generated by Mistral",
                        "parameters": extracted_params
                    }
                else:
                    # Fall back to template-based generation if model output is empty or invalid
                    fallback_code = self._fallback_generation(prompt, parameters)
                    result = {
                        "code": fallback_code,
                        "source": "Generated by fallback system",
                        "parameters": self.web_crawler._extract_parameters(fallback_code)
                    }
            
            # Save the model if user_id is provided
            if user_id and result["code"]:
                # Generate model name from prompt
                model_name = self._generate_model_name(prompt)
                
                # Save model and generate previews
                success, model_data = self.media_service.save_model(
                    result["code"],
                    user_id,
                    model_name
                )
                
                if success:
                    result.update({
                        "model_id": model_data.get("model_id"),
                        "model_path": model_data.get("model_path"),
                        "preview_path": model_data.get("preview_path"),
                        "stl_path": model_data.get("stl_path")
                    })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error generating OpenSCAD code: {str(e)}")
            fallback_code = self._fallback_generation(prompt, parameters)
            return {
                "code": fallback_code,
                "source": "Generated by fallback system due to error",
                "parameters": self.web_crawler._extract_parameters(fallback_code)
            }
    
    def chat_with_customer(self, user_id: str, user_message: str) -> Dict[str, Any]:
        """
        Generate a response to a customer query using Mistral, and handle modeling requests
        
        Args:
            user_id: Unique identifier for the user
            user_message: The customer's message
            
        Returns:
            Response dictionary with text and any additional data like code
        """
        # Initialize user state if needed
        if user_id not in self.user_states:
            self.user_states[user_id] = {
                "chat_history": [],
                "current_state": "general",  # Can be "general", "collecting_parameters", "generating"
                "current_model": None,
                "parameters_needed": {},
                "parameters_collected": {}
            }
            
        user_state = self.user_states[user_id]
        chat_history = user_state["chat_history"]
        
        # Add user message to history
        chat_history.append({"role": "user", "content": user_message})
            
        try:
            if not self.model_loaded:
                response = "I'm sorry, but the service is currently unavailable. Please try again later."
                chat_history.append({"role": "assistant", "content": response})
                return {"text": response}
            
            # Check if user is asking to create a 3D model
            if user_state["current_state"] == "general" and self._is_model_request(user_message):
                # Start collecting parameters
                model_info = self._parse_model_request(user_message)
                user_state["current_model"] = model_info["type"]
                
                # Search for template
                template_result = self.web_crawler.search_for_template(model_info["type"])
                
                if template_result["code"]:
                    user_state["parameters_needed"] = template_result["parameters"]
                else:
                    # Use fallback parameters if no template found
                    user_state["parameters_needed"] = self._get_fallback_parameters(model_info["type"])
                
                # Initialize collected parameters with any values from the initial request
                user_state["parameters_collected"] = model_info["parameters"]
                
                # Check if we need more parameters
                missing_params = self._get_missing_parameters(
                    user_state["parameters_needed"], 
                    user_state["parameters_collected"]
                )
                
                if missing_params:
                    # Need to collect more parameters
                    user_state["current_state"] = "collecting_parameters"
                    response = self._create_parameter_request(missing_params, user_state["current_model"])
                else:
                    # All parameters are provided, generate the model
                    user_state["current_state"] = "generating"
                    result = self.generate_code(
                        user_state["current_model"], 
                        user_state["parameters_collected"],
                        user_id
                    )
                    
                    response = "Here's your OpenSCAD model! You can copy this code into OpenSCAD to view and customize it further."
                    chat_history.append({"role": "assistant", "content": response})
                    
                    # Reset state
                    user_state["current_state"] = "general"
                    
                    return {
                        "text": response,
                        "code": result["code"],
                        "source": result["source"],
                        "parameters": result["parameters"],
                        "preview_path": result.get("preview_path"),
                        "model_id": result.get("model_id")
                    }
                
            # Check if user is providing parameters
            elif user_state["current_state"] == "collecting_parameters":
                # Extract parameters from user message
                new_parameters = self._extract_parameters_from_message(
                    user_message, 
                    user_state["parameters_needed"]
                )
                
                # Update collected parameters
                user_state["parameters_collected"].update(new_parameters)
                
                # Check if we still need more parameters
                missing_params = self._get_missing_parameters(
                    user_state["parameters_needed"], 
                    user_state["parameters_collected"]
                )
                
                if missing_params:
                    # Still need more parameters
                    response = self._create_parameter_request(missing_params, user_state["current_model"])
                else:
                    # All parameters are provided, generate the model
                    user_state["current_state"] = "generating"
                    result = self.generate_code(
                        user_state["current_model"], 
                        user_state["parameters_collected"],
                        user_id
                    )
                    
                    response = "Here's your OpenSCAD model! You can copy this code into OpenSCAD to view and customize it further."
                    chat_history.append({"role": "assistant", "content": response})
                    
                    # Reset state
                    user_state["current_state"] = "general"
                    
                    return {
                        "text": response,
                        "code": result["code"],
                        "source": result["source"],
                        "parameters": result["parameters"],
                        "preview_path": result.get("preview_path"),
                        "model_id": result.get("model_id")
                    }
            
            else:
                # General conversation - use LLM to generate response
                # Format chat history as a string
                history_text = ""
                for message in chat_history[-5:]:  # Only include the last 5 messages for context
                    role = message.get("role", "user").upper()
                    content = message.get("content", "")
                    history_text += f"{role}: {content}\n\n"
                
                # Create a properly formatted prompt
                if history_text:
                    formatted_prompt = self._format_prompt_for_instruct(
                        self.customer_service_persona,
                        f"Chat history:\n{history_text}"
                    )
                else:
                    formatted_prompt = self._format_prompt_for_instruct(
                        self.customer_service_persona,
                        f"USER: {user_message}"
                    )
                
                # Generate the response
                response = self._generate_text(formatted_prompt)
                
                # Clean up the response (remove any trailing agent identifiers like "ASSISTANT:")
                response = re.sub(r"^ASSISTANT:\s*", "", response).strip()
            
            # Add assistant response to history
            chat_history.append({"role": "assistant", "content": response})
            return {"text": response}
            
        except Exception as e:
            self.logger.error(f"Error in chat response: {str(e)}")
            response = "I'm sorry, I'm experiencing technical difficulties. Please try again later."
            chat_history.append({"role": "assistant", "content": response})
            return {"text": response}
    
    def _generate_model_name(self, prompt: str) -> str:
        """Generate a model name from a prompt"""
        # Extract key words from the prompt
        words = re.findall(r'\b\w+\b', prompt.lower())
        
        # Filter out common words
        common_words = {'a', 'an', 'the', 'and', 'or', 'but', 'for', 'with', 'without', 'of', 'in', 'on', 'at', 'to', 'create', 'make', 'generate', 'model'}
        filtered_words = [word for word in words if word not in common_words and len(word) > 2]
        
        # If no meaningful words found, use a generic name
        if not filtered_words:
            return f"model_{uuid.uuid4().hex[:6]}"
            
        # Use the first 2-3 meaningful words
        name_words = filtered_words[:min(3, len(filtered_words))]
        model_name = '_'.join(name_words)
        
        # Add a timestamp to ensure uniqueness
        return f"{model_name}_{uuid.uuid4().hex[:6]}"
    
    def _is_model_request(self, message: str) -> bool:
        """Check if a message is requesting to create a 3D model"""
        # Keywords that suggest a 3D model request
        model_keywords = [
            "create", "generate", "make", "build", "design", "model",
            "3d model", "3d object", "3d print", "openscad"
        ]
        
        # Objects that can be modeled
        object_keywords = [
            "cube", "box", "sphere", "ball", "cylinder", "tube", "cone",
            "pyramid", "object", "shape", "gear", "bracket", "holder",
            "stand", "case", "container", "part"
        ]
        
        message_lower = message.lower()
        
        # Check for model request keywords
        has_model_keyword = any(keyword in message_lower for keyword in model_keywords)
        
        # Check for object keywords
        has_object_keyword = any(keyword in message_lower for keyword in object_keywords)
        
        return has_model_keyword and has_object_keyword
    
    def _parse_model_request(self, message: str) -> Dict[str, Any]:
        """
        Parse a model request to identify the type of model and any parameters
        
        Returns a dictionary with model type and parameters
        """
        message_lower = message.lower()
        
        # Try to identify model type
        model_type = "cube"  # Default
        
        if "sphere" in message_lower or "ball" in message_lower:
            model_type = "sphere"
        elif "cylinder" in message_lower or "tube" in message_lower:
            model_type = "cylinder"
        elif "cone" in message_lower:
            model_type = "cone"
        elif "pyramid" in message_lower:
            model_type = "pyramid"
        elif "gear" in message_lower:
            model_type = "gear"
        elif "box" in message_lower or "cube" in message_lower:
            model_type = "cube"
            
        # Extract any parameters mentioned in the message
        parameters = {}
        
        # Look for dimensions
        width_match = re.search(r'width(?:\s+of)?\s+(\d+\.?\d*)', message_lower)
        if width_match:
            parameters["width"] = float(width_match.group(1))
            
        height_match = re.search(r'height(?:\s+of)?\s+(\d+\.?\d*)', message_lower)
        if height_match:
            parameters["height"] = float(height_match.group(1))
            
        depth_match = re.search(r'depth(?:\s+of)?\s+(\d+\.?\d*)', message_lower)
        if depth_match:
            parameters["depth"] = float(depth_match.group(1))
            
        radius_match = re.search(r'radius(?:\s+of)?\s+(\d+\.?\d*)', message_lower)
        if radius_match:
            parameters["radius"] = float(radius_match.group(1))
            
        diameter_match = re.search(r'diameter(?:\s+of)?\s+(\d+\.?\d*)', message_lower)
        if diameter_match:
            parameters["radius"] = float(diameter_match.group(1)) / 2
        
        # Extract any measurements with units
        units_patterns = [
            (r'(\d+\.?\d*)\s*mm', 1.0),  # millimeters (default)
            (r'(\d+\.?\d*)\s*cm', 10.0),  # centimeters to mm
            (r'(\d+\.?\d*)\s*m', 1000.0),  # meters to mm
            (r'(\d+\.?\d*)\s*in', 25.4),  # inches to mm
        ]
        
        for pattern, factor in units_patterns:
            for match in re.finditer(pattern, message_lower):
                value = float(match.group(1)) * factor
                
                # Try to determine which dimension this measurement applies to
                context = message_lower[max(0, match.start() - 20):match.start()]
                
                if "width" in context or "wide" in context:
                    parameters["width"] = value
                elif "height" in context or "high" in context or "tall" in context:
                    parameters["height"] = value
                elif "depth" in context or "deep" in context:
                    parameters["depth"] = value
                elif "radius" in context:
                    parameters["radius"] = value
                elif "diameter" in context:
                    parameters["radius"] = value / 2
        
        return {
            "type": model_type,
            "parameters": parameters
        }
    
    def _get_fallback_parameters(self, model_type: str) -> Dict[str, Any]:
        """Get fallback parameters needed for a specific model type"""
        if model_type == "cube" or model_type == "box":
            return {
                "width": {"default": "10", "type": "number"},
                "height": {"default": "10", "type": "number"},
                "depth": {"default": "10", "type": "number"}
            }
        elif model_type == "sphere" or model_type == "ball":
            return {
                "radius": {"default": "10", "type": "number"}
            }
        elif model_type == "cylinder" or model_type == "tube":
            return {
                "radius": {"default": "5", "type": "number"},
                "height": {"default": "20", "type": "number"}
            }
        elif model_type == "cone":
            return {
                "radius1": {"default": "10", "type": "number"},
                "radius2": {"default": "0", "type": "number"},
                "height": {"default": "20", "type": "number"}
            }
        else:
            # Generic parameters
            return {
                "size": {"default": "10", "type": "number"}
            }
    
    def _get_missing_parameters(self, needed: Dict[str, Any], collected: Dict[str, Any]) -> Dict[str, Any]:
        """Get parameters that are still needed from the user"""
        missing = {}
        
        for param_name, param_info in needed.items():
            if param_name not in collected:
                missing[param_name] = param_info
                
        return missing
    
    def _create_parameter_request(self, missing_params: Dict[str, Any], model_type: str) -> str:
        """Create a message asking the user for missing parameters"""
        if not missing_params:
            return "I have all the information I need to create your 3D model."
            
        # Create a friendly message asking for parameters
        message = f"To create your {model_type}, I need a few more details.\n\n"
        
        # Ask for each missing parameter
        for param_name, param_info in missing_params.items():
            default = param_info.get("default", "")
            
            if param_name == "width":
                message += f"- What width would you like? (default is {default})\n"
            elif param_name == "height":
                message += f"- What height would you like? (default is {default})\n"
            elif param_name == "depth":
                message += f"- What depth would you like? (default is {default})\n"
            elif param_name == "radius":
                message += f"- What radius would you like? (default is {default})\n"
            elif param_name == "radius1":
                message += f"- What base radius would you like? (default is {default})\n"
            elif param_name == "radius2":
                message += f"- What top radius would you like? (default is {default})\n"
            else:
                message += f"- What {param_name} would you like? (default is {default})\n"
                
        message += "\nYou can specify these all at once or one at a time. Or just say 'use defaults' to use the default values."
        
        return message
    
    def _extract_parameters_from_message(self, message: str, needed_params: Dict[str, Any]) -> Dict[str, Any]:
        """Extract parameters from a user message"""
        parameters = {}
        message_lower = message.lower()
        
        # Check for "use defaults" message
        if "use default" in message_lower or "default" in message_lower:
            for param_name, param_info in needed_params.items():
                default_str = param_info.get("default", "")
                if default_str:
                    # Try to convert default to appropriate type
                    if param_info.get("type") == "number":
                        try:
                            parameters[param_name] = float(default_str)
                        except ValueError:
                            pass
                    elif param_info.get("type") == "boolean":
                        parameters[param_name] = default_str.lower() == "true"
                    else:
                        parameters[param_name] = default_str
                        
            return parameters
        
        # Extract numeric parameters with units
        units_patterns = [
            (r'(\d+\.?\d*)\s*mm', 1.0),  # millimeters (default)
            (r'(\d+\.?\d*)\s*cm', 10.0),  # centimeters to mm
            (r'(\d+\.?\d*)\s*m', 1000.0),  # meters to mm
            (r'(\d+\.?\d*)\s*in', 25.4),  # inches to mm
        ]
        
        # Look for parameter assignments like "width is 10" or "set height to 20"
        for param_name in needed_params.keys():
            # Different ways a parameter might be specified
            patterns = [
                rf'{param_name}\s+(?:is|should be|=)\s+(\d+\.?\d*)',
                rf'(?:set|make)\s+(?:the)?\s*{param_name}\s+(?:to|=)\s+(\d+\.?\d*)',
                rf'{param_name}:\s*(\d+\.?\d*)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, message_lower)
                if match:
                    value = float(match.group(1))
                    parameters[param_name] = value
                    break
        
        # Extract any measurements with units
        for pattern, factor in units_patterns:
            for match in re.finditer(pattern, message_lower):
                value = float(match.group(1)) * factor
                
                # Try to determine which dimension this measurement applies to
                context = message_lower[max(0, match.start() - 20):match.start()]
                
                if "width" in context or "wide" in context:
                    parameters["width"] = value
                elif "height" in context or "high" in context or "tall" in context:
                    parameters["height"] = value
                elif "depth" in context or "deep" in context:
                    parameters["depth"] = value
                elif "radius" in context:
                    parameters["radius"] = value
                elif "diameter" in context:
                    parameters["radius"] = value / 2
                elif "radius1" in context or "base radius" in context:
                    parameters["radius1"] = value
                elif "radius2" in context or "top radius" in context:
                    parameters["radius2"] = value
        
        return parameters
    
    def _apply_parameters(self, code: str, parameters: Dict[str, Any]) -> str:
        """Apply user parameters to OpenSCAD code"""
        modified_code = code
        
        # Replace parameter values in the code
        for param_name, param_value in parameters.items():
            # Look for variable assignments
            pattern = rf'({param_name}\s*=\s*)([^;]+)(;)'
            replacement = f"\\1{param_value}\\3"
            modified_code = re.sub(pattern, replacement, modified_code)
        
        return modified_code
    
    def _generate_text(self, prompt: str) -> str:
        """Generate text using the loaded model with GPU optimization"""
        try:
            # Set generation parameters
            gen_kwargs = {
                "max_new_tokens": self.max_length,
                "temperature": 0.7,
                "top_p": 0.9,
                "do_sample": True,
                "pad_token_id": self.tokenizer.eos_token_id
            }
            
            # Generate text
            outputs = self.text_generator(
                prompt,
                return_full_text=False,
                **gen_kwargs
            )
            
            # Extract the generated text
            generated_text = outputs[0]["generated_text"]
            return generated_text.strip()
            
        except Exception as e:
            self.logger.error(f"Error in text generation: {str(e)}")
            return ""
    
    def _format_prompt_for_instruct(self, system_prompt: str, user_prompt: str) -> str:
        """Format the prompt according to Mistral's expected instruction format"""
        # This is the format for Mistral-Instruct models
        return f"<s>[INST] {system_prompt}\n\n{user_prompt} [/INST]"
    
    def _extract_code(self, text: str) -> str:
        """Extract code from model output, removing any markdown or explanations"""
        # First try to extract code blocks
        code_block_pattern = r"```(?:openscad)?(.*?)```"
        code_blocks = re.findall(code_block_pattern, text, re.DOTALL)
        
        if code_blocks:
            # Join multiple code blocks if present
            return "\n\n".join(block.strip() for block in code_blocks)
        
        # If no code blocks, try to extract the entire response
        # Remove any explanations or anything that looks like natural language
        lines = text.split("\n")
        code_lines = []
        in_code = False
        
        for line in lines:
            # Skip lines that look like explanations
            if re.match(r"^(Here's|This|The|I've|I'll|I|As you|Now|Note:)", line):
                continue
                
            # Include line if it looks like code
            if "(" in line or ")" in line or "{" in line or "}" in line or "=" in line or "//" in line:
                in_code = True
                code_lines.append(line)
            elif in_code and line.strip():  # Continue including lines if we're in code mode
                code_lines.append(line)
        
        return "\n".join(code_lines).strip()
    
    def _fallback_generation(self, prompt: str, parameters: Dict[str, Any] = None) -> str:
        """Fallback to template-based generation if model fails"""
        self.logger.warning("Falling back to template-based generation")
        
        if parameters is None:
            parameters = {}
        
        if "cube" in prompt.lower() or "box" in prompt.lower():
            # Extract dimensions if mentioned
            width = parameters.get("width", 10)
            height = parameters.get("height", 10)
            depth = parameters.get("depth", 10)
            
            code = f"""
// Customizable Cube
// Generated by 3D Model Generator

// Parameters
width = {width};  // Width of the cube
height = {height};  // Height of the cube
depth = {depth};  // Depth of the cube

// Main module
module custom_cube(w, h, d) {{
    cube([w, h, d]);
}}

// Generate the cube
custom_cube(width, height, depth);
"""
            return code
            
        elif "sphere" in prompt.lower() or "ball" in prompt.lower():
            radius = parameters.get("radius", 10)
            
            code = f"""
// Customizable Sphere
// Generated by 3D Model Generator

// Parameters
radius = {radius};  // Radius of the sphere

// Main module
module custom_sphere(r) {{
    sphere(r=r);
}}

// Generate the sphere
custom_sphere(radius);
"""
            return code
            
        elif "cylinder" in prompt.lower() or "tube" in prompt.lower():
            height = parameters.get("height", 20)
            radius = parameters.get("radius", 5)
            
            code = f"""
// Customizable Cylinder
// Generated by 3D Model Generator

// Parameters
height = {height};  // Height of the cylinder
radius = {radius};  // Radius of the cylinder

// Main module
module custom_cylinder(h, r) {{
    cylinder(h=h, r=r);
}}

// Generate the cylinder
custom_cylinder(height, radius);
"""
            return code
            
        elif "cone" in prompt.lower():
            height = parameters.get("height", 20)
            radius1 = parameters.get("radius1", 10)
            radius2 = parameters.get("radius2", 0)
            
            code = f"""
// Customizable Cone
// Generated by 3D Model Generator

// Parameters
height = {height};  // Height of the cone
radius1 = {radius1};  // Radius of the base
radius2 = {radius2};  // Radius of the top (0 for a pointed cone)

// Main module
module custom_cone(h, r1, r2) {{
    cylinder(h=h, r1=r1, r2=r2);
}}

// Generate the cone
custom_cone(height, radius1, radius2);
"""
            return code
        
        else:
            # Default to a simple example
            size = parameters.get("size", 10)
            code = f"""
// Default 3D Model
// Generated by 3D Model Generator

// Parameters
size = {size};  // Size of the object

// Main module
module default_object(size) {{
    cube(size);
}}

// Generate the object
default_object(size);
"""
            return code