//
// Created by keega on 9/24/2021.
//
#include <sstream>
#include <algorithm>

#include "sim/ConsoleSimulator.h"
#include "sim/search/ScumSearchAgent2.h"
#include "sim/SimHelpers.h"
#include "sim/PrintHelpers.h"
#include "game/Game.h"
#include "game/Map.h"
#include "combat/BattleContext.h"
#include "combat/Player.h"
#include "combat/Monster.h"
#include "combat/MonsterGroup.h"
#include "combat/CardManager.h"
#include "constants/MonsterStatusEffects.h"

#include "slaythespire.h"

namespace sts {

    NNInterface::NNInterface() :
            cardEncodeMap(createOneHotCardEncodingMap()),
            bossEncodeMap(createBossEncodingMap()) {}

    int NNInterface::getCardIdx(Card c) const {
        int idx = cardEncodeMap[static_cast<int>(c.id)] * 2;
        if (idx == -1) {
            std::cerr << "attemped to get encoding idx for invalid card" << std::endl;
            assert(false);
        }

        if (c.isUpgraded()) {
            idx += 1;
        }

        return idx;
    }

    std::array<int,NNInterface::observation_space_size> NNInterface::getObservation(const GameContext &gc) const {
        std::array<int,observation_space_size> ret {};

        int offset = 0;

        ret[offset++] = std::min(gc.curHp, playerHpMax);
        ret[offset++] = std::min(gc.maxHp, playerHpMax);
        ret[offset++] = std::min(gc.gold, playerGoldMax);
        ret[offset++] = gc.floorNum;

        int bossEncodeIdx = offset + bossEncodeMap.at(gc.boss);
        ret[bossEncodeIdx] = 1;
        offset += 10;

        for (auto c : gc.deck.cards) {
            int encodeIdx = offset + getCardIdx(c);
            ret[encodeIdx] = std::min(ret[encodeIdx]+1, cardCountMax);
        }
        offset += 220;

        for (auto r : gc.relics.relics) {
            int encodeIdx = offset + static_cast<int>(r.id);
            ret[encodeIdx] = 1;
        }
        offset += relicSlotCount;

        return ret;
    }

    std::array<int,NNInterface::observation_space_size> NNInterface::getObservationMaximums() const {
        std::array<int,observation_space_size> ret {};
        int spaceOffset = 0;

        ret[0] = playerHpMax;
        ret[1] = playerHpMax;
        ret[2] = playerGoldMax;
        ret[3] = 60;
        spaceOffset += 4;

        std::fill(ret.begin()+spaceOffset, ret.begin()+spaceOffset+10, 1);
        spaceOffset += 10;

        std::fill(ret.begin()+spaceOffset, ret.begin()+spaceOffset+220, cardCountMax);
        spaceOffset += 220;

        std::fill(ret.begin()+spaceOffset, ret.begin()+spaceOffset+relicSlotCount, 1);
        spaceOffset += relicSlotCount;

        return ret;
    }

    std::vector<int> NNInterface::createOneHotCardEncodingMap() {
        std::vector<CardId> redCards;
        for (int i = static_cast<int>(CardId::INVALID); i <= static_cast<int>(CardId::ZAP); ++i) {
            auto cid = static_cast<CardId>(i);
            auto color = getCardColor(cid);
            if (color == CardColor::RED) {
                redCards.push_back(cid);
            }
        }

        std::vector<CardId> colorlessCards;
        for (int i = 0; i < srcColorlessCardPoolSize; ++i) {
            colorlessCards.push_back(srcColorlessCardPool[i]);
        }
        std::sort(colorlessCards.begin(), colorlessCards.end(), [](auto a, auto b) {
            return std::string(getCardEnumName(a)) < std::string(getCardEnumName(b));
        });

        std::vector<int> encodingMap(372);
        std::fill(encodingMap.begin(), encodingMap.end(), 0);

        int hotEncodingIdx = 0;
        for (auto x : redCards) {
            encodingMap[static_cast<int>(x)] = hotEncodingIdx++;
        }
        for (auto x : colorlessCards) {
            encodingMap[static_cast<int>(x)] = hotEncodingIdx++;
        }

        return encodingMap;
    }

    std::unordered_map<MonsterEncounter, int> NNInterface::createBossEncodingMap() {
        std::unordered_map<MonsterEncounter, int> bossMap;
        bossMap[ME::SLIME_BOSS] = 0;
        bossMap[ME::HEXAGHOST] = 1;
        bossMap[ME::THE_GUARDIAN] = 2;
        bossMap[ME::CHAMP] = 3;
        bossMap[ME::AUTOMATON] = 4;
        bossMap[ME::COLLECTOR] = 5;
        bossMap[ME::TIME_EATER] = 6;
        bossMap[ME::DONU_AND_DECA] = 7;
        bossMap[ME::AWAKENED_ONE] = 8;
        bossMap[ME::THE_HEART] = 9;
        return bossMap;
    }

    std::array<int, NNInterface::battle_observation_size>
    NNInterface::encodeBattle(const GameContext &gc, const BattleContext &bc) const {
        std::array<int, battle_observation_size> ret {};
        int offset = 0;

        const Player &p = bc.player;

        // --- 8 player core ---
        ret[offset++] = std::max(0, p.curHp);
        ret[offset++] = std::max(0, p.maxHp);
        ret[offset++] = std::max(0, p.block);
        ret[offset++] = std::max(0, static_cast<int>(p.energy));
        ret[offset++] = p.strength;
        ret[offset++] = p.dexterity;
        ret[offset++] = p.focus;
        ret[offset++] = p.artifact;

        // --- 8 player meta ---
        int hpPct = (p.maxHp > 0)
            ? std::min(100, (100 * std::max(0, p.curHp)) / p.maxHp)
            : 0;
        ret[offset++] = hpPct;
        // stance one-hot over 4 (NEUTRAL, WRATH, CALM, DIVINITY)
        {
            int stanceIdx = static_cast<int>(p.stance);
            if (stanceIdx >= 0 && stanceIdx < 4) {
                ret[offset + stanceIdx] = 1;
            }
        }
        offset += 4;
        ret[offset++] = p.orbSlots;
        ret[offset++] = bc.monsterTurnIdx;
        ret[offset++] = static_cast<int>(p.energyPerTurn);

        // --- numStatuses ---
        // Phase 7 review-fix: iterate ALL PlayerStatus values, not just
        // statusMap. Several real combat-affecting statuses are stored in
        // bit-fields outside statusMap (BARRICADE, CORRUPTION, CONFUSED,
        // PEN_NIB, SURROUNDED, ...). We can't call `getStatusRuntime`
        // directly here because it calls `statusMap.at(s)` for the default
        // branch and that throws for bit-only statuses (a latent bug in
        // Player::getStatusRuntime — out of scope for Phase 7). So
        // hand-roll the lookup: statusMap value wins, else 1 if the bit is
        // set, else 0.
        for (int sIdx = 0; sIdx < numStatuses; ++sIdx) {
            auto s = static_cast<PlayerStatus>(sIdx);
            auto it = p.statusMap.find(s);
            if (it != p.statusMap.end()) {
                ret[offset + sIdx] = it->second;
            } else if (p.hasStatusRuntime(s)) {
                // Bit-only boolean status (BARRICADE, etc.). Encode as 1.
                // Note: STRENGTH/DEX/FOCUS/ARTIFACT are already encoded in
                // player core; hasStatusRuntime returns truthy for those
                // too, so they'll get an extra slot here as well, which is
                // fine for an RL observation (redundant signal, no
                // ambiguity).
                ret[offset + sIdx] = 1;
            }
        }
        offset += numStatuses;

        // --- hand (10 positional slots × numCards*2 one-hot) ---
        // Phase 7 review-fix: index by raw CardId value, not the
        // legacy `cardEncodeMap`. The map in
        // `createOneHotCardEncodingMap()` only assigns slots to red +
        // colorless cards (used by the meta-state getObservation for
        // the out-of-battle deck encoding, which is Ironclad-only). For
        // the battle encoder we need all four characters' cards to
        // have distinct slots, so we use the raw enum value scaled by
        // upgrade bit.
        auto cardInstanceBattleIdx = [&](const CardInstance &ci) -> int {
            int id = static_cast<int>(ci.id);
            if (id < 0 || id >= numCards) return -1;
            return id * 2 + (ci.isUpgraded() ? 1 : 0);
        };
        for (int slot = 0; slot < handPositions; ++slot) {
            if (slot < bc.cards.cardsInHand) {
                int idx = cardInstanceBattleIdx(bc.cards.hand[slot]);
                if (idx >= 0 && idx < numCards * 2) {
                    ret[offset + idx] = 1;
                }
            }
            offset += numCards * 2;
        }

        // --- draw / discard / exhaust count vectors ---
        auto encodePileCounts = [&](const std::vector<CardInstance> &pile) {
            for (const auto &c : pile) {
                int idx = cardInstanceBattleIdx(c);
                if (idx >= 0 && idx < numCards * 2) {
                    ret[offset + idx] = std::min(ret[offset + idx] + 1, 30);
                }
            }
            offset += numCards * 2;
        };
        encodePileCounts(bc.cards.drawPile);
        encodePileCounts(bc.cards.discardPile);
        encodePileCounts(bc.cards.exhaustPile);

        // --- potions one-hot (over numPotions slots) ---
        for (int i = 0; i < gc.potionCount; ++i) {
            int potIdx = static_cast<int>(gc.potions[i]);
            if (potIdx >= 0 && potIdx < numPotions) {
                ret[offset + potIdx] = 1;
            }
        }
        offset += numPotions;

        // --- relic one-hot (out-of-battle layout) ---
        for (auto r : gc.relics.relics) {
            int rIdx = static_cast<int>(r.id);
            if (rIdx >= 0 && rIdx < relicSlotCount) {
                ret[offset + rIdx] = 1;
            }
        }
        offset += relicSlotCount;

        // --- 5 monster slots ---
        for (int i = 0; i < maxMonsters; ++i) {
            const Monster *m = (i < bc.monsters.monsterCount) ? &bc.monsters.arr[i] : nullptr;
            if (m != nullptr && !m->isDeadOrEscaped()) {
                ret[offset + 0] = std::max(0, m->curHp);
                ret[offset + 1] = std::max(0, m->maxHp);
                ret[offset + 2] = std::max(0, m->block);
            }
            offset += 3;

            if (m != nullptr && !m->isDeadOrEscaped()) {
                for (int s = 0; s < monsterStatusCount; ++s) {
                    auto ms = static_cast<MonsterStatus>(s);
                    ret[offset + s] = m->getStatusInternal(ms);
                }
            }
            offset += monsterStatusCount;

            if (m != nullptr && !m->isDeadOrEscaped()) {
                int mid = static_cast<int>(m->id);
                if (mid >= 0 && mid < numMonsterIds) {
                    ret[offset + mid] = 1;
                }
            }
            offset += numMonsterIds;

            if (m != nullptr && !m->isDeadOrEscaped()) {
                MMID nextMove = m->moveHistory[0];
                bool isAttack = isMoveAttack(nextMove);
                ret[offset + 0] = isAttack ? 1 : 0;
                if (isAttack) {
                    DamageInfo dmg = m->getMoveBaseDamage(bc);
                    ret[offset + 1] = dmg.attackCount;
                    ret[offset + 2] = m->calculateDamageToPlayer(bc, dmg.damage);
                }
            }
            offset += 3;
        }

        // sanity: offset should equal battle_observation_size
        assert(offset == battle_observation_size);
        return ret;
    }

    std::array<int, NNInterface::battle_observation_size>
    NNInterface::getBattleObservationMaximums() const {
        std::array<int, battle_observation_size> ret {};
        int offset = 0;

        // player core
        ret[offset++] = playerHpMax;      // curHp
        ret[offset++] = playerHpMax;      // maxHp
        ret[offset++] = 999;              // block
        ret[offset++] = 99;               // energy
        ret[offset++] = 999;              // strength
        ret[offset++] = 999;              // dexterity
        ret[offset++] = 999;              // focus
        ret[offset++] = 999;              // artifact

        // player meta
        ret[offset++] = 100;              // hp pct
        std::fill(ret.begin() + offset, ret.begin() + offset + 4, 1);  // stance
        offset += 4;
        ret[offset++] = 10;               // orbSlots
        ret[offset++] = 99;               // monsterTurnIdx (can transiently
                                          // exceed monsterCount when iterating
                                          // through end-of-round actions)
        ret[offset++] = 99;               // energyPerTurn

        // statuses: arbitrarily generous cap
        std::fill(ret.begin() + offset, ret.begin() + offset + numStatuses, 999);
        offset += numStatuses;

        // hand 10 × numCards*2 (one-hot)
        std::fill(ret.begin() + offset, ret.begin() + offset + numCards * 2 * handPositions, 1);
        offset += numCards * 2 * handPositions;

        // 3 pile count vectors (capped at 30)
        std::fill(ret.begin() + offset, ret.begin() + offset + numCards * 2 * 3, 30);
        offset += numCards * 2 * 3;

        // potions, relics: one-hot
        std::fill(ret.begin() + offset, ret.begin() + offset + numPotions, 1);
        offset += numPotions;
        std::fill(ret.begin() + offset, ret.begin() + offset + relicSlotCount, 1);
        offset += relicSlotCount;

        // monster blocks
        for (int i = 0; i < maxMonsters; ++i) {
            ret[offset++] = playerHpMax * 5;   // monster hp (some bosses > 200)
            ret[offset++] = playerHpMax * 5;   // monster maxHp
            ret[offset++] = 999;               // monster block
            std::fill(ret.begin() + offset, ret.begin() + offset + monsterStatusCount, 999);
            offset += monsterStatusCount;
            std::fill(ret.begin() + offset, ret.begin() + offset + numMonsterIds, 1);
            offset += numMonsterIds;
            ret[offset++] = 1;                 // isAttack
            ret[offset++] = 30;                // attackCount
            ret[offset++] = 999;               // damage
        }

        assert(offset == battle_observation_size);
        return ret;
    }

    NNInterface* NNInterface::getInstance() {
        // Meyers singleton: C++11 guarantees thread-safe initialization
        // of function-local statics. Replaces the previous unsynchronized
        // `if (theInstance == nullptr) theInstance = new NNInterface;`
        // pattern, which raced under the free-threaded Python build
        // (Phase 4 declares the module mod_gil_not_used). The legacy
        // `theInstance` pointer was dropped in the Phase 4 review-fix
        // round because no external code read it.
        static NNInterface instance;
        return &instance;
    }

}

namespace sts::py {

    void play() {
        sts::SimulatorContext ctx;
        sts::ConsoleSimulator sim;
        sim.play(std::cin, std::cout, ctx);
    }

    search::ScumSearchAgent2* getAgent() {
        static search::ScumSearchAgent2 *agent = nullptr;
        if (agent == nullptr) {
            agent = new search::ScumSearchAgent2();
            agent->pauseOnCardReward = true;
        }
        return agent;
    }

    void playout(GameContext &gc) {
        auto agent = getAgent();
        agent->playout(gc);
    }

    std::vector<Card> getCardReward(GameContext &gc) {
        const bool inValidState = gc.outcome == GameOutcome::UNDECIDED &&
                                  gc.screenState == ScreenState::REWARDS &&
                                  gc.info.rewardsContainer.cardRewardCount > 0;

        if (!inValidState) {
            std::cerr << "GameContext was not in a state with card rewards, check that the game has not completed first." << std::endl;
            return {};
        }

        const auto &r = gc.info.rewardsContainer;
        const auto &cardList = r.cardRewards[r.cardRewardCount-1];
        return std::vector<Card>(cardList.begin(), cardList.end());
    }

    void pickRewardCard(GameContext &gc, Card card) {
        const bool inValidState = gc.outcome == GameOutcome::UNDECIDED &&
                                  gc.screenState == ScreenState::REWARDS &&
                                  gc.info.rewardsContainer.cardRewardCount > 0;
        if (!inValidState) {
            std::cerr << "GameContext was not in a state with card rewards, check that the game has not completed first." << std::endl;
            return;
        }
        auto &r = gc.info.rewardsContainer;
        gc.deck.obtain(gc, card);
        r.removeCardReward(r.cardRewardCount-1);
    }

    void skipRewardCards(GameContext &gc) {
        const bool inValidState = gc.outcome == GameOutcome::UNDECIDED &&
                                  gc.screenState == ScreenState::REWARDS &&
                                  gc.info.rewardsContainer.cardRewardCount > 0;
        if (!inValidState) {
            std::cerr << "GameContext was not in a state with card rewards, check that the game has not completed first." << std::endl;
            return;
        }

        if (gc.hasRelic(RelicId::SINGING_BOWL)) {
            gc.playerIncreaseMaxHp(2);
        }

        auto &r = gc.info.rewardsContainer;
        r.removeCardReward(r.cardRewardCount-1);
    }



    // BEGIN MAP THINGS ****************************

    std::vector<int> getNNMapRepresentation(const Map &map) {
        std::vector<int> ret;

        // 7 bits
        // push edges to first row
        for (int x = 0; x < 7; ++x) {
            if (map.getNode(x,0).edgeCount > 0) {
                ret.push_back(true);
            } else {
                ret.push_back(false);
            }
        }

        // for each node in a row, push valid edges to next row, 3 bits per node, 21 bits per row
        // skip 14th row because it is invariant
        // 21 * 13 == 273 bits
        for (int y = 0; y < 14; ++y) {
            for (int x = 0; x < 7; ++x) {

                bool localEdgeValues[3] {false, false, false};
                auto node = map.getNode(x,y);
                for (int i = 0; i < node.edgeCount; ++i) {
                    auto edge = node.edges[i];
                    if (edge < x) {
                        localEdgeValues[0] = true;
                    } else if (edge == x) {
                        localEdgeValues[1] = true;
                    } else {
                        localEdgeValues[2] = true;
                    }
                }
                ret.insert(ret.end(), localEdgeValues, localEdgeValues+3);
            }
        }

        // room types - for each node there are 6 possible rooms,
        // the first row is always monster, the 8th row is always treasure, 14th is always rest
        // this gives 14-3 valid rows == 11
        // 11 * 6 * 7 = 462 bits
        for (int y = 1; y < 14; ++y) {
            if (y == 8) {
                continue;
            }
            for (int x = 0; x < 7; ++x) {
                auto roomType = map.getNode(x,y).room;
                for (int i = 0; i < 6; ++i) {
                    ret.push_back(static_cast<int>(roomType) == i);
                }
            }
        }

        return ret;
    };

    Room getRoomType(const Map &map, int x, int y) {
        if (x < 0 || x > 6 || y < 0 || y > 14) {
            return Room::INVALID;
        }

        return map.getNode(x,y).room;
    }

    bool hasEdge(const Map &map, int x, int y, int x2) {
        if (x == -1) {
            return map.getNode(x2,0).edgeCount > 0;
        }

        if (x < 0 || x > 6 || y < 0 || y > 14) {
            return false;
        }


        auto node = map.getNode(x,y);
        for (int i = 0; i < node.edgeCount; ++i) {
            if (node.edges[i] == x2) {
                return true;
            }
        }
        return false;
    }

}