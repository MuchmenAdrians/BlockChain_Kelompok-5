import random

def proof_of_stake(validators):

    total_stake = sum(validators.values())

    random_number = random.uniform(0, total_stake)

    current = 0

    for validator, stake in validators.items():

        current += stake

        if random_number <= current:
            return validator
