import sys

with open('defect_attacks.cpp', 'r') as f:
    attacks_code = f.read()

with open('defect_skills.cpp', 'r') as f:
    skills_code = f.read()

with open('defect_powers.cpp', 'r') as f:
    powers_code = f.read()

with open('src/combat/BattleContext.cpp', 'r') as f:
    battle_context = f.read()

attacks_target = """        case CardId::UNLOAD: {
            const int dmg = calculateCardDamage(c, t, up ? 18 : 14);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Action([=] (BattleContext &b) {
                int count = b.cards.cardsInHand;
                for (int i=count-1; i>=0; --i) {
                    if (b.cards.hand[i].getType() != CardType::ATTACK) {
                        auto cardDiscarded = b.cards.hand[i];
                        b.cards.removeFromHandAtIdx(i);
                        b.cards.moveToDiscardPile(cardDiscarded);
                        b.onManualDiscard(cardDiscarded);
                    }
                }
            }) );
            break;
        }

"""

attacks_replacement = attacks_target + "        // ********************* DEFECT ATTACKS *********************\n\n" + attacks_code

skills_target = """        case CardId::TERROR: {
            addToBot( Actions::DebuffEnemy<MS::VULNERABLE>(t, 99, false) );
            break;
        }

"""

skills_replacement = skills_target + "        // ********************* DEFECT SKILLS *********************\n\n" + skills_code

powers_target = """        case CardId::WRAITH_FORM:
            addToBot( Actions::BuffPlayer<PS::INTANGIBLE>(up ? 3 : 2) );
            addToBot( Actions::DebuffPlayer<PS::WRAITH_FORM>(1) );
            break;

"""

powers_replacement = powers_target + "        // ********************* DEFECT POWERS *********************\n\n" + powers_code

battle_context = battle_context.replace(attacks_target, attacks_replacement)
battle_context = battle_context.replace(skills_target, skills_replacement)
battle_context = battle_context.replace(powers_target, powers_replacement)

with open('src/combat/BattleContext.cpp', 'w') as f:
    f.write(battle_context)

print("Injections successful.")
