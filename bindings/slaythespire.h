//
// Created by keega on 9/24/2021.
//

#ifndef STS_LIGHTSPEED_SLAYTHESPIRE_H
#define STS_LIGHTSPEED_SLAYTHESPIRE_H

#include <vector>
#include <unordered_map>
#include <array>

#include "constants/Rooms.h"
#include "constants/Relics.h"
#include "constants/MonsterEncounters.h"
#include "constants/Cards.h"
#include "constants/PlayerStatusEffects.h"
#include "constants/Potions.h"
#include "constants/MonsterIds.h"

namespace sts {

    class GameContext;
    class BattleContext;
    struct Card;

    struct NNInterface {
        // observation_space layout (offsets / widths):
        //   [0]      curHp                                (max playerHpMax)
        //   [1]      maxHp                                (max playerHpMax)
        //   [2]      gold                                 (max playerGoldMax)
        //   [3]      floor                                (max 60)
        //   [4..13]  boss one-hot (10 bosses)             (max 1)
        //   [14..233] deck encoding (220 card slots)      (max cardCountMax)
        //   [234..]   relic one-hot (one slot per RelicId, INVALID-many slots).
        //             RelicId::INVALID is the sentinel "no relic" so the
        //             width is static_cast<int>(RelicId::INVALID) == 180.
        // Prior versions of this code allocated only 178 relic slots, which
        // caused an out-of-bounds write when the player ever held CIRCLET
        // (id 178) or RED_CIRCLET (id 179).
        static constexpr int playerHpMax = 200;
        static constexpr int playerGoldMax = 1800;
        static constexpr int cardCountMax = 7;
        static constexpr int relicSlotCount = static_cast<int>(RelicId::INVALID);
        static constexpr int observation_space_size =
            4 /*hp,maxHp,gold,floor*/ + 10 /*boss*/ + 220 /*deck*/ + relicSlotCount;

        // -------------------------------------------------------------------
        // Battle observation (Phase 7).
        //
        // Adapted from SimoneBarbaro/sts_lightspeed but extended to ben-w-smith's
        // expanded enum surface (more CardIds, more PlayerStatus values, no
        // free-standing `Intent` enum so we encode "is attack move" + damage
        // instead).
        //
        // Layout (each row is a contiguous block of ints in the returned array):
        //   - 8  player core: curHp, maxHp, block, energy, strength, dexterity,
        //         focus, artifact
        //   - 8  player meta: hp ratio*100, stance (one-hot over 4),
        //         orbSlots, lastTargetedMonster, energyPerTurn
        //   - numStatuses  player statuses (one int per PlayerStatus value;
        //         statusMap value at index, or 0)
        //   - numCards*2 * 10  positional hand encoding (hand[0..9], one-hot
        //         over numCards with upgrade-doubling). Empty hand slots
        //         contribute zeros.
        //   - numCards*2       draw pile count vector (counts of each card,
        //         upgrade-doubled)
        //   - numCards*2       discard pile count vector
        //   - numCards*2       exhaust pile count vector
        //   - numPotions  active potion one-hot (one slot per PotionId)
        //   - relicSlotCount  relic one-hot (same as out-of-battle relic layout)
        //   - 5 * monster_block  per-monster: HP/maxHP/block/statuses[13]
        //         /MonsterId one-hot/isAttack/attackCount/damage. Dead or
        //         escaped monsters contribute zeros.
        //
        // The total size is exposed as `battle_observation_size` for tests.
        static constexpr int numCards         = static_cast<int>(CardId::ZAP) + 1;
        static constexpr int numStatuses      = static_cast<int>(PlayerStatus::RETAIN_CARDS) + 1;
        static constexpr int numPotions       = static_cast<int>(Potion::WEAK_POTION) + 1;
        static constexpr int numMonsterIds    = static_cast<int>(MonsterId::WRITHING_MASS) + 1;
        static constexpr int monsterStatusCount = 14;  // ARTIFACT..WEAK in MonsterStatus
                                                       // enum (in order: ARTIFACT,
                                                       // BLOCK_RETURN, CHOKED,
                                                       // CORPSE_EXPLOSION, LOCK_ON,
                                                       // MARK, METALLICIZE, PLATED_ARMOR,
                                                       // POISON, REGEN, SHACKLED,
                                                       // STRENGTH, VULNERABLE, WEAK)
        static constexpr int monsterBlockSize =
            3 /*hp,maxHp,block*/ + monsterStatusCount + numMonsterIds + 3 /*isAttack,attackCount,damage*/;
        static constexpr int maxMonsters      = 5;
        static constexpr int playerCoreSize   = 8;
        static constexpr int playerMetaSize   = 8;
        static constexpr int handPositions    = 10;
        static constexpr int battle_observation_size =
            playerCoreSize + playerMetaSize + numStatuses
            + numCards * 2 * (handPositions + 3)  // hand + 3 piles
            + numPotions + relicSlotCount
            + maxMonsters * monsterBlockSize;

        const std::vector<int> cardEncodeMap;
        const std::unordered_map<MonsterEncounter, int> bossEncodeMap;

        // (Phase 4 review-fix^2) The previous `static inline NNInterface
        // *theInstance` was removed entirely. It was only ever read by
        // `getInstance()`, and writing it from multiple threads after the
        // Meyers singleton initializes is still an unsynchronized data
        // race even when every thread writes the same address.

        NNInterface();

        int getCardIdx(Card c) const;
        std::array<int,observation_space_size> getObservationMaximums() const;
        std::array<int,observation_space_size> getObservation(const GameContext &gc) const;

        // Phase 7 battle encoder.
        std::array<int,battle_observation_size> encodeBattle(const GameContext &gc, const BattleContext &bc) const;
        std::array<int,battle_observation_size> getBattleObservationMaximums() const;

        static std::vector<int> createOneHotCardEncodingMap();
        static std::unordered_map<MonsterEncounter, int> createBossEncodingMap();
        static NNInterface* getInstance();

    };

    namespace search {
        class ScumSearchAgent2;
    }


    class GameContext;
    class Map;

    namespace py {

        void play();

        search::ScumSearchAgent2* getAgent();
        void setGc(const GameContext &gc);
        GameContext* getGc();

        void playout();
        std::vector<Card> getCardReward(GameContext &gc);
        void pickRewardCard(GameContext &gc, Card card);
        void skipRewardCards(GameContext &gc);
        void rollCardReward(GameContext &gc, Room room);

        std::vector<int> getNNMapRepresentation(const Map &map);
        Room getRoomType(const Map &map, int x, int y);
        bool hasEdge(const Map &map, int x, int y, int x2);
    }


}


#endif //STS_LIGHTSPEED_SLAYTHESPIRE_H
