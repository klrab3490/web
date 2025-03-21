import os
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List

class PaymentController:
    """Controller for payment processing"""
    
    def __init__(self, config: Dict[str, Any], razorpay_service=None):
        self.config = config
        self.razorpay_service = razorpay_service
        self.payment_records_path = config.get('PAYMENT_RECORDS_PATH', 'data/payments')
        
        # Ensure payments directory exists
        os.makedirs(self.payment_records_path, exist_ok=True)
        
        # Token costs
        self.token_packages = {
            "small": {"tokens": 50, "price": 99, "currency": "INR"},
            "medium": {"tokens": 200, "price": 299, "currency": "INR"},
            "large": {"tokens": 500, "price": 599, "currency": "INR"}
        }
    
    def create_order(self, user_id: str, package_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Create a payment order
        
        Args:
            user_id: ID of the user making the purchase
            package_id: ID of the token package
            
        Returns:
            Tuple of (success, order_data)
        """
        try:
            # Check if package exists
            if package_id not in self.token_packages:
                return False, {"error": "Invalid package ID"}
                
            package = self.token_packages[package_id]
            
            # Create order ID
            order_id = f"order_{uuid.uuid4().hex[:8]}"
            
            # If Razorpay service is available, create actual order
            if self.razorpay_service:
                order_data = self.razorpay_service.create_order(
                    amount=package["price"] * 100,  # In smallest currency unit (paise)
                    currency=package["currency"],
                    receipt=order_id
                )
                razorpay_order_id = order_data["id"]
            else:
                # Mock order for testing
                razorpay_order_id = f"rzp_{uuid.uuid4().hex[:16]}"
            
            # Save order details
            order_data = {
                "order_id": order_id,
                "razorpay_order_id": razorpay_order_id,
                "user_id": user_id,
                "package_id": package_id,
                "amount": package["price"],
                "currency": package["currency"],
                "tokens": package["tokens"],
                "status": "created",
                "created_at": datetime.now().isoformat()
            }
            
            # Save to file
            order_file = os.path.join(self.payment_records_path, f"{order_id}.json")
            with open(order_file, 'w') as f:
                json.dump(order_data, f, indent=2)
            
            return True, order_data
            
        except Exception as e:
            return False, {"error": str(e)}
    
    def verify_payment(self, payment_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify a payment
        
        Args:
            payment_data: Payment verification data
            
        Returns:
            Tuple of (success, payment_result)
        """
        try:
            # Extract payment details
            order_id = payment_data.get("order_id")
            razorpay_payment_id = payment_data.get("razorpay_payment_id")
            razorpay_signature = payment_data.get("razorpay_signature")
            
            if not order_id or not razorpay_payment_id:
                return False, {"error": "Missing required payment data"}
            
            # Load order details
            order_file = os.path.join(self.payment_records_path, f"{order_id}.json")
            if not os.path.exists(order_file):
                return False, {"error": "Order not found"}
                
            with open(order_file, 'r') as f:
                order_data = json.load(f)
            
            # Verify signature if Razorpay service is available
            if self.razorpay_service and razorpay_signature:
                is_valid = self.razorpay_service.verify_payment_signature({
                    "razorpay_order_id": order_data["razorpay_order_id"],
                    "razorpay_payment_id": razorpay_payment_id,
                    "razorpay_signature": razorpay_signature
                })
                
                if not is_valid:
                    return False, {"error": "Invalid payment signature"}
            
            # Update order status
            order_data["status"] = "completed"
            order_data["payment_id"] = razorpay_payment_id
            order_data["completed_at"] = datetime.now().isoformat()
            
            # Save updated order
            with open(order_file, 'w') as f:
                json.dump(order_data, f, indent=2)
            
            return True, {
                "order_id": order_id,
                "payment_id": razorpay_payment_id,
                "tokens": order_data["tokens"],
                "amount": order_data["amount"],
                "currency": order_data["currency"]
            }
            
        except Exception as e:
            return False, {"error": str(e)}
    
    def get_payment_history(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get payment history for a user
        
        Args:
            user_id: ID of the user
            
        Returns:
            List of payment records
        """
        try:
            history = []
            
            # Iterate through payment files
            for filename in os.listdir(self.payment_records_path):
                if not filename.endswith('.json'):
                    continue
                    
                file_path = os.path.join(self.payment_records_path, filename)
                
                with open(file_path, 'r') as f:
                    order_data = json.load(f)
                
                # Check if order belongs to user
                if order_data.get("user_id") == user_id:
                    # Add to history with limited fields for security
                    history.append({
                        "order_id": order_data.get("order_id"),
                        "amount": order_data.get("amount"),
                        "currency": order_data.get("currency"),
                        "tokens": order_data.get("tokens"),
                        "status": order_data.get("status"),
                        "created_at": order_data.get("created_at"),
                        "completed_at": order_data.get("completed_at", None)
                    })
            
            # Sort by date (newest first)
            history.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            
            return history
            
        except Exception as e:
            return []
