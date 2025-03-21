class ChatInterface {
    constructor() {
        this.csrfToken = document.querySelector('input[name="csrf_token"]')?.value || window.csrfToken || '';
        this.sessionId = null;
        this.chatMessages = document.getElementById('chat-messages');
        this.chatForm = document.getElementById('chat-form');
        this.userMessageInput = document.getElementById('user-message');
        this.topicButtons = document.querySelectorAll('.topic-btn');
        
        this.initEventListeners();
        this.startChatSession();
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
            } else {
                throw new Error(data.error || 'Failed to send message');
            }
        } catch (error) {
            console.error('Error sending message:', error);
            this.removeLoadingMessage(loadingId);
            this.addErrorMessage('Failed to send message. Please try again.');
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
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.chatInterface = new ChatInterface();
});