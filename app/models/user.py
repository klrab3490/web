import os
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

class User:
    """Simple user model"""
    
    def __init__(self, user_id: str, session_id: str = None):
        self.user_id = user_id
        self.session_id = session_id or str(uuid.uuid4())
        self.created_at = datetime.now().isoformat()
        self.token_balance = 0
        self.free_generations_used = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary"""
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "token_balance": self.token_balance,
            "free_generations_used": self.free_generations_used
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """Create user from dictionary"""
        user = cls(data["user_id"], data.get("session_id"))
        user.created_at = data.get("created_at", user.created_at)
        user.token_balance = data.get("token_balance", 0)
        user.free_generations_used = data.get("free_generations_used", 0)
        return user

class UserManager:
    """Manager for user data"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Get a user by ID"""
        user_file = os.path.join(self.data_dir, f"{user_id}.json")
        
        if not os.path.exists(user_file):
            return None
            
        try:
            with open(user_file, 'r') as f:
                data = json.load(f)
            return User.from_dict(data)
        except:
            return None
    
    def save_user(self, user: User) -> bool:
        """Save a user"""
        user_file = os.path.join(self.data_dir, f"{user.user_id}.json")
        
        try:
            with open(user_file, 'w') as f:
                json.dump(user.to_dict(), f, indent=2)
            return True
        except:
            return False
    
    def create_user(self, user_id: str = None, session_id: str = None) -> User:
        """Create a new user"""
        if not user_id:
            user_id = f"user_{uuid.uuid4().hex[:8]}"
            
        user = User(user_id, session_id)
        self.save_user(user)
        return user
    
    def add_tokens(self, user_id: str, tokens: int) -> bool:
        """Add tokens to a user's balance"""
        user = self.get_user(user_id)
        
        if not user:
            user = self.create_user(user_id)
            
        user.token_balance += tokens
        return self.save_user(user)
    
    def use_tokens(self, user_id: str, tokens: int) -> bool:
        """Use tokens from a user's balance"""
        user = self.get_user(user_id)
        
        if not user or user.token_balance < tokens:
            return False
            
        user.token_balance -= tokens
        return self.save_user(user)
    
    def increment_free_generations(self, user_id: str) -> int:
        """Increment free generations used and return new count"""
        user = self.get_user(user_id)
        
        if not user:
            user = self.create_user(user_id)
            
        user.free_generations_used += 1
        self.save_user(user)
        return user.free_generations_used
