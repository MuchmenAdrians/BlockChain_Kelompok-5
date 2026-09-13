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

class Blockchain:

    def __init__(self):
        self.chain = [
            self.create_genesis_block()
        ]

    def create_genesis_block(self):

        return Block(
            index=0,
            data={
                "message": "Genesis Block"
            },
            previous_hash="0"
        )

    def add_block(self, data: dict):

        previous_block = self.chain[-1]

        new_block = Block(
            index=len(self.chain),
            data=data,
            previous_hash=previous_block.hash
        )

        self.chain.append(new_block)

    def is_valid(self):

        for i in range(1, len(self.chain)):

            current = self.chain[i]
            previous = self.chain[i - 1]

            if current.hash != current.calculate_hash():
                return False

            if current.previous_hash != previous.hash:
                return False

        return True

# ==============================
# PROGRAM UTAMA (main.py)
# ==============================

blockchain = Blockchain()

blockchain.add_block({
    "ticket_id": "TIX-2026-001",
    "event": "Konser Coldplay Jakarta",
    "actor": "Promotor",
    "location": "Jakarta"
})

blockchain.add_block({
    "ticket_id": "TIX-2026-001",
    "event": "Konser Coldplay Jakarta",
    "actor": "Platform Penjualan",
    "location": "Online"
})

blockchain.add_block({
    "ticket_id": "TIX-2026-001",
    "event": "Konser Coldplay Jakarta",
    "actor": "Pembeli",
    "location": "Cirebon"
})


blockchain.add_block({
    "ticket_id": "TIX-2026-001",
    "event": "Konser Coldplay Jakarta",
    "actor": "Petugas Gate",
    "location": "Jakarta"
})

for block in blockchain.chain:

    print("=" * 50)
    print("INDEX :", block.index)
    print("DATA  :", block.data)
    print("PREV  :", block.previous_hash)
    print("HASH  :", block.hash)

print("\nBlockchain valid:", blockchain.is_valid())