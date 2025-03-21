class ModelGenerator {
    constructor() {
        this.form = document.getElementById('model-form');
        this.modelTypeSelect = document.getElementById('model-type');
        this.parametersContainer = document.getElementById('parameters-container');
        this.modelResult = document.getElementById('model-result');
        this.modelViewer = document.getElementById('model-viewer');
        this.modelInfo = document.getElementById('model-info');
        
        this.csrfToken = document.querySelector('input[name="csrf_token"]')?.value || window.csrfToken || '';
        this.sessionId = null;
        
        this.initEventListeners();
    }
    
    initEventListeners() {
        // Initialize the form if it exists
        if (this.form) {
            this.form.addEventListener('submit', (e) => this.handleFormSubmit(e));
        }
        
        // Handle model type selection
        if (this.modelTypeSelect) {
            this.modelTypeSelect.addEventListener('change', () => this.updateParameterInputs());
        }
    }
    
    updateParameterInputs() {
        const modelType = this.modelTypeSelect.value;
        
        // Clear current parameters
        this.parametersContainer.innerHTML = '';
        
        if (!modelType) return;
        
        // Add default parameters based on model type
        if (modelType === 'openscad') {
            // Add inputs for basic parameters
            this.addParameterInput('width', 'Width', 'number', 10);
            this.addParameterInput('height', 'Height', 'number', 10);
            this.addParameterInput('depth', 'Depth', 'number', 10);
            
            // Add shape selector
            const shapeGroup = document.createElement('div');
            shapeGroup.className = 'form-group';
            
            const shapeLabel = document.createElement('label');
            shapeLabel.textContent = 'Shape:';
            shapeLabel.htmlFor = 'shape';
            
            const shapeSelect = document.createElement('select');
            shapeSelect.id = 'shape';
            shapeSelect.name = 'parameters[shape]';
            
            const shapes = [
                { value: 'cube', label: 'Cube' },
                { value: 'sphere', label: 'Sphere' },
                { value: 'cylinder', label: 'Cylinder' }
            ];
            
            // Add empty option
            const emptyOption = document.createElement('option');
            emptyOption.value = '';
            emptyOption.textContent = 'Select a shape';
            shapeSelect.appendChild(emptyOption);
            
            // Add shape options
            shapes.forEach(shape => {
                const option = document.createElement('option');
                option.value = shape.value;
                option.textContent = shape.label;
                shapeSelect.appendChild(option);
            });
            
            shapeGroup.appendChild(shapeLabel);
            shapeGroup.appendChild(shapeSelect);
            this.parametersContainer.appendChild(shapeGroup);
            
            // Add event listener to shape selector to update available parameters
            shapeSelect.addEventListener('change', () => {
                const shape = shapeSelect.value;
                
                // Remove shape-specific parameters
                const specificParams = document.querySelectorAll('.shape-specific');
                specificParams.forEach(param => param.remove());
                
                // Add shape-specific parameters
                if (shape === 'sphere') {
                    this.addParameterInput('radius', 'Radius', 'number', 10, true);
                } else if (shape === 'cylinder') {
                    this.addParameterInput('radius', 'Radius', 'number', 5, true);
                    this.addParameterInput('height', 'Height', 'number', 20, true);
                }
            });
        }
    }
    
    addParameterInput(name, label, type, defaultValue, isShapeSpecific = false) {
        const paramGroup = document.createElement('div');
        paramGroup.className = `form-group ${isShapeSpecific ? 'shape-specific' : ''}`;
        
        const paramLabel = document.createElement('label');
        paramLabel.textContent = label + ':';
        paramLabel.htmlFor = name;
        
        const paramInput = document.createElement('input');
        paramInput.type = type;
        paramInput.id = name;
        paramInput.name = `parameters[${name}]`;
        paramInput.value = defaultValue;
        
        paramGroup.appendChild(paramLabel);
        paramGroup.appendChild(paramInput);
        this.parametersContainer.appendChild(paramGroup);
    }
    
    async handleFormSubmit(e) {
        e.preventDefault();
        
        // Show loading indicator
        window.utils.showLoading(true);
        
        // Collect form data
        const formData = new FormData(this.form);
        const modelType = formData.get('model_type');
        
        // Collect parameters
        const parameters = {};
        for (const [key, value] of formData.entries()) {
            if (key.startsWith('parameters[') && key.endsWith(']')) {
                const paramName = key.substring(11, key.length - 1);
                parameters[paramName] = value;
            }
        }
        
        // Prepare request data
        const requestData = {
            model_type: modelType,
            parameters: parameters,
            csrf_token: this.csrfToken
        };
        
        if (this.sessionId) {
            requestData.session_id = this.sessionId;
        }
        
        try {
            // Send API request
            const response = await fetch('/api/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': this.csrfToken
                },
                body: JSON.stringify(requestData)
            });
            
            // Process response
            if (response.ok) {
                const data = await response.json();
                
                if (data.success) {
                    // Store session ID for future requests
                    this.sessionId = data.session_id;
                    
                    // Display the model
                    this.displayModel(data.model);
                } else {
                    window.utils.showError(data.error || 'Failed to generate model');
                }
            } else {
                const errorData = await response.json();
                window.utils.showError(errorData.error || 'Failed to generate model');
            }
        } catch (error) {
            console.error('Error generating model:', error);
            window.utils.showError('An error occurred while generating the model');
        } finally {
            window.utils.showLoading(false);
        }
    }
    
    displayModel(model) {
        // Show the result container
        this.modelResult.style.display = 'block';
        
        // Update model info
        this.modelInfo.innerHTML = `
            <h3>Model Details</h3>
            <p><strong>ID:</strong> ${window.utils.escapeHtml(model.model_id)}</p>
            <p><strong>Type:</strong> ${window.utils.escapeHtml(model.model_type)}</p>
            <div class="code-preview">
                <h4>Code Preview:</h4>
                <pre>${window.utils.escapeHtml(model.code_preview)}</pre>
            </div>
            <div class="actions">
                <button id="download-btn" class="secondary-btn">Download OpenSCAD File</button>
                <button id="view-code-btn" class="secondary-btn">View Full Code</button>
            </div>
        `;
        
        // Add event listeners to buttons
        const downloadBtn = document.getElementById('download-btn');
        if (downloadBtn) {
            downloadBtn.addEventListener('click', () => this.downloadModel(model.model_id));
        }
        
        const viewCodeBtn = document.getElementById('view-code-btn');
        if (viewCodeBtn) {
            viewCodeBtn.addEventListener('click', () => this.viewFullCode(model.model_id));
        }
        
        // For a simple preview, we'll just show a placeholder
        // In a real app, you would render the OpenSCAD model
        this.modelViewer.innerHTML = `
            <div class="placeholder-viewer">
                <div class="placeholder-text">3D Preview</div>
                <div class="placeholder-cube"></div>
            </div>
        `;
    }
    
    async downloadModel(modelId) {
        try {
            const response = await fetch(`/api/model/${modelId}`);
            
            if (response.ok) {
                const data = await response.json();
                
                if (data.success && data.model) {
                    // Create a blob from the code
                    const blob = new Blob([data.model.code], { type: 'text/plain' });
                    const url = URL.createObjectURL(blob);
                    
                    // Create a download link
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `model_${modelId}.scad`;
                    document.body.appendChild(a);
                    a.click();
                    
                    // Clean up
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                } else {
                    window.utils.showError(data.error || 'Failed to download model');
                }
            } else {
                const errorData = await response.json();
                window.utils.showError(errorData.error || 'Failed to download model');
            }
        } catch (error) {
            console.error('Error downloading model:', error);
            window.utils.showError('An error occurred while downloading the model');
        }
    }
    
    async viewFullCode(modelId) {
        try {
            const response = await fetch(`/api/model/${modelId}`);
            
            if (response.ok) {
                const data = await response.json();
                
                if (data.success && data.model) {
                    // Create a modal to display the code
                    const modal = document.createElement('div');
                    modal.className = 'modal';
                    modal.style.display = 'flex';
                    
                    modal.innerHTML = `
                        <div class="modal-content">
                            <span class="close-modal">&times;</span>
                            <h3>OpenSCAD Code</h3>
                            <div class="modal-body">
                                <pre style="white-space: pre-wrap; overflow-x: auto;">${window.utils.escapeHtml(data.model.code)}</pre>
                            </div>
                        </div>
                    `;
                    
                    document.body.appendChild(modal);
                    
                    // Add close functionality
                    const closeBtn = modal.querySelector('.close-modal');
                    closeBtn.addEventListener('click', () => {
                        document.body.removeChild(modal);
                    });
                    
                    modal.addEventListener('click', (e) => {
                        if (e.target === modal) {
                            document.body.removeChild(modal);
                        }
                    });
                } else {
                    window.utils.showError(data.error || 'Failed to retrieve model code');
                }
            } else {
                const errorData = await response.json();
                window.utils.showError(errorData.error || 'Failed to retrieve model code');
            }
        } catch (error) {
            console.error('Error retrieving model code:', error);
            window.utils.showError('An error occurred while retrieving the model code');
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.modelGenerator = new ModelGenerator();
});
