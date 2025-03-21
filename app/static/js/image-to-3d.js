class ImageTo3DConverter {
    constructor() {
        this.csrfToken = document.querySelector('input[name="csrf_token"]')?.value || window.csrfToken || '';
        this.currentFileId = null;
        this.uploadedImageUrl = null;
        this.modelId = null;
        
        // Initialize elements
        this.imageInput = document.getElementById('image-input');
        this.imagePreview = document.getElementById('image-preview');
        this.previewArea = document.querySelector('.preview-area');
        this.uploadForm = document.getElementById('image-upload-form');
        this.uploadBtn = document.getElementById('upload-btn');
        this.removeImageBtn = document.getElementById('remove-image');
        this.conversionSection = document.querySelector('.conversion-section');
        this.generateBtn = document.getElementById('generate-3d-btn');
        this.resultSection = document.querySelector('.result-section');
        this.modelViewer = document.getElementById('model-viewer');
        this.modelDetails = document.getElementById('model-details');
        this.downloadButtons = document.getElementById('download-buttons');
        
        // Parameters elements
        this.resolutionSelect = document.getElementById('resolution');
        this.detailLevelSlider = document.getElementById('detail-level');
        this.detailLevelValue = document.getElementById('detail-level-value');
        this.smoothingSlider = document.getElementById('smoothing');
        this.smoothingValue = document.getElementById('smoothing-value');
        
        this.initEventListeners();
    }
    
    initEventListeners() {
        // File input change
        if (this.imageInput) {
            this.imageInput.addEventListener('change', (e) => this.handleFileSelect(e));
        }
        
        // Form submission
        if (this.uploadForm) {
            this.uploadForm.addEventListener('submit', (e) => this.handleFormSubmit(e));
        }
        
        // Remove image button
        if (this.removeImageBtn) {
            this.removeImageBtn.addEventListener('click', () => this.removeImage());
        }
        
        // Generate 3D button
        if (this.generateBtn) {
            this.generateBtn.addEventListener('click', () => this.generate3DModel());
        }
        
        // Parameter sliders
        if (this.detailLevelSlider) {
            this.detailLevelSlider.addEventListener('input', () => {
                this.detailLevelValue.textContent = this.detailLevelSlider.value;
            });
        }
        
        if (this.smoothingSlider) {
            this.smoothingSlider.addEventListener('input', () => {
                this.smoothingValue.textContent = this.smoothingSlider.value;
            });
        }
        
        // Drag and drop
        const dropArea = document.querySelector('.file-drop-area');
        if (dropArea) {
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                dropArea.addEventListener(eventName, (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                });
            });
            
            ['dragenter', 'dragover'].forEach(eventName => {
                dropArea.addEventListener(eventName, () => {
                    dropArea.classList.add('highlight');
                });
            });
            
            ['dragleave', 'drop'].forEach(eventName => {
                dropArea.addEventListener(eventName, () => {
                    dropArea.classList.remove('highlight');
                });
            });
            
            dropArea.addEventListener('drop', (e) => {
                const dt = e.dataTransfer;
                const files = dt.files;
                
                if (files.length) {
                    this.imageInput.files = files;
                    this.handleFileSelect({ target: this.imageInput });
                }
            });
            
            dropArea.addEventListener('click', () => {
                this.imageInput.click();
            });
        }
    }
    
    handleFileSelect(e) {
        const file = e.target.files[0];
        
        if (!file) {
            return;
        }
        
        // Check file type
        const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
        if (!validTypes.includes(file.type)) {
            window.utils.showError('Invalid file type. Please upload a JPEG, PNG, or WebP image.');
            this.imageInput.value = '';
            return;
        }
        
        // Check file size (10MB max)
        if (file.size > 10 * 1024 * 1024) {
            window.utils.showError('File is too large. Maximum size is 10MB.');
            this.imageInput.value = '';
            return;
        }
        
        // Preview the image
        const reader = new FileReader();
        reader.onload = (e) => {
            this.imagePreview.src = e.target.result;
            this.uploadedImageUrl = e.target.result;
            this.previewArea.style.display = 'block';
            this.uploadBtn.disabled = false;
        };
        reader.readAsDataURL(file);
    }
    
    async handleFormSubmit(e) {
        e.preventDefault();
        
        if (!this.imageInput.files.length) {
            return;
        }
        
        try {
            window.utils.showLoading(true);
            
            const formData = new FormData();
            formData.append('image', this.imageInput.files[0]);
            formData.append('csrf_token', this.csrfToken);
            
            const response = await fetch('/api/upload-image', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Upload failed');
            }
            
            const data = await response.json();
            
            if (data.success) {
                this.currentFileId = data.file_id;
                window.utils.showSuccess('Image uploaded successfully');
                
                // Show conversion section
                this.conversionSection.style.display = 'block';
            } else {
                throw new Error(data.error || 'Upload failed');
            }
        } catch (error) {
            console.error('Upload error:', error);
            window.utils.showError(error.message || 'Failed to upload image');
        } finally {
            window.utils.showLoading(false);
        }
    }
    
    removeImage() {
        this.imageInput.value = '';
        this.imagePreview.src = '';
        this.previewArea.style.display = 'none';
        this.uploadBtn.disabled = true;
        this.currentFileId = null;
        this.uploadedImageUrl = null;
        
        // Hide conversion section
        this.conversionSection.style.display = 'none';
    }
    
    async generate3DModel() {
        if (!this.currentFileId) {
            window.utils.showError('Please upload an image first');
            return;
        }
        
        try {
            window.utils.showLoading(true);
            
            // Collect parameters
            const parameters = {
                resolution: parseInt(this.resolutionSelect.value),
                detail_level: parseFloat(this.detailLevelSlider.value),
                smoothing: parseFloat(this.smoothingSlider.value)
            };
            
            const response = await fetch('/api/generate-3d-from-image', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': this.csrfToken
                },
                body: JSON.stringify({
                    file_id: this.currentFileId,
                    parameters: parameters,
                    csrf_token: this.csrfToken
                })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Generation failed');
            }
            
            const data = await response.json();
            
            if (data.success) {
                this.modelId = data.model_id;
                window.utils.showSuccess('3D model generated successfully');
                
                // Get model details and display
                await this.loadModelDetails();
                
                // Show result section
                this.resultSection.style.display = 'block';
            } else {
                throw new Error(data.error || 'Generation failed');
            }
        } catch (error) {
            console.error('Generation error:', error);
            window.utils.showError(error.message || 'Failed to generate 3D model');
        } finally {
            window.utils.showLoading(false);
        }
    }
    
    async loadModelDetails() {
        if (!this.modelId) return;
        
        try {
            const response = await fetch(`/api/3d-model/${this.modelId}`);
            
            if (!response.ok) {
                throw new Error('Failed to load model details');
            }
            
            const data = await response.json();
            
            if (data.success) {
                // Update model viewer
                this.updateModelViewer(data.preview_url);
                
                // Update model details
                this.modelDetails.innerHTML = `
                    <p><strong>Model ID:</strong> ${window.utils.escapeHtml(data.model_id)}</p>
                    <p><strong>Available Formats:</strong> ${Object.keys(data.formats).join(', ')}</p>
                `;
                
                // Update download buttons
                this.downloadButtons.innerHTML = '';
                
                for (const [format, url] of Object.entries(data.formats)) {
                    const btn = document.createElement('a');
                    btn.href = url;
                    btn.className = 'download-btn';
                    btn.textContent = `Download ${format.toUpperCase()}`;
                    this.downloadButtons.appendChild(btn);
                }
            }
        } catch (error) {
            console.error('Error loading model details:', error);
        }
    }
    
    updateModelViewer(previewUrl) {
        if (!previewUrl) {
            // Show placeholder
            this.modelViewer.innerHTML = `
                <div class="placeholder-viewer">
                    <div class="placeholder-text">3D Preview</div>
                    <div class="placeholder-cube"></div>
                </div>
            `;
            return;
        }
        
        // Show model preview image
        this.modelViewer.innerHTML = `
            <img src="${previewUrl}" alt="3D Model Preview" class="model-preview-image">
        `;
        
        // In a real implementation, you might use three.js to display the 3D model
    }
    
    showLoading(isLoading) {
        // Use the common loading indicator
        window.utils.showLoading(isLoading);
    }
    
    showError(message) {
        window.utils.showError(message);
    }
    
    showSuccess(message) {
        window.utils.showSuccess(message);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.imageConverter = new ImageTo3DConverter();
});
