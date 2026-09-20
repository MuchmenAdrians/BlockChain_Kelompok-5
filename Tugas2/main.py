from collections import Counter
from block import Block
from pow import proof_of_work 
from pos import proof_of_stake

# ==============================
# PROGRAM UTAMA 
# ==============================

print("PROOF OF WORK")

difficulties = [2, 3, 4, 5]

for difficulty in difficulties:
    print("\n"+ "="*50)
    print(f"DIFFICULT {difficulty}")
    print("="*50)

    block = Block(
        index=1,
        data="Tiket konser dibeli oleh pembeli dari Promotor",
        previous_hash="0"
    )

    print("\nData Block        :", block.data)
    print("Difficulty        :", difficulty)

    proof_of_work(block, difficulty)

    print("Nonce :", block.nonce)
    print("Hash  :", block.hash)

print("")
print("PROOF OF STAKE")

validators = {
    "Promotor"      : 10,
    "Venue"         : 20,
    "Sponsor"       : 30,
    "Platform Tiket": 40
}

print("\nValidator:")
for validator, stake in validators.items():
    print(f"- {validator}: {stake} stake")

print("")

hasil = []
for i in range(1, 21):
    selected = proof_of_stake(validators)
    print(f"{i:>2}. Validator terpilih:", selected)
    hasil.append(selected)

rekap = Counter(hasil)

print("\nRekap:")
for validator in validators:
    print(f"- {validator} : {rekap.get(validator, 0)}")
