class PaymentManager {
    constructor() {
        this.csrfToken = document.querySelector('input[name="csrf_token"]')?.value || window.csrfToken || '';
        this.packageButtons = document.querySelectorAll('.buy-package-btn');
        this.paymentModal = document.getElementById('payment-modal');
        this.closeModalBtn = document.querySelector('.close-modal');
        this.paymentDetails = document.getElementById('payment-details');
        this.razorpayContainer = document.getElementById('razorpay-container');
        this.historyContainer = document.getElementById('history-container');
        
        this.initEventListeners();
        this.loadPaymentHistory();
    }
    
    initEventListeners() {
        // Package buy buttons
        this.packageButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const packageId = btn.getAttribute('data-package-id');
                this.initiatePayment(packageId);
            });
        });
        
        // Close modal
        if (this.closeModalBtn) {
            this.closeModalBtn.addEventListener('click', () => {
                this.paymentModal.style.display = 'none';
            });
        }
        
        // Close modal on outside click
        window.addEventListener('click', (e) => {
            if (e.target === this.paymentModal) {
                this.paymentModal.style.display = 'none';
            }
        });
    }
    
    async initiatePayment(packageId) {
        try {
            window.utils.showLoading(true);
            
            const response = await fetch('/api/create-payment', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': this.csrfToken
                },
                body: JSON.stringify({
                    package_id: packageId,
                    csrf_token: this.csrfToken
                })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to initiate payment');
            }
            
            const data = await response.json();
            
            if (data.success) {
                // Display payment details
                this.displayPaymentDetails(data.order);
                
                // Show payment modal
                this.paymentModal.style.display = 'flex';
                
                // Initialize Razorpay if available
                if (typeof Razorpay !== 'undefined') {
                    this.initializeRazorpay(data.order);
                }
            } else {
                throw new Error(data.error || 'Failed to initiate payment');
            }
        } catch (error) {
            console.error('Payment initiation error:', error);
            window.utils.showError(error.message || 'Failed to initiate payment');
        } finally {
            window.utils.showLoading(false);
        }
    }
    
    displayPaymentDetails(order) {
        if (!this.paymentDetails) return;
        
        // Format currency and amount
        const currency = order.currency || 'INR';
        const amount = (order.amount || 0).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
        
        this.paymentDetails.innerHTML = `
            <div class="payment-info">
                <p><strong>Package:</strong> ${window.utils.escapeHtml(order.package_name || '')}</p>
                <p><strong>Tokens:</strong> ${order.tokens || 0}</p>
                <p><strong>Amount:</strong> ${currency} ${amount}</p>
                <p><strong>Order ID:</strong> ${window.utils.escapeHtml(order.order_id || '')}</p>
            </div>
            <div class="payment-instructions">
                <p>Click the "Pay Now" button to complete your purchase.</p>
            </div>
        `;
    }
    
    initializeRazorpay(order) {
        // Create a Razorpay instance
        const options = {
            key: order.key_id || 'rzp_test_key', // Replace with your Razorpay key
            amount: order.amount * 100, // Amount in smallest currency unit
            currency: order.currency || 'INR',
            name: '3D Model Generator',
            description: `Purchase ${order.tokens} Tokens`,
            order_id: order.razorpay_order_id,
            handler: (response) => {
                this.handlePaymentSuccess(order.order_id, response);
            },
            prefill: {
                name: '',
                email: '',
                contact: ''
            },
            theme: {
                color: '#2196f3'
            }
        };
        
        // Create and render the payment button
        const razorpayBtn = document.createElement('button');
        razorpayBtn.className = 'primary-btn';
        razorpayBtn.textContent = 'Pay Now';
        this.razorpayContainer.innerHTML = '';
        this.razorpayContainer.appendChild(razorpayBtn);
        
        razorpayBtn.addEventListener('click', () => {
            const rzp = new Razorpay(options);
            rzp.open();
        });
    }
    
    async handlePaymentSuccess(orderId, response) {
        try {
            window.utils.showLoading(true);
            
            // Send payment verification to server
            const verifyResponse = await fetch('/api/verify-payment', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': this.csrfToken
                },
                body: JSON.stringify({
                    order_id: orderId,
                    razorpay_payment_id: response.razorpay_payment_id,
                    razorpay_order_id: response.razorpay_order_id,
                    razorpay_signature: response.razorpay_signature,
                    csrf_token: this.csrfToken
                })
            });
            
            if (!verifyResponse.ok) {
                const errorData = await verifyResponse.json();
                throw new Error(errorData.error || 'Payment verification failed');
            }
            
            const data = await verifyResponse.json();
            
            if (data.success) {
                // Close modal
                this.paymentModal.style.display = 'none';
                
                // Show success message
                window.utils.showSuccess(`Payment successful! ${data.tokens} tokens added to your account.`);
                
                // Reload payment history
                this.loadPaymentHistory();
                
                // Update token display in header
                const tokenDisplay = document.querySelector('.token-balance');
                if (tokenDisplay) {
                    tokenDisplay.textContent = data.new_balance || '0';
                }
            } else {
                throw new Error(data.error || 'Payment verification failed');
            }
        } catch (error) {
            console.error('Payment verification error:', error);
            window.utils.showError(error.message || 'Failed to verify payment');
        } finally {
            window.utils.showLoading(false);
        }
    }
    
    async loadPaymentHistory() {
        try {
            const response = await fetch('/api/payment-history');
            
            if (!response.ok) {
                throw new Error('Failed to load payment history');
            }
            
            const data = await response.json();
            
            if (data.success) {
                this.displayPaymentHistory(data.history);
            } else {
                throw new Error(data.error || 'Failed to load payment history');
            }
        } catch (error) {
            console.error('Error loading payment history:', error);
            this.historyContainer.innerHTML = '<p>Failed to load payment history.</p>';
        }
    }
    
    displayPaymentHistory(history) {
        if (!this.historyContainer) return;
        
        if (!history || history.length === 0) {
            this.historyContainer.innerHTML = '<p>No payment history found.</p>';
            return;
        }
        
        // Create table
        let tableHtml = `
            <table class="history-table">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Tokens</th>
                        <th>Amount</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        // Add rows
        history.forEach(payment => {
            const date = window.utils.formatDate(payment.created_at);
            const status = payment.status === 'completed' ? 
                '<span style="color: #4caf50;">Completed</span>' : 
                '<span style="color: #f44336;">Pending</span>';
            
            tableHtml += `
                <tr>
                    <td>${date}</td>
                    <td>${payment.tokens || 0}</td>
                    <td>${payment.currency || 'INR'} ${payment.amount || 0}</td>
                    <td>${status}</td>
                </tr>
            `;
        });
        
        tableHtml += `
                </tbody>
            </table>
        `;
        
        this.historyContainer.innerHTML = tableHtml;
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.paymentManager = new PaymentManager();
});
