        // ********************* SILENT SKILLS 1 *********************

        case CardId::ACROBATICS: {
            addToBot( Actions::DrawCards(up ? 4 : 3) );
            addToBot( Actions::DiscardAction(1, false, false, false) );
            break;
        }

        case CardId::ADRENALINE: {
            addToBot( Actions::GainEnergy(up ? 2 : 1) );
            addToBot( Actions::DrawCards(2) );
            break;
        }

        case CardId::ALCHEMIZE: {
            addToBot( Actions::DrawCards(0) /* Potion gen not implemented */ ); // random
            break;
        }

        case CardId::BACKFLIP: {
            addToBot( Actions::GainBlock(calculateCardBlock(up ? 8 : 5)) );
            addToBot( Actions::DrawCards(2) );
            break;
        }

        case CardId::BLADE_DANCE: {
            addToBot( Actions::MakeTempCardInHand(CardId::SHIV, false, up ? 4 : 3) );
            break;
        }

        case CardId::BLUR: {
            addToBot( Actions::GainBlock(calculateCardBlock(up ? 8 : 5)) );
            addToBot( Actions::BuffPlayer<PS::BLUR>(1) );
            break;
        }

        case CardId::BOUNCING_FLASK: {
            for (int i=0; i < (up ? 4 : 3); ++i) {
                addToBot( Action([](BattleContext &b) { int r = b.monsters.getRandomMonsterIdx(b.cardRandomRng, true); if (r != -1) b.addToTop(Actions::DebuffEnemy<MS::POISON>(r, 3, false)); }) );
            }
            break;
        }

        case CardId::BURST: {
            addToBot( Actions::BuffPlayer<PS::BURST>(up ? 2 : 1) );
            break;
        }

        case CardId::CALCULATED_GAMBLE: {
            addToBot( Action([=] (BattleContext &b) {
                int count = b.cards.cardsInHand;
                for (int i=count-1; i>=0; --i) {
                    if (b.cards.hand[i].uniqueId != c.uniqueId) { // discard all EXCEPT this card
                        auto cardDiscarded = b.cards.hand[i];
                        b.cards.removeFromHandAtIdx(i);
                        b.cards.moveToDiscardPile(cardDiscarded);
                        b.onManualDiscard(cardDiscarded);
                    }
                }
                b.addToTop( Actions::DrawCards( count - 1 ) ); // -1 to not count itself
            }) );
            break;
        }

        case CardId::CATALYST: {
            addToBot( Action([&](BattleContext &b) {
                if (b.monsters.arr[t].hasStatus<MS::POISON>()) {
                    int p = b.monsters.arr[t].getStatus<MS::POISON>();
                    b.addToTop( Actions::DebuffEnemy<MS::POISON>(t, p * (up ? 2 : 1), false) ); // Doubles or triples
                }
            }) );
            break;
        }

        case CardId::CLOAK_AND_DAGGER: {
            addToBot( Actions::GainBlock(calculateCardBlock(6)) );
            addToBot( Actions::MakeTempCardInHand(CardId::SHIV, false, up ? 2 : 1) );
            break;
        }

        case CardId::CORPSE_EXPLOSION: {
            addToBot( Actions::DebuffEnemy<MS::POISON>(t, up ? 9 : 6, false) );
            addToBot( Actions::DebuffEnemy<MS::CORPSE_EXPLOSION>(t, 1, false) );
            break;
        }

        case CardId::CRIPPLING_CLOUD: {
            addToBot( Actions::DebuffAllEnemy<MS::POISON>(up ? 7 : 4, false) );
            addToBot( Actions::DebuffAllEnemy<MS::WEAK>(2, false) );
            break;
        }

        case CardId::DEADLY_POISON: {
            addToBot( Actions::DebuffEnemy<MS::POISON>(t, up ? 7 : 5, false) );
            break;
        }

        // CardId::DEFEND_GREEN is defined natively in STS lightspeed

        case CardId::DEFLECT: {
            addToBot( Actions::GainBlock(calculateCardBlock(up ? 7 : 4)) );
            break;
        }

        case CardId::DISTRACTION: {
            addToBot( Actions::MakeTempCardInHand(CardId::INVALID, up, 1) ); // Needs to be random Skill
            break;
        }

        case CardId::DODGE_AND_ROLL: {
            const int block = calculateCardBlock(up ? 6 : 4);
            addToBot( Actions::GainBlock(block) );
            addToBot( Actions::BuffPlayer<PS::NEXT_TURN_BLOCK>(block) );
            break;
        }
