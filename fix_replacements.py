import sys

files = [
    'silent_attacks.cpp',
    'silent_skills1.cpp',
    'silent_skills2.cpp',
    'defect_attacks.cpp',
    'silent_powers.cpp'
]

replacements = {
    'MS::CHOKE>': 'MS::CHOKED>',
    'MS::CHOKE ': 'MS::CHOKED ',
    'cards.cardsPlayedThisTurn': 'player.cardsPlayedThisTurn',
    'PS::NEXT_TURN_ENERGY': 'PS::ENERGIZED',
    'PS::DRAW_CARD>': 'PS::DRAW_CARD_NEXT_TURN>',
    'getCostForTurn()': 'costForTurn',
    'getCost()': 'cost',
    'removeFromDiscardAtIdx': 'removeFromDiscard',
    'addToHand': 'moveToHand',
    'Actions::AttackRandomEnemy': 'Actions::DamageRandomEnemy',
    'hasIntentToAttack()': 'isAttacking()',
    'Action([](BattleContext &b)': 'Action([&](BattleContext &b)',
    'Action([=](BattleContext &b)': 'Action([&](BattleContext &b)',
    'b.attackEnemy(t, dmg);': 'b.monsters.arr[t].attacked(b, dmg);',
    'DrawCardsWrapper(4, [](BattleContext &bc': 'DrawCardsWrapper(4, [&](BattleContext &bc',
    'Cards.lightningOrbsChanneledThisCombat': 'player.lightningOrbsChanneledThisCombat',
    'cards.lightningOrbsChanneledThisCombat': 'player.lightningOrbsChanneledThisCombat'
}

for f in files:
    try:
        with open(f, 'r') as file:
            content = file.read()
            
        for k, v in replacements.items():
            content = content.replace(k, v)
                
        with open(f, 'w') as file:
            file.write(content)
        print(f"Patched {f}")
    except Exception as e:
        print(f"Error on {f}: {e}")

print("Replacements applied safely.")
