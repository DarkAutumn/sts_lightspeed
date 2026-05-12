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

namespace sts {

    class GameContext;
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

        const std::vector<int> cardEncodeMap;
        const std::unordered_map<MonsterEncounter, int> bossEncodeMap;

        static inline NNInterface *theInstance = nullptr;

        NNInterface();

        int getCardIdx(Card c) const;
        std::array<int,observation_space_size> getObservationMaximums() const;
        std::array<int,observation_space_size> getObservation(const GameContext &gc) const;


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

        std::vector<int> getNNMapRepresentation(const Map &map);
        Room getRoomType(const Map &map, int x, int y);
        bool hasEdge(const Map &map, int x, int y, int x2);
    }


}


#endif //STS_LIGHTSPEED_SLAYTHESPIRE_H
