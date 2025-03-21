import os
import logging
import hmac
import hashlib
from typing import Dict, Any, Optional
import json

# Try to import Razorpay
try:
    import razorpay
    RAZORPAY_AVAILABLE = True
except ImportError:
    RAZORPAY_AVAILABLE = False

class RazorpayService:
    """Service for integrating with Razorpay payment gateway"""
    
    def __init__(self, config: Dict[str, Any]):
        self.logger = logging.getLogger("razorpay_service")
        self.config = config
        self.key_id = config.get("RAZORPAY_KEY_ID", "")
        self.key_secret = config.get("RAZORPAY_KEY_SECRET", "")
        self.client = None
        
        # Initialize Razorpay client if available
        if RAZORPAY_AVAILABLE and self.key_id and self.key_secret:
            try:
                self.client = razorpay.Client(auth=(self.key_id, self.key_secret))
                self.logger.info("Razorpay client initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize Razorpay client: {str(e)}")
        else:
            if not RAZORPAY_AVAILABLE:
                self.logger.warning("Razorpay SDK not available. Install with 'pip install razorpay'")
            else:
                self.logger.warning("Razorpay credentials not configured")
    
    def create_order(self, amount: int, currency: str = "INR", receipt: str = None) -> Dict[str, Any]:
        """
        Create a payment order
        
        Args:
            amount: Amount in smallest currency unit (e.g., paise for INR)
            currency: Currency code (e.g., INR, USD)
            receipt: Receipt ID for reference
            
        Returns:
            Order data dictionary
        """
        if not self.client:
            return self._mock_order(amount, currency, receipt)
            
        try:
            data = {
                "amount": amount,
                "currency": currency,
                "receipt": receipt or f"receipt_{os.urandom(8).hex()}"
            }
            
            order = self.client.order.create(data=data)
            self.logger.info(f"Created Razorpay order: {order['id']}")
            return order
            
        except Exception as e:
            self.logger.error(f"Error creating Razorpay order: {str(e)}")
            # Fall back to mock order in case of error
            return self._mock_order(amount, currency, receipt)
    
    def verify_payment_signature(self, data: Dict[str, Any]) -> bool:
        """
        Verify Razorpay payment signature
        
        Args:
            data: Dictionary containing razorpay_order_id, razorpay_payment_id, razorpay_signature
            
        Returns:
            True if signature is valid, False otherwise
        """
        if not self.client:
            # In mock mode, always return True
            return True
            
        try:
            # Get required fields
            order_id = data.get("razorpay_order_id")
            payment_id = data.get("razorpay_payment_id")
            signature = data.get("razorpay_signature")
            
            if not order_id or not payment_id or not signature:
                self.logger.error("Missing required fields for signature verification")
                return False
                
            # Use Razorpay SDK to verify
            return self.client.utility.verify_payment_signature({
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            })
            
        except Exception as e:
            self.logger.error(f"Error verifying Razorpay signature: {str(e)}")
            return False
    
    def _mock_order(self, amount: int, currency: str, receipt: str = None) -> Dict[str, Any]:
        """Create a mock order for testing"""
        import uuid
        
        order_id = f"order_{uuid.uuid4().hex[:16]}"
        self.logger.warning(f"Creating mock Razorpay order: {order_id}")
        
        return {
            "id": order_id,
            "entity": "order",
            "amount": amount,
            "amount_paid": 0,
            "amount_due": amount,
            "currency": currency,
            "receipt": receipt,
            "status": "created",
            "notes": {},
            "created_at": int(os.urandom(4).hex(), 16)
        }
    
    def fetch_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Fetch order details from Razorpay"""
        if not self.client:
            return None
            
        try:
            order = self.client.order.fetch(order_id)
            return order
        except Exception as e:
            self.logger.error(f"Error fetching Razorpay order: {str(e)}")
            return None
    
    def fetch_payment(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """Fetch payment details from Razorpay"""
        if not self.client:
            return None
            
        try:
            payment = self.client.payment.fetch(payment_id)
            return payment
        except Exception as e:
            self.logger.error(f"Error fetching Razorpay payment: {str(e)}")
            return None
