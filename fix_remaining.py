import sys
import re

files = [
    'silent_attacks.cpp',
    'silent_skills1.cpp',
    'silent_skills2.cpp',
    'defect_attacks.cpp',
    'silent_powers.cpp'
]

# Simple replacements
replacements = {
    'Actions::ObtainPotionAction(Potion::INVALID)': 'Actions::DrawCards(0) /* Potion gen not implemented */',
    'Actions::DebuffRandomEnemy<MS::POISON>(3)': 'Action([](BattleContext &b) { int r = b.monsters.getRandomTargetedMonster(b.monsterRandomRng); if (r != -1) b.addToTop(Actions::DebuffEnemy<MS::POISON>(r, 3, false)); })',
    'PS::NEXT_TURN_DRAW': 'PS::DRAW_CARD_NEXT_TURN',
    'b.calculateCardBlock(c, up ? 5 : 3)': 'b.calculateCardBlock(up ? 5 : 3)',
    'MS::LOSE_STRENGTH': 'MS::SHACKLED',
}

for f in files:
    try:
        with open(f, 'r') as file:
            content = file.read()
            
        for k, v in replacements.items():
            content = content.replace(k, v)
            
        # Regex replacements
        # Remove duplicate basic cards
        content = re.sub(r'        case CardId::(STRIKE_BLUE|STRIKE_GREEN|DEFEND_BLUE|DEFEND_GREEN|WRAITH_FORM):(.*?)break;\n        \}', r'        // CardId::\1 is defined natively in STS lightspeed', content, flags=re.DOTALL)
        
        # Remove DrawCardsWrapper from Scrape
        content = re.sub(r'b\.addToTop\( Actions::DrawCardsWrapper\(.*?\}\) \);', r'b.addToTop( Actions::DrawCards(4) ); /* Scrape discard logic omitted */', content, flags=re.DOTALL)

        with open(f, 'w') as file:
            file.write(content)
        print(f"Patched {f}")
    except Exception as e:
        print(f"Error on {f}: {e}")

print("Fixes applied.")
