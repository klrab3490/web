document.addEventListener('DOMContentLoaded', function() {
    // Initialize CSRF token from meta tag
    window.csrfToken = window.csrfToken || "";
    
    // Common utility functions
    window.utils = {
        // Show error message
        showError: function(message) {
            const errorElement = document.getElementById('error-message');
            if (errorElement) {
                errorElement.textContent = message;
                errorElement.style.display = 'block';
                
                setTimeout(() => {
                    errorElement.style.display = 'none';
                }, 5000);
            }
        },
        
        // Show success message
        showSuccess: function(message) {
            const successElement = document.getElementById('success-message');
            if (successElement) {
                successElement.textContent = message;
                successElement.style.display = 'block';
                
                setTimeout(() => {
                    successElement.style.display = 'none';
                }, 5000);
            }
        },
        
        // Show loading indicator
        showLoading: function(isLoading) {
            let loadingElement = document.getElementById('loading');
            if (!loadingElement) {
                loadingElement = document.createElement('div');
                loadingElement.id = 'loading';
                loadingElement.className = 'loading-indicator';
                loadingElement.innerHTML = '<div class="spinner"></div><div>Processing...</div>';
                document.body.appendChild(loadingElement);
            }
            
            loadingElement.className = 'loading-indicator ' + (isLoading ? 'active' : '');
        },
        
        // Security helper to escape HTML
        escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },
        
        // Format date
        formatDate: function(dateString) {
            try {
                const date = new Date(dateString);
                return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
            } catch (e) {
                return dateString;
            }
        }
    };
    
    // Common event listeners
    
    // Buy tokens button
    const buyTokensBtn = document.getElementById('buy-tokens-btn');
    if (buyTokensBtn) {
        buyTokensBtn.addEventListener('click', function() {
            window.location.href = '/payment/purchase';
        });
    }
});
