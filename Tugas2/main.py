from collections import Counter
from block import Block
from pow import proof_of_work 
from pos import proof_of_stake

# ==============================
# PROGRAM UTAMA (main.py)
# ==============================

print("PROOF OF WORK")

for difficulty in [2, 3, 4, 5]:

    block = Block(
        index=1,
        data="Tiket dari Prmotor ke Venue",
        previous_hash="0"
    )

    print("\nData Block       :", block.data)
    print("Difficulty        :", difficulty)

    proof_of_work(block, difficulty)

    print("Nonce             :", block.nonce)
    print("Hash              :", block.hash)

print("PROOF OF STAKE")

validators = {
    "Promotor": 70,
    "Venue": 10,
    "Sponsor": 10,
    "Platform Tiket": 10
}

print("\nValidator:")
for validator, stake in validators.items():
    print(f"- {validator}: {stake} stake")

hasil = []
for i in range(1, 21):
    selected = proof_of_stake(validators)
    print(f"{i:>2}. Validator terpilih:", selected)
    hasil.append(selected)

print("\nRekap:", Counter(hasil))