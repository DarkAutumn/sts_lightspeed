        // ********************* WATCHER SKILLS *********************

        // DEFEND_PURPLE already implemented

        case CardId::VIGILANCE: {
            addToBot( Actions::GainBlock(calculateCardBlock(up ? 16 : 12)) );
            addToBot( Actions::ChangeStance(Stance::CALM) );
            break;
        }

        case CardId::MEDITATE: {
            // Simplified: just gain mantra
            addToBot( Actions::BuffPlayer<PS::MANTRA>(up ? 2 : 1) );
            // Full implementation would put a card from discard to hand with retain
            break;
        }

        case CardId::PROSTRATE: {
            addToBot( Actions::BuffPlayer<PS::MANTRA>(up ? 2 : 1) );
            addToBot( Actions::GainBlock(up ? 6 : 4) );
            break;
        }

        case CardId::BLASPHEMY: {
            addToBot( Actions::ChangeStance(Stance::DIVINITY) );
            addToBot( Action([&](BattleContext &b) {
                b.player.buff<PS::BLASPHEMY>(1);
            }));
            break;
        }

        case CardId::TRANQUILITY: {
            addToBot( Actions::ChangeStance(Stance::CALM) );
            // Exhausts when played (ethereal behavior)
            break;
        }

        case CardId::EVALUATE: {
            addToBot( Actions::DrawCards(1) );
            addToBot( Actions::MakeTempCardInDrawPile(CardInstance(CardId::INSIGHT, up), 1, true) );
            break;
        }

        case CardId::WORSHIP: {
            addToBot( Actions::BuffPlayer<PS::MANTRA>(up ? 6 : 5) );
            break;
        }

        case CardId::THIRD_EYE: {
            addToBot( Actions::ScryAction(up ? 5 : 3) );
            addToBot( Actions::GainBlock(up ? 6 : 4) );
            break;
        }

        case CardId::INNER_PEACE: {
            addToBot( Action([&, up](BattleContext &b) {
                if (b.player.stance == Stance::CALM) {
                    b.addToTop(Actions::DrawCards(3));
                } else {
                    b.addToTop(Actions::ChangeStance(Stance::CALM));
                }
            }));
            break;
        }

        case CardId::SWIVEL: {
            addToBot( Actions::GainBlock(calculateCardBlock(up ? 16 : 12)) );
            addToBot( Action([&](BattleContext &b) {
                b.player.buff<PS::FREE_ATTACK_POWER>(1);
            }));
            break;
        }

        case CardId::PRAY: {
            addToBot( Actions::BuffPlayer<PS::MANTRA>(up ? 4 : 3) );
            // BLESSING card doesn't exist in this implementation, skip adding it
            // addToBot( Actions::MakeTempCardInDrawPile(CardInstance(CardId::BLESSING, up), 1, true) );
            break;
        }

        case CardId::SIMMERING_FURY: {
            addToBot( Action([&, up](BattleContext &b) {
                b.player.buff<PS::SIMMERING_FURY>(1);
            }));
            break;
        }

        case CardId::DECEIVE_REALITY: {
            addToBot( Actions::ChangeStance(Stance::WRATH) );
            addToBot( Actions::MakeTempCardInDrawPile(CardInstance(CardId::INSIGHT, up), 1, true) );
            break;
        }

        case CardId::JUDGMENT: {
            addToBot( Action([&, up](BattleContext &b) {
                // Exhaust a card costing 2 or less
                // For now, simplified: exhaust cheapest card in hand
                int maxCost = up ? 3 : 2;
                for (int i = 0; i < b.cards.cardsInHand; ++i) {
                    if (b.cards.hand[i].cost <= maxCost) {
                        b.addToTop(Actions::ExhaustSpecificCardInHand(i, b.cards.hand[i].getUniqueId()));
                        break;
                    }
                }
            }));
            break;
        }

        case CardId::WAVE_OF_THE_HAND: {
            const int block = cards.cardsInHand;
            addToBot( Actions::GainBlock(block) );
            break;
        }

        case CardId::SCRAWL: {
            addToBot( Action([&](BattleContext &b) {
                int cardsToDraw = 10 - b.cards.cardsInHand;
                if (cardsToDraw > 0) {
                    b.addToTop(Actions::DrawCards(cardsToDraw));
                }
            }));
            break;
        }

        case CardId::SANCTITY: {
            // Simplified: just gain block
            addToBot( Actions::GainBlock(up ? 9 : 6) );
            // Full implementation checks if previous card was a skill
            break;
        }

        case CardId::SPIRIT_SHIELD: {
            addToBot( Action([&, up](BattleContext &b) {
                b.player.buff<PS::SPIRIT_SHIELD>(up ? 2 : 1);
            }));
            break;
        }

        case CardId::HALT: {
            addToBot( Action([&, up](BattleContext &b) {
                int block = up ? 5 : 3;
                if (b.player.stance == Stance::WRATH) {
                    block += up ? 13 : 9;
                }
                b.addToTop(Actions::GainBlock(block));
            }));
            break;
        }

        case CardId::PROTECT: {
            addToBot( Actions::GainBlock(calculateCardBlock(up ? 16 : 12)) );
            break;
        }

        case CardId::ALPHA: {
            addToBot( Actions::MakeTempCardInDrawPile(CardInstance(CardId::BETA, up), 1, true) );
            break;
        }

        case CardId::BETA: {
            addToBot( Actions::MakeTempCardInDrawPile(CardInstance(CardId::OMEGA, up), 1, true) );
            break;
        }

        case CardId::WISH: {
            addToBot( Action([&, up](BattleContext &b) {
                // Simplified: always choose deal damage option
                // Real game offers: 6 energy, 30 damage, 30 block, or 3 Smite
                int damage = up ? 45 : 30;
                for (int i = 0; i < b.monsters.monsterCount; ++i) {
                    if (!b.monsters.arr[i].isDeadOrEscaped()) {
                        b.addToTop(Actions::DamageEnemy(i, damage));
                    }
                }
            }));
            break;
        }

        case CardId::DEUS_EX_MACHINA: {
            addToBot( Actions::GainEnergy(up ? 3 : 2) );
            addToBot( Actions::MakeTempCardInDrawPile(CardInstance(CardId::MIRACLE, up), up ? 3 : 2, true) );
            break;
        }

        case CardId::CONJURE_BLADE: {
            addToBot( Action([&, up](BattleContext &b) {
                // Create a scaling card (simplified)
                auto blade = CardInstance(CardId::SHIV, up);
                blade.misc = up ? 6 : 3;
                b.addToTop(Actions::MakeTempCardInDrawPile(blade, 1, true));
            }));
            break;
        }

        case CardId::OMNISCIENCE: {
            // Simplified: just draw and play a card
            addToBot( Actions::DrawCards(1) );
            // Full implementation plays a card from draw pile twice
            break;
        }

        case CardId::FOREIGN_INFLUENCE: {
            addToBot( Action([&, up](BattleContext &b) {
                // Add a random attack to top of draw pile (simplified)
                auto attack = CardInstance(CardId::STRIKE_RED, up);
                b.addToTop(Actions::MakeTempCardInDrawPile(attack, 1, false));
            }));
            break;
        }

        case CardId::CRESCENDO: {
            addToBot( Actions::ChangeStance(Stance::WRATH) );
            break;
        }

        case CardId::INDIGNATION: {
            addToBot( Action([&, up](BattleContext &b) {
                if (b.player.stance == Stance::WRATH) {
                    for (int i = 0; i < b.monsters.monsterCount; ++i) {
                        if (!b.monsters.arr[i].isDeadOrEscaped()) {
                            b.addToTop(Actions::DebuffEnemy<MS::VULNERABLE>(i, up ? 4 : 3, false));
                        }
                    }
                } else {
                    b.addToTop(Actions::ChangeStance(Stance::WRATH));
                }
            }));
            break;
        }

        case CardId::EMPTY_MIND: {
            addToBot( Actions::DrawCards(2) );
            addToBot( Action([&, up](BattleContext &b) {
                if (b.player.stance == Stance::NEUTRAL) {
                    b.addToTop(Actions::GainEnergy(1));
                }
            }));
            break;
        }

        case CardId::EMPTY_BODY: {
            addToBot( Actions::GainBlock(calculateCardBlock(up ? 11 : 7)) );
            addToBot( Action([&](BattleContext &b) {
                if (b.player.stance == Stance::NEUTRAL) {
                    b.addToTop(Actions::DrawCards(1));
                }
            }));
            break;
        }

        case CardId::PERSEVERANCE: {
            // Block bonus stored in misc
            int bonusBlock = c.misc;
            addToBot( Actions::GainBlock(calculateCardBlock(up ? 8 : 4) + bonusBlock) );
            break;
        }

        case CardId::PRESSURE_POINTS: {
            addToBot( Action([&, up](BattleContext &b) {
                int marks = up ? 11 : 8;
                for (int i = 0; i < b.monsters.monsterCount; ++i) {
                    if (!b.monsters.arr[i].isDeadOrEscaped()) {
                        b.addToTop(Actions::DebuffEnemy<MS::MARK>(i, marks, false));
                    }
                }
            }));
            break;
        }

        case CardId::VAULT: {
            addToBot( Action([&](BattleContext &b) {
                b.player.buff<PS::EXTRA_TURN>(1);
            }));
            break;
        }

        case CardId::MIRACLE: {
            addToBot( Actions::GainEnergy(1) );
            // Exhausts when played
            break;
        }

        case CardId::INSIGHT: {
            addToBot( Actions::DrawCards(1) );
            // Exhausts when played
            break;
        }

        // BLESSING card doesn't exist - case removed
