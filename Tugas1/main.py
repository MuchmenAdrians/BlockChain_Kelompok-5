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
