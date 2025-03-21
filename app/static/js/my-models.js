class ModelsViewer {
    constructor() {
        this.csrfToken = document.querySelector('input[name="csrf_token"]')?.value || window.csrfToken || '';
        this.modelTypeFilter = document.getElementById('model-type-filter');
        this.sortBySelect = document.getElementById('sort-by');
        this.modelsContainer = document.getElementById('models-container');
        this.noModelsEl = document.getElementById('no-models');
        this.loadMoreBtn = document.getElementById('load-more-btn');
        this.currentPage = 1;
        this.hasMorePages = false;
        
        this.initEventListeners();
        this.loadModels();
    }
    
    initEventListeners() {
        // Filter and sort changes
        if (this.modelTypeFilter) {
            this.modelTypeFilter.addEventListener('change', () => {
                this.currentPage = 1;
                this.loadModels();
            });
        }
        
        if (this.sortBySelect) {
            this.sortBySelect.addEventListener('change', () => {
                this.currentPage = 1;
                this.loadModels();
            });
        }
        
        // Load more button
        if (this.loadMoreBtn) {
            this.loadMoreBtn.addEventListener('click', () => {
                this.currentPage++;
                this.loadModels(true);
            });
        }
        
        // Modal close buttons
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('close-modal') || e.target.id === 'model-details-modal') {
                document.getElementById('model-details-modal').style.display = 'none';
            }
        });
    }
    
    async loadModels(append = false) {
        try {
            window.utils.showLoading(true);
            
            // Get filter values
            const modelType = this.modelTypeFilter ? this.modelTypeFilter.value : '';
            const sortBy = this.sortBySelect ? this.sortBySelect.value : 'newest';
            
            // Build query string
            let queryString = `?page=${this.currentPage}&sort=${sortBy}`;
            if (modelType) {
                queryString += `&type=${modelType}`;
            }
            
            // Fetch models from API
            const response = await fetch(`/api/my-models${queryString}`);
            
            if (!response.ok) {
                throw new Error('Failed to load models');
            }
            
            const data = await response.json();
            
            if (data.success) {
                // Update pagination status
                this.hasMorePages = data.has_more;
                this.loadMoreBtn.style.display = this.hasMorePages ? 'inline-block' : 'none';
                
                // Display models
                if (data.models.length === 0 && !append) {
                    this.modelsContainer.innerHTML = '';
                    this.noModelsEl.style.display = 'block';
                } else {
                    this.noModelsEl.style.display = 'none';
                    
                    if (!append) {
                        this.modelsContainer.innerHTML = '';
                    }
                    
                    data.models.forEach(model => {
                        this.modelsContainer.appendChild(this.createModelCard(model));
                    });
                }
            } else {
                throw new Error(data.error || 'Failed to load models');
            }
        } catch (error) {
            console.error('Error loading models:', error);
            window.utils.showError(error.message || 'Failed to load models');
        } finally {
            window.utils.showLoading(false);
        }
    }
    
    createModelCard(model) {
        const card = document.createElement('div');
        card.className = 'model-card';
        
        // Determine preview image
        const previewUrl = model.preview_url || '';
        const previewHtml = previewUrl ? 
            `<img src="${previewUrl}" alt="Model preview">` : 
            `<div class="placeholder-cube"></div>`;
        
        // Format date
        const createdAt = window.utils.formatDate(model.created_at);
        
        // Model type label
        const typeLabel = model.model_type === 'openscad' ? 'OpenSCAD' : 'Image to 3D';
        
        card.innerHTML = `
            <div class="model-preview">
                ${previewHtml}
            </div>
            <div class="model-details">
                <div class="model-title">${window.utils.escapeHtml(model.name || `Model ${model.model_id}`)}</div>
                <div class="model-meta">
                    <span>${typeLabel}</span> • <span>${createdAt}</span>
                </div>
                <div class="model-actions">
                    <button class="view-model-btn primary-btn" data-model-id="${model.model_id}">View</button>
                    <button class="download-model-btn secondary-btn" data-model-id="${model.model_id}">Download</button>
                </div>
            </div>
        `;
        
        // Add event listeners
        const viewBtn = card.querySelector('.view-model-btn');
        if (viewBtn) {
            viewBtn.addEventListener('click', () => this.showModelDetails(model.model_id));
        }
        
        const downloadBtn = card.querySelector('.download-model-btn');
        if (downloadBtn) {
            downloadBtn.addEventListener('click', () => this.downloadModel(model.model_id));
        }
        
        return card;
    }
    
    async showModelDetails(modelId) {
        try {
            window.utils.showLoading(true);
            
            // Fetch model details
            const response = await fetch(`/api/3d-model/${modelId}`);
            
            if (!response.ok) {
                throw new Error('Failed to load model details');
            }
            
            const data = await response.json();
            
            if (data.success) {
                // Get modal elements
                const modal = document.getElementById('model-details-modal');
                const modalViewer = document.getElementById('modal-model-viewer');
                const modalInfo = document.getElementById('modal-model-info');
                
                // Update model viewer
                if (data.preview_url) {
                    modalViewer.innerHTML = `<img src="${data.preview_url}" alt="Model preview" style="max-width: 100%; max-height: 100%;">`;
                } else {
                    modalViewer.innerHTML = `
                        <div class="placeholder-viewer">
                            <div class="placeholder-text">3D Preview</div>
                            <div class="placeholder-cube"></div>
                        </div>
                    `;
                }
                
                // Update model info
                let downloadButtons = '';
                for (const [format, url] of Object.entries(data.formats)) {
                    downloadButtons += `<a href="${url}" class="download-btn">${format.toUpperCase()}</a>`;
                }
                
                modalInfo.innerHTML = `
                    <h4>Model Details</h4>
                    <p><strong>ID:</strong> ${window.utils.escapeHtml(data.model_id)}</p>
                    <p><strong>Type:</strong> ${data.model_type === 'openscad' ? 'OpenSCAD' : 'Image to 3D'}</p>
                    <p><strong>Created:</strong> ${window.utils.formatDate(data.created_at)}</p>
                    
                    <div class="download-options">
                        <h4>Download</h4>
                        <div class="download-buttons">
                            ${downloadButtons}
                        </div>
                    </div>
                `;
                
                // Show modal
                modal.style.display = 'flex';
            } else {
                throw new Error(data.error || 'Failed to load model details');
            }
        } catch (error) {
            console.error('Error loading model details:', error);
            window.utils.showError(error.message || 'Failed to load model details');
        } finally {
            window.utils.showLoading(false);
        }
    }
    
    downloadModel(modelId) {
        window.location.href = `/api/download-model/${modelId}/stl`;
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.modelsViewer = new ModelsViewer();
});
