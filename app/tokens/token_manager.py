import os
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional

class TokenManager:
    """Manager for token economy"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.token_data_path = config.get('TOKEN_DATA_PATH', 'data/tokens')
        self.free_generations = config.get('FREE_GENERATIONS', 5)
        
        # Token costs for different operations
        self.operation_costs = {
            "openscad_generation": 5,
            "image_to_3d": 20,
            "export_stl": 2,
            "export_obj": 3,
            "high_resolution": 10  # Additional cost for high resolution
        }
        
        # Ensure token data directory exists
        os.makedirs(self.token_data_path, exist_ok=True)
    
    def get_user_balance(self, user_id: str) -> int:
        """Get token balance for a user"""
        user_data = self._load_user_data(user_id)
        return user_data.get("balance", 0)
    
    def get_free_generations_remaining(self, user_id: str) -> int:
        """Get remaining free generations for a user"""
        user_data = self._load_user_data(user_id)
        used = user_data.get("free_generations_used", 0)
        remaining = max(self.free_generations - used, 0)
        return remaining
    
    def add_tokens(self, user_id: str, amount: int, source: str = "purchase") -> bool:
        """
        Add tokens to a user's balance
        
        Args:
            user_id: User ID
            amount: Amount of tokens to add
            source: Source of tokens (purchase, bonus, etc.)
            
        Returns:
            Success flag
        """
        if amount <= 0:
            return False
            
        user_data = self._load_user_data(user_id)
        current_balance = user_data.get("balance", 0)
        
        # Add tokens
        user_data["balance"] = current_balance + amount
        
        # Record transaction
        transaction = {
            "id": f"tx_{uuid.uuid4().hex[:8]}",
            "type": "credit",
            "amount": amount,
            "source": source,
            "timestamp": datetime.now().isoformat()
        }
        
        if "transactions" not in user_data:
            user_data["transactions"] = []
            
        user_data["transactions"].append(transaction)
        
        # Save updated data
        return self._save_user_data(user_id, user_data)
    
    def use_tokens(self, user_id: str, amount: int, operation: str) -> bool:
        """
        Use tokens from a user's balance
        
        Args:
            user_id: User ID
            amount: Amount of tokens to use
            operation: Operation type (for record keeping)
            
        Returns:
            Success flag
        """
        if amount <= 0:
            return False
            
        user_data = self._load_user_data(user_id)
        current_balance = user_data.get("balance", 0)
        
        # Check if user has enough tokens
        if current_balance < amount:
            return False
            
        # Deduct tokens
        user_data["balance"] = current_balance - amount
        
        # Record transaction
        transaction = {
            "id": f"tx_{uuid.uuid4().hex[:8]}",
            "type": "debit",
            "amount": amount,
            "operation": operation,
            "timestamp": datetime.now().isoformat()
        }
        
        if "transactions" not in user_data:
            user_data["transactions"] = []
            
        user_data["transactions"].append(transaction)
        
        # Save updated data
        return self._save_user_data(user_id, user_data)
    
    def use_free_generation(self, user_id: str) -> bool:
        """
        Use a free generation slot
        
        Args:
            user_id: User ID
            
        Returns:
            Success flag
        """
        user_data = self._load_user_data(user_id)
        used = user_data.get("free_generations_used", 0)
        
        # Check if user has free generations left
        if used >= self.free_generations:
            return False
            
        # Increment used count
        user_data["free_generations_used"] = used + 1
        
        # Record usage
        if "free_generations" not in user_data:
            user_data["free_generations"] = []
            
        user_data["free_generations"].append({
            "id": len(user_data["free_generations"]) + 1,
            "timestamp": datetime.now().isoformat()
        })
        
        # Save updated data
        return self._save_user_data(user_id, user_data)
    
    def get_operation_cost(self, operation: str, parameters: Dict[str, Any] = None) -> int:
        """
        Get the token cost for an operation
        
        Args:
            operation: Operation type
            parameters: Optional parameters that might affect cost
            
        Returns:
            Token cost
        """
        base_cost = self.operation_costs.get(operation, 0)
        
        # Adjust cost based on parameters
        if parameters:
            # For example, high resolution costs more
            if parameters.get("resolution") == "high":
                base_cost += self.operation_costs.get("high_resolution", 0)
                
        return base_cost
    
    def can_afford_generation(self, user_id: str, operation: str, parameters: Dict[str, Any] = None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Check if user can afford a generation
        
        Args:
            user_id: User ID
            operation: Operation type
            parameters: Optional parameters
            
        Returns:
            Tuple of (can_afford, message, payment_info)
        """
        # Get cost
        cost = self.get_operation_cost(operation, parameters)
        
        # First check free generations
        free_remaining = self.get_free_generations_remaining(user_id)
        if free_remaining > 0:
            return True, "Using free generation", {
                "type": "free",
                "cost": 0,
                "free_remaining": free_remaining - 1
            }
        
        # Check token balance
        balance = self.get_user_balance(user_id)
        if balance >= cost:
            return True, "Using token balance", {
                "type": "tokens",
                "cost": cost,
                "balance_remaining": balance - cost
            }
        
        # Cannot afford
        return False, "Insufficient tokens", {
            "type": "insufficient",
            "cost": cost,
            "balance": balance,
            "needed": cost - balance
        }
    
    def get_transaction_history(self, user_id: str) -> List[Dict[str, Any]]:
        """Get transaction history for a user"""
        user_data = self._load_user_data(user_id)
        return user_data.get("transactions", [])
    
    def _load_user_data(self, user_id: str) -> Dict[str, Any]:
        """Load user token data"""
        user_file = os.path.join(self.token_data_path, f"{user_id}_tokens.json")
        
        if not os.path.exists(user_file):
            return {
                "user_id": user_id,
                "balance": 0,
                "free_generations_used": 0,
                "transactions": [],
                "free_generations": [],
                "created_at": datetime.now().isoformat()
            }
            
        try:
            with open(user_file, 'r') as f:
                return json.load(f)
        except:
            return {
                "user_id": user_id,
                "balance": 0,
                "free_generations_used": 0
            }
    
    def _save_user_data(self, user_id: str, data: Dict[str, Any]) -> bool:
        """Save user token data"""
        user_file = os.path.join(self.token_data_path, f"{user_id}_tokens.json")
        
        try:
            with open(user_file, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except:
            return False
