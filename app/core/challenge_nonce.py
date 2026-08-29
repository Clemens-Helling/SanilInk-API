"""
Challenge Nonce Store - In-Memory Implementation with TTL.

Single-use nonce validation for SCRAM-proof login.
Ensures each challenge_nonce can only be used once within a time window.
"""

import time
from collections import defaultdict
from typing import Optional


class ChallengeNonceStore:
	"""
	In-memory store for login challenge nonces with automatic expiration.
	
	Invariants:
	1. Each nonce is single-use – validated once, then invalidated
	2. Nonces expire after TTL (default 5 minutes)
	3. Expired nonces are automatically cleaned up
	
	For production, consider Redis or database-backed storage.
	"""
	
	def __init__(self, ttl_seconds: int = 300):
		"""
		Initialize nonce store.
		
		Args:
			ttl_seconds: Time-to-live for nonces in seconds (default: 5 min)
		"""
		self.ttl_seconds = ttl_seconds
		self.nonces: dict[str, tuple[float, Optional[str]]] = {}
	
	def create_nonce(self, email: str, customer_number: str) -> str:
		"""
		Create a new challenge nonce for a login attempt.
		
		Args:
			email: User email (for tracking)
			customer_number: Tenant customer number (for tracking)
		
		Returns:
			Nonce as hex string (from crypto.generate_challenge_nonce)
		"""
		from app.core.crypto import generate_challenge_nonce
		
		nonce_bytes = generate_challenge_nonce()
		nonce_hex = nonce_bytes.hex()
		
		# Store: (creation_time, identifier_for_tracking)
		identifier = f"{email}@{customer_number}"
		self.nonces[nonce_hex] = (time.time(), identifier)
		
		return nonce_hex

	def get_identifier(self, nonce_hex: str) -> Optional[str]:
		"""Return the stored identifier for a nonce without consuming it."""
		entry = self.nonces.get(nonce_hex)
		if entry is None:
			return None
		created_at, identifier = entry
		if time.time() - created_at > self.ttl_seconds:
			del self.nonces[nonce_hex]
			return None
		return identifier
	
	def is_valid_and_consume(self, nonce_hex: str) -> bool:
		"""
		Validate a nonce and mark it as consumed (single-use).
		
		Args:
			nonce_hex: Nonce to validate
		
		Returns:
			True if nonce is valid and not expired, False otherwise
		"""
		if nonce_hex not in self.nonces:
			return False
		
		created_at, _identifier = self.nonces[nonce_hex]
		now = time.time()
		
		# Check if expired
		if now - created_at > self.ttl_seconds:
			del self.nonces[nonce_hex]
			return False
		
		# Nonce is valid – consume it (invalidate for replay)
		del self.nonces[nonce_hex]
		return True
	
	def cleanup_expired(self) -> int:
		"""
		Remove all expired nonces from store.
		Call periodically or on-demand to free memory.
		
		Returns:
			Number of nonces removed
		"""
		now = time.time()
		expired = [
			nonce for nonce, (created_at, _) in self.nonces.items()
			if now - created_at > self.ttl_seconds
		]
		for nonce in expired:
			del self.nonces[nonce]
		return len(expired)


# Global singleton instance
_nonce_store: Optional[ChallengeNonceStore] = None


def get_nonce_store() -> ChallengeNonceStore:
	"""Get or initialize the global challenge nonce store."""
	global _nonce_store
	if _nonce_store is None:
		_nonce_store = ChallengeNonceStore(ttl_seconds=300)  # 5 minutes
	return _nonce_store
