        // ********************* SILENT SKILLS 2 *********************

        case CardId::DOPPELGANGER: {
            int e = item.energyOnUse;
            if (player.hasRelic<R::CHEMICAL_X>()) e += 2;
            if (up) e += 1;
            addToBot( Actions::BuffPlayer<PS::ENERGIZED>(e) );
            addToBot( Actions::BuffPlayer<PS::DRAW_CARD_NEXT_TURN>(e) );
            break;
        }

        case CardId::ESCAPE_PLAN: {
            addToBot( Action([&](BattleContext &b) {
                b.addToTop( Actions::DrawCards(1) );
                // Note: The conditional block should technically be checked after drawing
                // The engine might need a conditional check. Doing rudimentary top evaluation.
            }) );
            addToBot( Action([&](BattleContext &b) {
                if (b.cards.cardsInHand > 0 && b.cards.hand[b.cards.cardsInHand-1].getType() == CardType::SKILL) {
                   b.addToTop( Actions::GainBlock(b.calculateCardBlock(up ? 5 : 3)) );
                }
            }) );
            break;
        }

        case CardId::EXPERTISE: {
            int cap = up ? 7 : 6;
            int h = cards.cardsInHand; // includes itself actually if not removed yet, but draw pile logic handles it
            if (h < cap) {
                addToBot( Actions::DrawCards(cap - h) ); // Draw until cap
            }
            break;
        }

        case CardId::LEG_SWEEP: {
            addToBot( Actions::DebuffEnemy<MS::WEAK>(t, up ? 3 : 2, false) );
            addToBot( Actions::GainBlock(calculateCardBlock(up ? 14 : 11)) );
            break;
        }

        case CardId::MALAISE: {
            int e = item.energyOnUse;
            if (player.hasRelic<R::CHEMICAL_X>()) e += 2;
            if (up) e += 1;
            addToBot( Actions::DebuffEnemy<MS::SHACKLED>(t, e, false) );
            addToBot( Actions::DebuffEnemy<MS::WEAK>(t, e, false) );
            break;
        }

        case CardId::NIGHTMARE: {
            addToBot( Action([&](BattleContext &b) {
                b.openSimpleCardSelectScreen(CardSelectTask::NIGHTMARE, 1);
            }) );
            break;
        }

        case CardId::OUTMANEUVER: {
            addToBot( Actions::BuffPlayer<PS::ENERGIZED>(up ? 3 : 2) );
            break;
        }

        case CardId::PHANTASMAL_KILLER: {
            addToBot( Actions::BuffPlayer<PS::PHANTASMAL>(1) );
            break;
        }

        case CardId::PIERCING_WAIL: {
            addToBot( Actions::DebuffAllEnemy<MS::SHACKLED>(up ? 8 : 6, false) );
            // Note: LOSE_STRENGTH in sts_lightspeed engine is temporary strength down, meaning it regains it end of turn.
            break;
        }

        case CardId::PREPARED: {
            addToBot( Actions::DrawCards(up ? 2 : 1) );
            addToBot( Actions::DiscardAction(up ? 2 : 1, false, false, false) );
            break;
        }

        case CardId::REFLEX: {
            // Handled in onManualDiscard
            break;
        }

        case CardId::SETUP: {
            addToBot( Action([&](BattleContext &b) {
                b.openSimpleCardSelectScreen(CardSelectTask::SETUP, 1);
            }) );
            break;
        }

        case CardId::STORM_OF_STEEL: {
            addToBot( Action([=] (BattleContext &b) {
                int count = b.cards.cardsInHand;
                for (int i=count-1; i>=0; --i) {
                    auto cardDiscarded = b.cards.hand[i];
                    b.cards.removeFromHandAtIdx(i);
                    b.cards.moveToDiscardPile(cardDiscarded);
                    b.onManualDiscard(cardDiscarded);
                }
                b.addToTop( Actions::MakeTempCardInHand( CardId::SHIV, up, count ) );
            }) );
            break;
        }

        case CardId::SURVIVOR: {
            addToBot( Actions::GainBlock(calculateCardBlock(up ? 11 : 8)) );
            addToBot( Actions::DiscardAction(1, false, false, false) );
            break;
        }

        case CardId::TACTICIAN: {
            // Handled in onManualDiscard
            break;
        }

        case CardId::TERROR: {
            addToBot( Actions::DebuffEnemy<MS::VULNERABLE>(t, 99, false) );
            break;
        }
