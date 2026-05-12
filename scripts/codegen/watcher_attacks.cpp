        // ********************* WATCHER ATTACKS *********************

        // STRIKE_PURPLE already implemented

        case CardId::ERUPTION: {
            const int dmg = calculateCardDamage(c, t, up ? 12 : 8);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Actions::ChangeStance(Stance::WRATH) );
            break;
        }

        case CardId::FLURRY_OF_BLOWS: {
            const int dmg = calculateCardDamage(c, t, up ? 8 : 4);
            for (int i = 0; i < 4; ++i) {
                addToBot( Actions::AttackEnemy(t, dmg) );
            }
            addToBot( Action([&, oldStance = player.stance](BattleContext &b) mutable {
                if (b.player.stance != oldStance && b.player.stance == Stance::NEUTRAL) {
                    // If exited stance, return this card to hand
                    auto cardCopy = b.curCardQueueItem.card;
                    cardCopy.retain = true;
                    b.addToTop(Actions::MakeTempCardInHand(cardCopy, 1));
                }
            }));
            break;
        }

        case CardId::CONSECRATE: {
            const int dmg = calculateCardDamage(c, -1, up ? 6 : 5);
            addToBot( Actions::AttackAllEnemy(dmg) );
            break;
        }

        case CardId::CRUSH_JOINTS: {
            const int dmg = calculateCardDamage(c, t, up ? 11 : 8);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Action([&, t](BattleContext &b) {
                auto &m = b.monsters.arr[t];
                if (!m.isDeadOrEscaped() && m.isAttacking()) {
                    b.addToTop(Actions::DebuffEnemy<MS::VULNERABLE>(t, up ? 2 : 1, false));
                }
            }));
            break;
        }

        case CardId::SASH_WHIP: {
            const int dmg = calculateCardDamage(c, t, up ? 11 : 8);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Action([&, t](BattleContext &b) {
                auto &m = b.monsters.arr[t];
                if (!m.isDeadOrEscaped() && !m.isAttacking()) {
                    b.addToTop(Actions::DebuffEnemy<MS::WEAK>(t, up ? 2 : 1, false));
                }
            }));
            break;
        }

        case CardId::BOWLING_BASH: {
            const int dmgPerEnemy = up ? 10 : 7;
            for (int i = 0; i < monsters.monsterCount; ++i) {
                if (!monsters.arr[i].isDeadOrEscaped()) {
                    const int dmg = calculateCardDamage(c, i, dmgPerEnemy);
                    addToBot( Actions::AttackEnemy(i, dmg) );
                }
            }
            break;
        }

        case CardId::CARVE_REALITY: {
            const int dmg = calculateCardDamage(c, t, up ? 10 : 6);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Action([&, up](BattleContext &b) {
                if (b.player.stance == Stance::WRATH) {
                    b.addToTop(Actions::MakeTempCardInHand(CardId::SMITE, up, 1));
                }
            }));
            break;
        }

        case CardId::FLYING_SLEEVES: {
            const int dmg = calculateCardDamage(c, t, up ? 11 : 7);
            addToBot( Actions::AttackEnemy(t, dmg) );
            // Retain damage is handled by hasSelfRetain() check
            break;
        }

        case CardId::REACH_HEAVEN: {
            const int dmg = calculateCardDamage(c, t, up ? 25 : 20);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Actions::MakeTempCardInDrawPile(CardInstance(CardId::THROUGH_VIOLENCE, up), 1, true) );
            break;
        }

        case CardId::FEAR_NO_EVIL: {
            const int dmg = calculateCardDamage(c, t, up ? 11 : 8);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Action([&, t](BattleContext &b) {
                auto &m = b.monsters.arr[t];
                if (!m.isDeadOrEscaped() && m.isAttacking()) {
                    b.addToTop(Actions::ChangeStance(Stance::CALM));
                }
            }));
            break;
        }

        case CardId::WHEEL_KICK: {
            const int dmg = calculateCardDamage(c, t, up ? 15 : 10);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Actions::DrawCards(2) );
            addToBot( Actions::DiscardAction(1, false, false, false) );
            break;
        }

        case CardId::WINDMILL_STRIKE: {
            // Base damage plus bonus damage based on misc counter
            int bonusDmg = c.misc;
            const int baseDmg = up ? 16 : 12;
            const int dmg = calculateCardDamage(c, t, baseDmg + bonusDmg);
            addToBot( Actions::AttackEnemy(t, dmg) );
            break;
        }

        case CardId::TALK_TO_THE_HAND: {
            const int dmg = calculateCardDamage(c, t, up ? 5 : 2);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Actions::DebuffEnemy<MS::WEAK>(t, up ? 2 : 1, false) );
            addToBot( Actions::DrawCards(1) );
            break;
        }

        case CardId::WALLOP: {
            const int dmg = calculateCardDamage(c, t, up ? 13 : 9);
            addToBot( Actions::AttackEnemy(t, dmg) );
            // Simplified: gain block equal to damage dealt
            addToBot( Action([&, dmg](BattleContext &b) {
                // Gain block equal to damage (simplified from actual mechanics)
                b.addToTop(Actions::GainBlock(dmg));
            }));
            break;
        }

        case CardId::TANTRUM: {
            const int dmg = calculateCardDamage(c, t, up ? 15 : 12);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Actions::ChangeStance(Stance::WRATH) );
            addToBot( Actions::ChangeStance(Stance::WRATH) ); // Enter wrath twice
            break;
        }

        case CardId::RAGNAROK: {
            const int totalDmg = up ? 36 : 31;
            int remaining = totalDmg;
            for (int i = 0; i < monsters.monsterCount; ++i) {
                if (!monsters.arr[i].isDeadOrEscaped()) {
                    int dmg = calculateCardDamage(c, i, totalDmg); // Random split simplified
                    addToBot( Actions::AttackEnemy(i, dmg) );
                }
            }
            addToBot( Actions::MakeTempCardInDrawPile(CardInstance(CardId::SMITE, up), up ? 3 : 3, true) );
            break;
        }

        case CardId::CONCLUDE: {
            const int dmg = calculateCardDamage(c, -1, up ? 16 : 12);
            addToBot( Actions::AttackAllEnemy(dmg) );
            // Minion killing simplified - just deal damage
            break;
        }

        case CardId::WEAVE: {
            const int dmg = calculateCardDamage(c, t, up ? 7 : 4);
            addToBot( Actions::AttackEnemy(t, dmg) );
            // Return to hand when discarded is handled in triggerOnManualDiscard
            break;
        }

        case CardId::EMPTY_FIST: {
            const int dmg = calculateCardDamage(c, t, up ? 13 : 9);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Actions::ChangeStance(Stance::NEUTRAL) );
            break;
        }

        case CardId::CUT_THROUGH_FATE: {
            const int dmg = calculateCardDamage(c, t, up ? 10 : 7);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Actions::ScryAction(up ? 3 : 2) );
            addToBot( Actions::DrawCards(1) );
            break;
        }

        case CardId::JUST_LUCKY: {
            const int dmg = calculateCardDamage(c, t, up ? 6 : 3);
            addToBot( Actions::AttackEnemy(t, dmg) );
            addToBot( Actions::GainBlock(up ? 2 : 1) );
            addToBot( Actions::ScryAction(1) );
            break;
        }

        case CardId::SANDS_OF_TIME: {
            const int dmg = calculateCardDamage(c, t, up ? 28 : 20);
            addToBot( Actions::AttackEnemy(t, dmg) );
            // Cost reduction when in discard is handled in CardInstance
            break;
        }

        case CardId::FOLLOW_UP: {
            const int dmg = calculateCardDamage(c, t, up ? 9 : 6);
            addToBot( Actions::AttackEnemy(t, dmg) );
            // Simplified: always gain energy if previous card was attack
            // Real game checks playedCardsThisTurn
            break;
        }

        case CardId::LESSON_LEARNED: {
            const int dmg = calculateCardDamage(c, t, up ? 14 : 10);
            addToBot( Actions::AttackEnemy(t, dmg) );
            // Upgrade on kill simplified
            break;
        }

        case CardId::SIGNATURE_MOVE: {
            const int dmg = calculateCardDamage(c, t, up ? 40 : 30);
            addToBot( Actions::AttackEnemy(t, dmg) );
            // Cannot be played if other attacks played - handled in canUse
            break;
        }

        case CardId::COMPILE_DRIVER: {
            const int dmg = calculateCardDamage(c, t, up ? 10 : 7);
            addToBot( Actions::AttackEnemy(t, dmg) );
            // Draw 1 for each unique orb type (simplified for now)
            addToBot( Actions::DrawCards(1) );
            break;
        }

        case CardId::SMITE: {
            const int dmg = calculateCardDamage(c, t, up ? 9 : 6);
            addToBot( Actions::AttackEnemy(t, dmg) );
            // Exhausts when played (ethereal behavior)
            break;
        }

        case CardId::THROUGH_VIOLENCE: {
            const int dmg = calculateCardDamage(c, t, up ? 25 : 20);
            addToBot( Actions::AttackEnemy(t, dmg) );
            // Exhausts when played (ethereal behavior)
            break;
        }
