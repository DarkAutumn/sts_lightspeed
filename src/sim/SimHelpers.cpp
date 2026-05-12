//
// Created by keega on 9/14/2021.
//

#include <sim/SimHelpers.h>

using namespace sts;

SimHelpers &SimHelpers::getInstance() {
    // Meyers singleton — C++11 guarantees thread-safe one-shot init of
    // function-local statics. Replaces the previous unsynchronized
    // `if (theInstance == nullptr) theInstance = new SimHelpers()`
    // pattern which raced under the free-threaded Python build (the
    // pybind module is mod_gil_not_used; concurrent threads can hit
    // any of the SimHelpers::get*ForString accessors simultaneously).
    static SimHelpers instance;
    return instance;
}

SimHelpers::SimHelpers() {
    for (int i = static_cast<int>(MMID::INVALID); i <= static_cast<int>(MMID::WRITHING_MASS_STRONG_STRIKE); ++i) {
        const auto stringKey = monsterMoveStrings[i];
        const auto move = static_cast<MonsterMoveId>(i);
        monsterMoveStringMap.insert({stringKey, move});
    }

    for (int i = static_cast<int>(MS::ARTIFACT); i <= static_cast<int>(MS::INVALID); ++i) {
        const auto stringKey = monsterStatusEnumStrings[i];
        const auto status = static_cast<MonsterStatus>(i);
        monsterStatusStringMap.insert({stringKey, status});
    }

    for (int i = static_cast<int>(MonsterId::INVALID); i <= static_cast<int>(MonsterId::WRITHING_MASS); ++i) {
        const auto stringKey = monsterIdStrings[i];
        const auto id = static_cast<MonsterId>(i);
        monsterIdStringMap.insert({stringKey, id});
    }

    for (int i = static_cast<int>(PS::INVALID); i <= static_cast<int>(PS::THE_BOMB); ++i) {
        const auto stringKey = playerStatusEnumStrings[i];
        const auto id = static_cast<PlayerStatus>(i);
        playerStatusStringMap.insert({stringKey, id});
    }

    for (int i = static_cast<int>(CardId::INVALID); i <= static_cast<int>(CardId::ZAP); ++i) {
        const auto stringKey = cardEnumStrings[i];
        const auto id = static_cast<CardId>(i);
        cardIdStringMap.insert({stringKey, id});
    }
}

MonsterId SimHelpers::getMonsterIdForString(const std::string &s) {
    auto &inst = getInstance();
    auto it = inst.monsterIdStringMap.find(s);
    if (it != inst.monsterIdStringMap.end()) {
        return it->second;
    }
    return MonsterId::INVALID;
}

MonsterStatus SimHelpers::getMonsterStatusForString(const std::string &s) {
    auto &inst = getInstance();
    auto it = inst.monsterStatusStringMap.find(s);
    if (it != inst.monsterStatusStringMap.end()) {
        return it->second;
    }
    return MonsterStatus::INVALID;
}

MonsterMoveId SimHelpers::getMonsterMoveForString(const std::string &s) {
    auto &inst = getInstance();
    auto it = inst.monsterMoveStringMap.find(s);
    if (it != inst.monsterMoveStringMap.end()) {
        return it->second;
    }
    return MonsterMoveId::INVALID;
}

PlayerStatus SimHelpers::getPlayerStatusForString(const std::string &s) {
    auto &inst = getInstance();
    auto it = inst.playerStatusStringMap.find(s);
    if (it != inst.playerStatusStringMap.end()) {
        return it->second;
    }
    return PlayerStatus::INVALID;
}

CardId SimHelpers::getCardIdForString(const std::string &s) {
    auto &inst = getInstance();
    auto it = inst.cardIdStringMap.find(s);
    if (it != inst.cardIdStringMap.end()) {
        return it->second;
    }
    return CardId::INVALID;
}
