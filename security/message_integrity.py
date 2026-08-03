import hmac
import hashlib
import json
import config

class MessageIntegrityVerifier:
    """
    HMAC-style message checksum verification for swarm acoustic communication.
    """
    SHARED_KEY = "swarm_shared_acoustic_key"

    @staticmethod
    def generate_checksum(payload, secret_key=None):
        if secret_key is None:
            secret_key = MessageIntegrityVerifier.SHARED_KEY
        
        # Remove any existing checksum key
        payload_copy = {k: v for k, v in payload.items() if k != "checksum"}
        
        # Sort keys to ensure deterministic serialization
        serialized = json.dumps(payload_copy, sort_keys=True)
        return hmac.new(
            secret_key.encode('utf-8'),
            serialized.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    @staticmethod
    def verify_checksum(payload, secret_key=None):
        if not isinstance(payload, dict):
            return True
        if "checksum" not in payload:
            return False
            
        if secret_key is None:
            secret_key = MessageIntegrityVerifier.SHARED_KEY
            
        expected = MessageIntegrityVerifier.generate_checksum(payload, secret_key)
        return hmac.compare_digest(payload["checksum"], expected)
