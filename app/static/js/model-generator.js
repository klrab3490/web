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
        
        // 3D renderer properties
        this.renderer = null;
        this.scene = null;
        this.camera = null;
        this.controls = null;
        this.modelMesh = null;
        this.rendererInitialized = false;
        
        // Current model data
        this.currentModelId = '';
        this.currentPreviewPath = '';
        this.currentStlPath = '';
        this.currentCode = '';
        this.currentParams = {};
        
        // Add tabs for 2D/3D view
        this.setupViewTabs();
        
        this.initEventListeners();
    }
    
    setupViewTabs() {
        // Create tabs if they don't exist
        if (!document.getElementById('tab-preview')) {
            const tabsHtml = `
                <div class="model-tabs">
                    <div class="model-tab active" id="tab-preview">Preview</div>
                    <div class="model-tab" id="tab-3d">3D View</div>
                </div>
            `;
            
            // Insert tabs before the viewer
            if (this.modelViewer) {
                this.modelViewer.insertAdjacentHTML('beforebegin', tabsHtml);
                
                // Set up event listeners for tabs
                document.getElementById('tab-preview').addEventListener('click', () => this.showPreviewTab());
                document.getElementById('tab-3d').addEventListener('click', () => this.show3DTab());
            }
        }
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
        
        // Handle window resize for 3D renderer
        window.addEventListener('resize', () => this.onWindowResize());
    }
    
    updateParameterInputs() {
        const modelType = this.modelTypeSelect.value;
        
        // Clear current parameters
        this.parametersContainer.innerHTML = '';
        
        if (!modelType) return;
        
        // Add default parameters based on model type
        if (modelType === 'openscad') {
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
                { value: 'cylinder', label: 'Cylinder' },
                { value: 'cone', label: 'Cone' },
                { value: 'pyramid', label: 'Pyramid' }
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
                
                // Add common parameters
                if (shape === 'cube' || shape === 'pyramid') {
                    this.addParameterInput('width', 'Width', 'number', 10, true);
                    this.addParameterInput('height', 'Height', 'number', 10, true);
                    this.addParameterInput('depth', 'Depth', 'number', 10, true);
                }
                
                // Add shape-specific parameters
                if (shape === 'sphere') {
                    this.addParameterInput('radius', 'Radius', 'number', 10, true);
                } else if (shape === 'cylinder' || shape === 'cone') {
                    this.addParameterInput('radius', 'Radius', 'number', 5, true);
                    this.addParameterInput('height', 'Height', 'number', 20, true);
                    
                    if (shape === 'cone') {
                        this.addParameterInput('top_radius', 'Top Radius', 'number', 0, true);
                    }
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
            csrf_token: this.csrfToken,
            user_id: this.getUserId()
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
                    
                    // Save model data
                    this.currentModelId = data.model?.model_id || '';
                    this.currentCode = data.model?.code || '';
                    this.currentParams = parameters;
                    
                    // Set preview and STL paths if available
                    if (data.model?.model_id) {
                        const userId = this.getUserId();
                        this.currentPreviewPath = `/preview/${userId}/${data.model.model_id}`;
                        this.currentStlPath = `/model/${userId}/${data.model.model_id.replace('.scad', '.stl')}`;
                    }
                    
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
    
    getUserId() {
        // Generate a unique user ID if not available
        if (!window.userId) {
            window.userId = 'user_' + Math.random().toString(36).substring(2, 15);
        }
        return window.userId;
    }
    
    displayModel(model) {
        // Show the result container
        this.modelResult.style.display = 'block';
        
        // Update model info
        this.modelInfo.innerHTML = `
            <h3>Model Details</h3>
            <p><strong>ID:</strong> ${window.utils.escapeHtml(model.model_id)}</p>
            <p><strong>Type:</strong> ${window.utils.escapeHtml(model.model_type)}</p>
            <div class="actions">
                <button id="download-stl-btn" class="secondary-btn">Download STL File</button>
                <button id="update-params-btn" class="secondary-btn">Update Parameters</button>
            </div>
        `;
        
        // Show parameter inputs for editing
        this.displayParameterInputs(this.currentParams);
        
        // Add event listeners to buttons
        const downloadStlBtn = document.getElementById('download-stl-btn');
        if (downloadStlBtn) {
            downloadStlBtn.addEventListener('click', () => this.downloadStl());
        }
        
        const updateParamsBtn = document.getElementById('update-params-btn');
        if (updateParamsBtn) {
            updateParamsBtn.addEventListener('click', () => this.updateModel());
        }
        
        // Show model preview
        if (this.currentPreviewPath) {
            this.showModelPreview(this.currentPreviewPath);
        } else {
            // For a simple preview, we'll just show a placeholder
            this.modelViewer.innerHTML = `
                <div class="placeholder-viewer">
                    <div class="placeholder-text">3D Preview</div>
                    <div class="placeholder-cube"></div>
                </div>
            `;
        }
    }
    
    displayParameterInputs(parameters) {
        if (!parameters) return;
        
        // Create or get parameters display area
        let parameterList = document.getElementById('parameter-list');
        if (!parameterList) {
            parameterList = document.createElement('div');
            parameterList.id = 'parameter-list';
            parameterList.className = 'parameter-list';
            this.modelInfo.appendChild(parameterList);
        } else {
            parameterList.innerHTML = '';
        }
        
        // Add parameter inputs
        for (const [name, value] of Object.entries(parameters)) {
            const paramItem = document.createElement('div');
            paramItem.className = 'parameter-item';
            
            const paramLabel = document.createElement('label');
            paramLabel.className = 'parameter-label';
            paramLabel.textContent = name;
            
            const paramInput = document.createElement('input');
            paramInput.className = 'parameter-input';
            paramInput.type = 'text';
            paramInput.name = name;
            paramInput.value = value;
            
            paramItem.appendChild(paramLabel);
            paramItem.appendChild(paramInput);
            parameterList.appendChild(paramItem);
        }
        
        // Add update button
        let updateButton = document.getElementById('update-model');
        if (!updateButton) {
            updateButton = document.createElement('button');
            updateButton.id = 'update-model';
            updateButton.textContent = 'Update Model';
            updateButton.className = 'secondary-btn';
            updateButton.addEventListener('click', () => this.updateModel());
            parameterList.parentNode.appendChild(updateButton);
        }
    }
    
    async updateModel() {
        // Get updated parameters
        const paramInputs = document.querySelectorAll('.parameter-input');
        const updatedParams = {};
        
        paramInputs.forEach(input => {
            updatedParams[input.name] = input.value;
        });
        
        // Show loading
        window.utils.showLoading(true);
        
        try {
            const response = await fetch('/api/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': this.csrfToken
                },
                body: JSON.stringify({
                    prompt: this.currentModelId || 'update model',
                    parameters: updatedParams,
                    user_id: this.getUserId(),
                    model_id: this.currentModelId
                })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to update model');
            }
            
            const data = await response.json();
            
            // Update current data
            this.currentParams = updatedParams;
            if (data.model_id) {
                this.currentModelId = data.model_id;
                const userId = this.getUserId();
                this.currentPreviewPath = `/preview/${userId}/${data.model_id}`;
                this.currentStlPath = `/model/${userId}/${data.model_id.replace('.scad', '.stl')}`;
                
                // Show the updated preview
                this.showModelPreview(this.currentPreviewPath);
            }
            
            window.utils.showSuccess('Model updated successfully');
            
        } catch (error) {
            console.error('Error updating model:', error);
            window.utils.showError(error.message || 'Failed to update model');
        } finally {
            window.utils.showLoading(false);
        }
    }
    
    showModelPreview(previewPath) {
        // Get preview image element or create one
        let modelPreview = document.getElementById('model-preview');
        if (!modelPreview) {
            modelPreview = document.createElement('img');
            modelPreview.id = 'model-preview';
            this.modelViewer.innerHTML = '';
            this.modelViewer.appendChild(modelPreview);
        }
        
        // Show preview image
        modelPreview.src = previewPath;
        modelPreview.style.display = 'block';
        
        // Hide any placeholders
        const placeholder = document.querySelector('.placeholder-viewer');
        if (placeholder) {
            placeholder.style.display = 'none';
        }
        
        // Hide 3D canvas if visible
        const modelCanvas = document.getElementById('model-canvas');
        if (modelCanvas) {
            modelCanvas.style.display = 'none';
        }
        
        // Set active tab
        const tabPreview = document.getElementById('tab-preview');
        const tab3D = document.getElementById('tab-3d');
        if (tabPreview && tab3D) {
            tabPreview.classList.add('active');
            tab3D.classList.remove('active');
        }
    }
    
    showPreviewTab() {
        // Get tab elements
        const tabPreview = document.getElementById('tab-preview');
        const tab3D = document.getElementById('tab-3d');
        
        // Set active state
        tabPreview.classList.add('active');
        tab3D.classList.remove('active');
        
        // Show preview image if available
        const modelPreview = document.getElementById('model-preview');
        const modelCanvas = document.getElementById('model-canvas');
        const placeholder = document.querySelector('.placeholder-viewer');
        
        if (this.currentPreviewPath && modelPreview) {
            modelPreview.style.display = 'block';
            if (modelCanvas) modelCanvas.style.display = 'none';
            if (placeholder) placeholder.style.display = 'none';
        } else {
            if (modelPreview) modelPreview.style.display = 'none';
            if (modelCanvas) modelCanvas.style.display = 'none';
            if (placeholder) placeholder.style.display = 'flex';
        }
    }
    
    show3DTab() {
        // Get tab elements
        const tabPreview = document.getElementById('tab-preview');
        const tab3D = document.getElementById('tab-3d');
        
        // Set active state
        tabPreview.classList.remove('active');
        tab3D.classList.add('active');
        
        // Show 3D view if STL is available
        if (this.currentStlPath) {
            // Initialize 3D viewer if needed
            this.initialize3DRenderer();
            
            // Show the canvas
            const modelCanvas = document.getElementById('model-canvas');
            const modelPreview = document.getElementById('model-preview');
            const placeholder = document.querySelector('.placeholder-viewer');
            
            if (modelCanvas) modelCanvas.style.display = 'block';
            if (modelPreview) modelPreview.style.display = 'none';
            if (placeholder) placeholder.style.display = 'none';
            
            // Load the STL model
            this.loadSTLModel(this.currentStlPath);
        } else {
            // Show placeholder if no STL
            const placeholder = document.querySelector('.placeholder-viewer');
            const modelPreview = document.getElementById('model-preview');
            const modelCanvas = document.getElementById('model-canvas');
            
            if (placeholder) placeholder.style.display = 'flex';
            if (modelPreview) modelPreview.style.display = 'none';
            if (modelCanvas) modelCanvas.style.display = 'none';
        }
    }
    
    initialize3DRenderer() {
        if (this.rendererInitialized) return;
        
        // Ensure Three.js is loaded
        if (typeof THREE === 'undefined') {
            console.error('Three.js is not loaded. Cannot initialize 3D renderer.');
            return;
        }
        
        // Create canvas if it doesn't exist
        let modelCanvas = document.getElementById('model-canvas');
        if (!modelCanvas) {
            modelCanvas = document.createElement('canvas');
            modelCanvas.id = 'model-canvas';
            modelCanvas.style.display = 'none';
            this.modelViewer.appendChild(modelCanvas);
        }
        
        // Create scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0xf5f5f5);
        
        // Create camera
        this.camera = new THREE.PerspectiveCamera(75, this.modelViewer.clientWidth / this.modelViewer.clientHeight, 0.1, 1000);
        this.camera.position.z = 30;
        
        // Create renderer
        this.renderer = new THREE.WebGLRenderer({ canvas: modelCanvas, antialias: true });
        this.renderer.setSize(this.modelViewer.clientWidth, this.modelViewer.clientHeight);
        
        // Add lights
        const ambientLight = new THREE.AmbientLight(0x404040);
        this.scene.add(ambientLight);
        
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(1, 1, 1);
        this.scene.add(directionalLight);
        
        const directionalLight2 = new THREE.DirectionalLight(0xffffff, 0.5);
        directionalLight2.position.set(-1, -1, -1);
        this.scene.add(directionalLight2);
        
        // Add orbit controls
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.25;
        
        // Add a grid
        const gridHelper = new THREE.GridHelper(50, 50);
        this.scene.add(gridHelper);
        
        // Add a coordinate system
        const axesHelper = new THREE.AxesHelper(10);
        this.scene.add(axesHelper);
        
        // Animation loop
        const animate = () => {
            requestAnimationFrame(animate);
            this.controls.update();
            this.renderer.render(this.scene, this.camera);
        };
        
        animate();
        
        this.rendererInitialized = true;
    }
    
    loadSTLModel(stlPath) {
        if (!this.rendererInitialized) {
            this.initialize3DRenderer();
        }
        
        // Remove existing model if any
        if (this.modelMesh) {
            this.scene.remove(this.modelMesh);
        }
        
        // Load STL file
        const loader = new THREE.STLLoader();
        loader.load(stlPath, (geometry) => {
            const material = new THREE.MeshPhongMaterial({
                color: 0x3f7fb0,
                specular: 0x111111,
                shininess: 200
            });
            
            this.modelMesh = new THREE.Mesh(geometry, material);
            
            // Center the model
            geometry.computeBoundingBox();
            const boundingBox = geometry.boundingBox;
            const center = new THREE.Vector3();
            boundingBox.getCenter(center);
            this.modelMesh.position.set(-center.x, -center.y, -center.z);
            
            // Scale the model to fit the view
            const size = new THREE.Vector3();
            boundingBox.getSize(size);
            const maxDim = Math.max(size.x, size.y, size.z);
            const scale = 20 / maxDim;
            this.modelMesh.scale.set(scale, scale, scale);
            
            this.scene.add(this.modelMesh);
            
            // Position camera to view the model
            this.camera.position.set(0, 10, 30);
            this.controls.update();
        });
    }
    
    onWindowResize() {
        if (!this.rendererInitialized || !this.camera || !this.renderer) return;
        
        const modelCanvas = document.getElementById('model-canvas');
        if (!modelCanvas || modelCanvas.style.display === 'none') return;
        
        this.camera.aspect = this.modelViewer.clientWidth / this.modelViewer.clientHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.modelViewer.clientWidth, this.modelViewer.clientHeight);
    }
    
    downloadStl() {
        if (!this.currentStlPath) {
            window.utils.showError('No STL file available for download');
            return;
        }
        
        window.location.href = this.currentStlPath;
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.modelGenerator = new ModelGenerator();
});