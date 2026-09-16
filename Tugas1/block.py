import hashlib
import json
from datetime import datetime

class Block:

    def __init__(
        self,
        index: int,
        data: dict,
        previous_hash: str
    ):
        self.index = index
        self.timestamp = datetime.utcnow().isoformat()
        self.data = data
        self.previous_hash = previous_hash
        self.hash = self.calculate_hash()

    def calculate_hash(self) -> str:

        block_data = {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash
        }

        encoded = json.dumps(
            block_data,
            sort_keys=True
        ).encode()

        return hashlib.sha256(encoded).hexdigest()
