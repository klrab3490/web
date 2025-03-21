class ChatInterface {
    constructor() {
        this.csrfToken = document.querySelector('input[name="csrf_token"]')?.value || window.csrfToken || '';
        this.sessionId = null;
        this.chatMessages = document.getElementById('chat-messages');
        this.chatForm = document.getElementById('chat-form');
        this.userMessageInput = document.getElementById('user-message');
        this.topicButtons = document.querySelectorAll('.topic-btn');
        
        // Model preview elements
        this.modelPreviewContainer = document.getElementById('model-preview-container') || this.createModelPreviewContainer();
        
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
        
        this.initEventListeners();
        this.startChatSession();
    }
    
    createModelPreviewContainer() {
        // Create container for model preview that will be shown when a model is generated
        const container = document.createElement('div');
        container.id = 'model-preview-container';
        container.className = 'model-preview-container';
        container.style.display = 'none';
        
        // Create tabs for 2D/3D view
        const tabsHtml = `
            <div class="model-tabs">
                <div class="model-tab active" id="tab-preview">Preview</div>
                <div class="model-tab" id="tab-3d">3D View</div>
            </div>
            <div class="canvas-container">
                <div id="model-placeholder">
                    <i>⚙️</i>
                    <p>Your 3D model will appear here</p>
                </div>
                <img id="model-preview" style="display: none;">
                <canvas id="model-canvas" style="display: none;"></canvas>
            </div>
            <div class="model-actions">
                <button class="action-button" id="download-stl">Download STL</button>
                <button class="action-button buy-button" id="order-print">Order 3D Print</button>
            </div>
            <div class="parameter-section">
                <div class="parameter-title">Parameters</div>
                <div class="parameter-list" id="parameter-list"></div>
                <button id="update-model" style="display: none;">Update Model</button>
            </div>
        `;
        
        container.innerHTML = tabsHtml;
        
        // Append to the chat container
        const chatContainer = document.querySelector('.chat-container');
        if (chatContainer) {
            chatContainer.parentNode.insertBefore(container, chatContainer.nextSibling);
        } else {
            document.body.appendChild(container);
        }
        
        return container;
    }
    
    initEventListeners() {
        // Chat form submission
        if (this.chatForm) {
            this.chatForm.addEventListener('submit', (e) => this.handleSendMessage(e));
        }
        
        // Topic buttons
        this.topicButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const message = btn.getAttribute('data-message');
                if (message) {
                    this.userMessageInput.value = message;
                    this.chatForm.dispatchEvent(new Event('submit'));
                }
            });
        });
        
        // Tab switching
        const tabPreview = document.getElementById('tab-preview');
        const tab3D = document.getElementById('tab-3d');
        
        if (tabPreview) {
            tabPreview.addEventListener('click', () => this.showPreviewTab());
        }
        
        if (tab3D) {
            tab3D.addEventListener('click', () => this.show3DTab());
        }
        
        // Download STL button
        const downloadStlBtn = document.getElementById('download-stl');
        if (downloadStlBtn) {
            downloadStlBtn.addEventListener('click', () => this.downloadStl());
        }
        
        // Order print button
        const orderPrintBtn = document.getElementById('order-print');
        if (orderPrintBtn) {
            orderPrintBtn.addEventListener('click', () => this.orderPrint());
        }
        
        // Update model button
        const updateModelBtn = document.getElementById('update-model');
        if (updateModelBtn) {
            updateModelBtn.addEventListener('click', () => this.updateModel());
        }
        
        // Handle window resize for 3D renderer
        window.addEventListener('resize', () => this.onWindowResize());
    }
    
    async startChatSession() {
        try {
            const response = await fetch('/api/chat/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': this.csrfToken
                },
                body: JSON.stringify({
                    csrf_token: this.csrfToken
                })
            });
            
            if (!response.ok) {
                throw new Error('Failed to start chat session');
            }
            
            const data = await response.json();
            
            if (data.success) {
                this.sessionId = data.session_id;
                
                // Initial welcome message is already in the HTML template
            } else {
                throw new Error(data.error || 'Failed to start chat session');
            }
        } catch (error) {
            console.error('Error starting chat session:', error);
            this.addErrorMessage('Could not start chat session. Please try refreshing the page.');
        }
    }
    
    async handleSendMessage(e) {
        e.preventDefault();
        
        const message = this.userMessageInput.value.trim();
        
        if (!message || !this.sessionId) {
            return;
        }
        
        // Add user message to chat
        this.addUserMessage(message);
        
        // Clear input
        this.userMessageInput.value = '';
        
        // Add loading indicator
        const loadingId = this.addLoadingMessage();
        
        try {
            const response = await fetch('/api/chat/message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': this.csrfToken
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    message: message,
                    user_id: this.getUserId(),
                    csrf_token: this.csrfToken
                })
            });
            
            // Remove loading indicator
            this.removeLoadingMessage(loadingId);
            
            if (!response.ok) {
                throw new Error('Failed to send message');
            }
            
            const data = await response.json();
            
            if (data.success) {
                // Add assistant response
                this.addAssistantMessage(data.response);
                
                // Check if there's model data in the response
                if (data.code || data.model_id) {
                    this.handleModelData(data);
                }
            } else {
                throw new Error(data.error || 'Failed to send message');
            }
        } catch (error) {
            console.error('Error sending message:', error);
            this.removeLoadingMessage(loadingId);
            this.addErrorMessage('Failed to send message. Please try again.');
        }
    }
    
    getUserId() {
        // Generate a unique user ID if not available
        if (!window.userId) {
            window.userId = 'user_' + Math.random().toString(36).substring(2, 15);
        }
        return window.userId;
    }
    
    handleModelData(data) {
        // Save model data
        this.currentCode = data.code || '';
        this.currentParams = data.parameters || {};
        this.currentModelId = data.model_id || '';
        
        const userId = this.getUserId();
        
        // Set paths for preview and STL
        if (data.model_id) {
            this.currentPreviewPath = `/preview/${userId}/${data.model_id}`;
            this.currentStlPath = `/model/${userId}/${data.model_id.replace('.scad', '.stl')}`;
        } else if (data.preview_path) {
            this.currentPreviewPath = data.preview_path;
        }
        
        // Show model preview container
        this.modelPreviewContainer.style.display = 'block';
        
        // Display parameter inputs
        this.updateParameterList(data.parameters);
        
        // Show model preview
        if (this.currentPreviewPath) {
            this.showModelPreview(this.currentPreviewPath);
        }
        
        // Enable download STL button if STL is available
        const downloadStlBtn = document.getElementById('download-stl');
        if (downloadStlBtn) {
            downloadStlBtn.disabled = !this.currentStlPath;
        }
    }
    
    addUserMessage(message) {
        const messageEl = document.createElement('div');
        messageEl.className = 'message user';
        messageEl.innerHTML = `
            <div class="message-content">${this.escapeHtml(message)}</div>
        `;
        
        this.chatMessages.appendChild(messageEl);
        this.scrollToBottom();
    }
    
    addAssistantMessage(message) {
        const messageEl = document.createElement('div');
        messageEl.className = 'message assistant';
        messageEl.innerHTML = `
            <div class="message-content">${this.formatMessage(message)}</div>
        `;
        
        this.chatMessages.appendChild(messageEl);
        this.scrollToBottom();
    }
    
    addErrorMessage(message) {
        const messageEl = document.createElement('div');
        messageEl.className = 'message system';
        messageEl.innerHTML = `
            <div class="message-content error">${this.escapeHtml(message)}</div>
        `;
        
        this.chatMessages.appendChild(messageEl);
        this.scrollToBottom();
    }
    
    addLoadingMessage() {
        const id = 'loading-' + Date.now();
        const messageEl = document.createElement('div');
        messageEl.className = 'message assistant';
        messageEl.id = id;
        messageEl.innerHTML = `
            <div class="message-content">
                <span class="loading-dots"></span>
            </div>
        `;
        
        this.chatMessages.appendChild(messageEl);
        this.scrollToBottom();
        
        return id;
    }
    
    removeLoadingMessage(id) {
        const loadingEl = document.getElementById(id);
        if (loadingEl) {
            this.chatMessages.removeChild(loadingEl);
        }
    }
    
    formatMessage(message) {
        // Convert line breaks to <br> tags
        return this.escapeHtml(message).replace(/\n/g, '<br>');
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }
    
    updateParameterList(parameters) {
        if (!parameters) return;
        
        const parameterList = document.getElementById('parameter-list');
        if (!parameterList) return;
        
        // Clear existing parameters
        parameterList.innerHTML = '';
        
        // Add new parameters
        for (const [name, info] of Object.entries(parameters)) {
            const paramItem = document.createElement('div');
            paramItem.className = 'parameter-item';
            
            const paramLabel = document.createElement('label');
            paramLabel.className = 'parameter-label';
            paramLabel.textContent = name;
            
            const paramInput = document.createElement('input');
            paramInput.className = 'parameter-input';
            paramInput.type = 'text';
            paramInput.name = name;
            paramInput.value = info.default || '';
            
            paramItem.appendChild(paramLabel);
            paramItem.appendChild(paramInput);
            parameterList.appendChild(paramItem);
        }
        
        // Show update button if parameters exist
        const updateModelBtn = document.getElementById('update-model');
        if (updateModelBtn) {
            updateModelBtn.style.display = Object.keys(parameters).length > 0 ? 'block' : 'none';
        }
    }
    
    showModelPreview(previewPath) {
        // Get preview image element
        const modelPreview = document.getElementById('model-preview');
        const modelPlaceholder = document.getElementById('model-placeholder');
        const modelCanvas = document.getElementById('model-canvas');
        
        if (!modelPreview) return;
        
        // Show preview image
        modelPreview.src = previewPath;
        modelPreview.style.display = 'block';
        
        // Hide placeholder and canvas
        if (modelPlaceholder) modelPlaceholder.style.display = 'none';
        if (modelCanvas) modelCanvas.style.display = 'none';
        
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
        if (tabPreview) tabPreview.classList.add('active');
        if (tab3D) tab3D.classList.remove('active');
        
        // Show preview image if available
        const modelPreview = document.getElementById('model-preview');
        const modelCanvas = document.getElementById('model-canvas');
        const modelPlaceholder = document.getElementById('model-placeholder');
        
        if (this.currentPreviewPath && modelPreview) {
            modelPreview.style.display = 'block';
            if (modelCanvas) modelCanvas.style.display = 'none';
            if (modelPlaceholder) modelPlaceholder.style.display = 'none';
        } else {
            if (modelPreview) modelPreview.style.display = 'none';
            if (modelCanvas) modelCanvas.style.display = 'none';
            if (modelPlaceholder) modelPlaceholder.style.display = 'flex';
        }
    }
    
    show3DTab() {
        // Get tab elements
        const tabPreview = document.getElementById('tab-preview');
        const tab3D = document.getElementById('tab-3d');
        
        // Set active state
        if (tabPreview) tabPreview.classList.remove('active');
        if (tab3D) tab3D.classList.add('active');
        
        // Show 3D view if STL is available
        if (this.currentStlPath) {
            // Initialize 3D viewer if needed
            this.initialize3DRenderer();
            
            // Show the canvas
            const modelCanvas = document.getElementById('model-canvas');
            const modelPreview = document.getElementById('model-preview');
            const modelPlaceholder = document.getElementById('model-placeholder');
            
            if (modelCanvas) modelCanvas.style.display = 'block';
            if (modelPreview) modelPreview.style.display = 'none';
            if (modelPlaceholder) modelPlaceholder.style.display = 'none';
            
            // Load the STL model
            this.loadSTLModel(this.currentStlPath);
        } else {
            // Show placeholder if no STL
            const modelPlaceholder = document.getElementById('model-placeholder');
            const modelPreview = document.getElementById('model-preview');
            const modelCanvas = document.getElementById('model-canvas');
            
            if (modelPlaceholder) modelPlaceholder.style.display = 'flex';
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
        
        // Get canvas element
        const modelCanvas = document.getElementById('model-canvas');
        if (!modelCanvas) return;
        
        // Get container element for sizing
        const canvasContainer = modelCanvas.parentElement;
        
        // Create scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0xf5f5f5);
        
        // Create camera
        this.camera = new THREE.PerspectiveCamera(75, canvasContainer.clientWidth / canvasContainer.clientHeight, 0.1, 1000);
        this.camera.position.z = 30;
        
        // Create renderer
        this.renderer = new THREE.WebGLRenderer({ canvas: modelCanvas, antialias: true });
        this.renderer.setSize(canvasContainer.clientWidth, canvasContainer.clientHeight);
        
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
        
        const canvasContainer = modelCanvas.parentElement;
        
        this.camera.aspect = canvasContainer.clientWidth / canvasContainer.clientHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(canvasContainer.clientWidth, canvasContainer.clientHeight);
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
            
            this.addAssistantMessage("I've updated the model with your parameters.");
            
        } catch (error) {
            console.error('Error updating model:', error);
            this.addErrorMessage(error.message || 'Failed to update model');
        } finally {
            window.utils.showLoading(false);
        }
    }
    
    downloadStl() {
        if (!this.currentStlPath) {
            this.addErrorMessage('No STL file available for download');
            return;
        }
        
        window.location.href = this.currentStlPath;
    }
    
    orderPrint() {
        if (!this.currentModelId) {
            this.addErrorMessage('Please create a model first');
            return;
        }
        
        // Redirect to checkout page
        window.location.href = `/checkout?user_id=${this.getUserId()}&model_id=${this.currentModelId}`;
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.chatInterface = new ChatInterface();
});