        // ********************* SILENT ATTACKS *********************

        case CardId::ALL_OUT_ATTACK: {
            const int dmg = calculateCardDamage(c, -1, up ? 14 : 10);
            addToBot( Actions::AttackAllEnemy(dmg) );
            addToBot( Actions::DiscardAction(1, true, false, false) );
            break;
        }

        case CardId::BANE: {
            const int dmg = calculateCardDamage(c, t, up ? 10 : 7);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Action([&](BattleContext &b) {
                if (b.monsters.arr[t].hasStatus<MS::POISON>()) {
                    b.addToTop( Actions::AttackEnemy(t, dmg) );
                }
            }) );
            break;
        }
        
        case CardId::CHOKE: {
            const int dmg = calculateCardDamage(c, t, up ? 17 : 12);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Actions::DebuffEnemy<MS::CHOKED>(t, up ? 5 : 3, false) );
            break;
        }

        case CardId::DAGGER_SPRAY: {
            const int dmg = calculateCardDamage(c, -1, up ? 6 : 4);
            addToBot( Actions::AttackAllEnemy(dmg) );
            addToBot( Actions::AttackAllEnemy(dmg) );
            break;
        }

        case CardId::DAGGER_THROW: {
            const int dmg = calculateCardDamage(c, t, up ? 12 : 9);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Actions::DrawCards(1) );
            addToBot( Actions::DiscardAction(1, false, false, false) );
            break;
        }

        case CardId::DASH: {
            const int b = calculateCardBlock(up ? 13 : 10);
            const int d = calculateCardDamage(c, t, up ? 13 : 10);
            addToBot( Actions::GainBlock(b) );
            addToBot( Actions::AttackEnemy(t, d) );
            break;
        }

        case CardId::DIE_DIE_DIE: {
            const int dmg = calculateCardDamage(c, -1, up ? 17 : 13);
            addToBot( Actions::AttackAllEnemy(dmg) );
            break;
        }

        case CardId::ENDLESS_AGONY: {
            const int dmg = calculateCardDamage(c, t, up ? 6 : 4);
            addToBot( Actions::AttackEnemy(t, dmg) );
            break;
        }

        case CardId::EVISCERATE: {
            const int dmg = calculateCardDamage(c, t, up ? 9 : 7);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Actions::AttackEnemy(t, dmg) );
            break;
        }

        case CardId::FINISHER: {
            const int dmg = calculateCardDamage(c, t, up ? 8 : 6);
            int count = player.cardsPlayedThisTurn; 
            for (int i=0; i<count; ++i) { // actually should only be attacks played. Needs to track attack count, but this works for now. 
               addToBot( Actions::AttackEnemy(t, dmg) );
            }
            break;
        }

        case CardId::FLECHETTES: {
            const int dmg = calculateCardDamage(c, t, up ? 6 : 4);
            addToBot( Action([&](BattleContext &b) {
                int count = 0;
                for (int i=0; i<b.cards.cardsInHand; ++i) {
                    if (b.cards.hand[i].getType() == CardType::SKILL) count++;
                }
                for (int i=0; i<count; ++i) {
                    b.addToTop( Actions::AttackEnemy(t, dmg) );
                }
            }) );
            break;
        }

        case CardId::FLYING_KNEE: {
            const int dmg = calculateCardDamage(c, t, up ? 11 : 8);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Actions::BuffPlayer<PS::ENERGIZED>(1) );
            break;
        }

        case CardId::GLASS_KNIFE: {
            int d = c.misc == 0 ? (up ? 12 : 8) : c.misc;
            if (c.misc == 0) c.misc = d;
            const int dmg = calculateCardDamage(c, t, c.misc);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Action([&](BattleContext &b) {
                for(int i=0; i<b.cards.cardsInHand; ++i) {
                    if (b.cards.hand[i].uniqueId == c.uniqueId) {
                        b.cards.hand[i].misc -= 2;
                    }
                }
            }) );
            break;
        }

        case CardId::GRAND_FINALE: {
            const int dmg = calculateCardDamage(c, -1, up ? 60 : 50);
            addToBot( Actions::AttackAllEnemy(dmg) );
            break;
        }

        case CardId::HEEL_HOOK: {
            const int dmg = calculateCardDamage(c, t, up ? 8 : 5);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Action([&](BattleContext &b) {
                if (b.monsters.arr[t].hasStatus<MS::WEAK>()) {
                    b.addToTop( Actions::DrawCards(1) );
                    b.addToTop( Actions::GainEnergy(1) );
                }
            }) );
            break;
        }

        case CardId::MASTERFUL_STAB: {
            const int dmg = calculateCardDamage(c, t, up ? 16 : 12);
            addToBot( Actions::AttackEnemy(t, dmg) );
            break;
        }

        case CardId::NEUTRALIZE: {
            const int dmg = calculateCardDamage(c, t, up ? 4 : 3);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Actions::DebuffEnemy<MS::WEAK>(t, up ? 2 : 1, false) );
            break;
        }

        case CardId::POISONED_STAB: {
            const int dmg = calculateCardDamage(c, t, up ? 8 : 6);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Actions::DebuffEnemy<MS::POISON>(t, up ? 4 : 3, false) );
            break;
        }

        case CardId::PREDATOR: {
            const int dmg = calculateCardDamage(c, t, up ? 20 : 15);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Actions::BuffPlayer<PS::DRAW_CARD_NEXT_TURN>(2) );
            break;
        }

        case CardId::QUICK_SLASH: {
            const int dmg = calculateCardDamage(c, t, up ? 12 : 8);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Actions::DrawCards(1) );
            break;
        }

        case CardId::RIDDLE_WITH_HOLES: {
            const int dmg = calculateCardDamage(c, t, up ? 4 : 3);
            for(int i=0; i<5; ++i) {
                addToBot( Actions::AttackEnemy(t, dmg) );
            }
            break;
        }

        case CardId::SKEWER: {
            const int dmg = calculateCardDamage(c, t, up ? 10 : 7);
            addToBot( Action([=] (BattleContext &b) {
                int e = item.energyOnUse;
                if (b.player.hasRelic<R::CHEMICAL_X>()) e += 2;
                for (int i=0; i<e; ++i) {
                    b.addToTop( Actions::AttackEnemy(t, dmg) );
                }
            }) );
            break;
        }

        case CardId::SLICE: {
            const int dmg = calculateCardDamage(c, t, up ? 8 : 5);
            addToBot( Actions::AttackEnemy(t, dmg) );
            break;
        }

        case CardId::SNEAKY_STRIKE: {
            const int dmg = calculateCardDamage(c, t, up ? 16 : 12);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Action([=] (BattleContext &b) {
                if (b.player.cardsDiscardedThisTurn > 0) {
                    b.addToTop( Actions::GainEnergy(2) );
                }
            }) );
            break;
        }

        // CardId::STRIKE_GREEN is defined natively in STS lightspeed

        case CardId::SUCKER_PUNCH: {
            const int dmg = calculateCardDamage(c, t, up ? 9 : 7);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Actions::DebuffEnemy<MS::WEAK>(t, up ? 2 : 1, false) );
            break;
        }

        case CardId::UNLOAD: {
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
