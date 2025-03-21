import os
import re
import logging
import torch
from typing import Dict, Any, Optional, List
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

class LLMService:
    """Service for generating OpenSCAD code and providing customer support using Mistral"""
    
    def __init__(self):
        self.logger = logging.getLogger("llm_service")
        
        # Model configuration - can be set in environment variables
        self.model_name = os.environ.get("MISTRAL_MODEL_NAME", "D:/mistral")
        self.tokenizer_name = os.environ.get("MISTRAL_TOKENIZER_NAME", self.model_name)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.max_length = int(os.environ.get("MISTRAL_MAX_LENGTH", "1024"))
        self.load_8bit = os.environ.get("MISTRAL_LOAD_8BIT", "True").lower() == "true"
        
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
        
        # Load fallback templates in case model fails
        self.templates = {
            "cube": "cube([${width}, ${height}, ${depth}]);",
            "sphere": "sphere(r=${radius});",
            "cylinder": "cylinder(h=${height}, r=${radius});"
        }
    
    def _load_model(self):
        """Load the Mistral model from Hugging Face"""
        try:
            self.logger.info(f"Loading Mistral model from {self.model_name} on {self.device}")
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.tokenizer_name)
            
            # Load model with appropriate quantization
            model_kwargs = {}
            if self.load_8bit and self.device == "cuda":
                model_kwargs["load_in_8bit"] = True
            
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
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
    
    def generate_code(self, prompt: str) -> str:
        """
        Generate OpenSCAD code based on a prompt using Mistral
        
        Args:
            prompt: The prompt describing what to generate
            
        Returns:
            OpenSCAD code as a string
        """
        self.logger.info("Generating OpenSCAD code with Mistral")
        
        try:
            if not self.model_loaded:
                return self._fallback_generation(prompt)
            
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
                return code
            
            # Fall back to template-based generation if model output is empty or invalid
            return self._fallback_generation(prompt)
            
        except Exception as e:
            self.logger.error(f"Error generating OpenSCAD code: {str(e)}")
            return self._fallback_generation(prompt)
    
    def chat_with_customer(self, user_message: str, chat_history: List[Dict[str, str]] = None) -> str:
        """
        Generate a response to a customer query using Mistral
        
        Args:
            user_message: The customer's message
            chat_history: Previous chat history as a list of message dictionaries with 'role' and 'content'
            
        Returns:
            Assistant's response as a string
        """
        if chat_history is None:
            chat_history = []
            
        try:
            if not self.model_loaded:
                return "I'm sorry, but the service is currently unavailable. Please try again later."
            
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
                    f"Chat history:\n{history_text}\nUSER: {user_message}"
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
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error in chat response: {str(e)}")
            return "I'm sorry, I'm experiencing technical difficulties. Please try again later."
    
    def _generate_text(self, prompt: str) -> str:
        """Generate text using the loaded model"""
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
    
    def _fallback_generation(self, prompt: str) -> str:
        """Fallback to template-based generation if model fails"""
        self.logger.warning("Falling back to template-based generation")
        
        if "cube" in prompt.lower():
            # Extract dimensions if mentioned
            width = self._extract_parameter(prompt, "width", 10)
            height = self._extract_parameter(prompt, "height", 10)
            depth = self._extract_parameter(prompt, "depth", 10)
            
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
            
        elif "sphere" in prompt.lower():
            radius = self._extract_parameter(prompt, "radius", 10)
            
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
            
        elif "cylinder" in prompt.lower():
            height = self._extract_parameter(prompt, "height", 20)
            radius = self._extract_parameter(prompt, "radius", 5)
            
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
        
        else:
            # Default to a simple example
            code = """
// Default 3D Model
// Generated by 3D Model Generator

// Parameters
size = 10;  // Size of the object

// Main module
module default_object(size) {
    cube(size);
}

// Generate the object
default_object(size);
"""
            return code
    
    def _extract_parameter(self, text: str, param_name: str, default_value: float) -> float:
        """Extract a parameter value from text"""
        pattern = rf'{param_name}\s*[=:]\s*(\d+\.?\d*)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return default_value
        return default_value