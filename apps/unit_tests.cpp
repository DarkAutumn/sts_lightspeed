// Phase 3 onward: in-tree C++ unit tests. Builds as an executable that
// exits 0 on success, non-zero on first failure. Wrapped from Python via
// `tests/python/test_cpp_unit_tests.py`.

#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>

#include "constants/Relics.h"
#include "combat/Player.h"
#include "game/Game.h"
#include "game/Map.h"
#include "slaythespire.h"

using namespace sts;

namespace {

int g_failures = 0;
int g_assertions = 0;

#define EXPECT_TRUE(cond, msg) do { \
    ++g_assertions; \
    if (!(cond)) { \
        ++g_failures; \
        std::fprintf(stderr, "FAIL %s:%d: %s (cond: %s)\n", \
                     __FILE__, __LINE__, msg, #cond); \
    } \
} while (0)

#define EXPECT_EQ(a, b, msg) EXPECT_TRUE((a) == (b), msg)

// ----------------------------------------------------------------------------
// X-macro list of every RelicId in the enum. Kept in declaration order;
// must stay in sync with include/constants/Relics.h. If you add a relic
// there, append it here too.
// ----------------------------------------------------------------------------
#define STS_FOR_EACH_RELIC(X) \
    X(AKABEKO) X(ART_OF_WAR) X(BIRD_FACED_URN) X(BLOODY_IDOL) X(BLUE_CANDLE) \
    X(BRIMSTONE) X(CALIPERS) X(CAPTAINS_WHEEL) X(CENTENNIAL_PUZZLE) X(CERAMIC_FISH) \
    X(CHAMPION_BELT) X(CHARONS_ASHES) X(CHEMICAL_X) X(CLOAK_CLASP) X(DARKSTONE_PERIAPT) \
    X(DEAD_BRANCH) X(DUALITY) X(ECTOPLASM) X(EMOTION_CHIP) X(FROZEN_CORE) \
    X(FROZEN_EYE) X(GAMBLING_CHIP) X(GINGER) X(GOLDEN_EYE) X(GREMLIN_HORN) \
    X(HAND_DRILL) X(HAPPY_FLOWER) X(HORN_CLEAT) X(HOVERING_KITE) X(ICE_CREAM) \
    X(INCENSE_BURNER) X(INK_BOTTLE) X(INSERTER) X(KUNAI) X(LETTER_OPENER) \
    X(LIZARD_TAIL) X(MAGIC_FLOWER) X(MARK_OF_THE_BLOOM) X(MEDICAL_KIT) X(MELANGE) \
    X(MERCURY_HOURGLASS) X(MUMMIFIED_HAND) X(NECRONOMICON) X(NILRYS_CODEX) X(NUNCHAKU) \
    X(ODD_MUSHROOM) X(OMAMORI) X(ORANGE_PELLETS) X(ORICHALCUM) X(ORNAMENTAL_FAN) \
    X(PAPER_KRANE) X(PAPER_PHROG) X(PEN_NIB) X(PHILOSOPHERS_STONE) X(POCKETWATCH) \
    X(RED_SKULL) X(RUNIC_CUBE) X(RUNIC_DOME) X(RUNIC_PYRAMID) X(SACRED_BARK) \
    X(SELF_FORMING_CLAY) X(SHURIKEN) X(SNECKO_EYE) X(SNECKO_SKULL) X(SOZU) \
    X(STONE_CALENDAR) X(STRANGE_SPOON) X(STRIKE_DUMMY) X(SUNDIAL) X(THE_ABACUS) \
    X(THE_BOOT) X(THE_SPECIMEN) X(TINGSHA) X(TOOLBOX) X(TORII) \
    X(TOUGH_BANDAGES) X(TOY_ORNITHOPTER) X(TUNGSTEN_ROD) X(TURNIP) X(TWISTED_FUNNEL) \
    X(UNCEASING_TOP) X(VELVET_CHOKER) X(VIOLET_LOTUS) X(WARPED_TONGS) X(WRIST_BLADE) \
    X(BLACK_BLOOD) X(BURNING_BLOOD) X(MEAT_ON_THE_BONE) X(FACE_OF_CLERIC) X(ANCHOR) \
    X(ANCIENT_TEA_SET) X(BAG_OF_MARBLES) X(BAG_OF_PREPARATION) X(BLOOD_VIAL) X(BOTTLED_FLAME) \
    X(BOTTLED_LIGHTNING) X(BOTTLED_TORNADO) X(BRONZE_SCALES) X(BUSTED_CROWN) X(CLOCKWORK_SOUVENIR) \
    X(COFFEE_DRIPPER) X(CRACKED_CORE) X(CURSED_KEY) X(DAMARU) X(DATA_DISK) \
    X(DU_VU_DOLL) X(ENCHIRIDION) X(FOSSILIZED_HELIX) X(FUSION_HAMMER) X(GIRYA) \
    X(GOLD_PLATED_CABLES) X(GREMLIN_VISAGE) X(HOLY_WATER) X(LANTERN) X(MARK_OF_PAIN) \
    X(MUTAGENIC_STRENGTH) X(NEOWS_LAMENT) X(NINJA_SCROLL) X(NUCLEAR_BATTERY) X(ODDLY_SMOOTH_STONE) \
    X(PANTOGRAPH) X(PRESERVED_INSECT) X(PURE_WATER) X(RED_MASK) X(RING_OF_THE_SERPENT) \
    X(RING_OF_THE_SNAKE) X(RUNIC_CAPACITOR) X(SLAVERS_COLLAR) X(SLING_OF_COURAGE) X(SYMBIOTIC_VIRUS) \
    X(TEARDROP_LOCKET) X(THREAD_AND_NEEDLE) X(VAJRA) X(ASTROLABE) X(BLACK_STAR) \
    X(CALLING_BELL) X(CAULDRON) X(CULTIST_HEADPIECE) X(DOLLYS_MIRROR) X(DREAM_CATCHER) \
    X(EMPTY_CAGE) X(ETERNAL_FEATHER) X(FROZEN_EGG) X(GOLDEN_IDOL) X(JUZU_BRACELET) \
    X(LEES_WAFFLE) X(MANGO) X(MATRYOSHKA) X(MAW_BANK) X(MEAL_TICKET) \
    X(MEMBERSHIP_CARD) X(MOLTEN_EGG) X(NLOTHS_GIFT) X(NLOTHS_HUNGRY_FACE) X(OLD_COIN) \
    X(ORRERY) X(PANDORAS_BOX) X(PEACE_PIPE) X(PEAR) X(POTION_BELT) \
    X(PRAYER_WHEEL) X(PRISMATIC_SHARD) X(QUESTION_CARD) X(REGAL_PILLOW) X(SSSERPENT_HEAD) \
    X(SHOVEL) X(SINGING_BOWL) X(SMILING_MASK) X(SPIRIT_POOP) X(STRAWBERRY) \
    X(THE_COURIER) X(TINY_CHEST) X(TINY_HOUSE) X(TOXIC_EGG) X(WAR_PAINT) \
    X(WHETSTONE) X(WHITE_BEAST_STATUE) X(WING_BOOTS) X(CIRCLET) X(RED_CIRCLET)

// Static check: the X-macro list must have the same count as the runtime
// enum (excluding INVALID).
constexpr int kEnumeratedRelicCount =
#define X(name) +1
    STS_FOR_EACH_RELIC(X)
#undef X
    ;
static_assert(kEnumeratedRelicCount == static_cast<int>(RelicId::INVALID),
              "STS_FOR_EACH_RELIC list is out of sync with RelicId enum");

// ---------------------------------------------------------------------------
// Phase 3.2: every RelicId round-trips through Player::setHasRelic<> /
// hasRelic<> and the runtime path agrees with the templated path.
// ---------------------------------------------------------------------------
void test_relic_bits_round_trip() {
    Player p;
    p.curHp = 50;
    p.maxHp = 50;

    // First pass: every relic starts unset and reads as false on both paths.
#define X(name) do { \
        const RelicId r = RelicId::name; \
        EXPECT_TRUE(!p.hasRelic<RelicId::name>(), \
                    "templated hasRelic should be false initially: " #name); \
        EXPECT_TRUE(!p.hasRelicRuntime(r), \
                    "runtime hasRelic should be false initially: " #name); \
    } while (0);
    STS_FOR_EACH_RELIC(X)
#undef X

    // Second pass: set each relic, both paths return true, then clear it.
#define X(name) do { \
        p.setHasRelic<RelicId::name>(true); \
        EXPECT_TRUE(p.hasRelic<RelicId::name>(), \
                    "templated hasRelic should be true after set: " #name); \
        EXPECT_TRUE(p.hasRelicRuntime(RelicId::name), \
                    "runtime hasRelic should be true after set: " #name); \
        p.setHasRelic<RelicId::name>(false); \
        EXPECT_TRUE(!p.hasRelic<RelicId::name>(), \
                    "templated hasRelic should be false after clear: " #name); \
        EXPECT_TRUE(!p.hasRelicRuntime(RelicId::name), \
                    "runtime hasRelic should be false after clear: " #name); \
    } while (0);
    STS_FOR_EACH_RELIC(X)
#undef X

    // Third pass: set all relics at once, every bit reads true.
#define X(name) p.setHasRelic<RelicId::name>(true);
    STS_FOR_EACH_RELIC(X)
#undef X
#define X(name) EXPECT_TRUE(p.hasRelic<RelicId::name>(), \
                            "all-relics: " #name);
    STS_FOR_EACH_RELIC(X)
#undef X
}

// ---------------------------------------------------------------------------
// Phase 3.2 sanity: relicBits segments are wide enough to cover every relic.
// The widening to 3x uint64_t supports up to 192 relics; we have 180.
// ---------------------------------------------------------------------------
void test_relic_bit_segments_cover_enum() {
    constexpr int kMaxBits = 3 * 64;
    static_assert(static_cast<int>(RelicId::INVALID) <= kMaxBits,
                  "RelicId enum exceeds relicBits capacity");
    EXPECT_TRUE(static_cast<int>(RelicId::INVALID) <= kMaxBits,
                "RelicId enum should fit in 3x64 segments");
    EXPECT_TRUE(static_cast<int>(RelicId::RED_CIRCLET) >= 128,
                "RED_CIRCLET should live in segment 2 (>=128)");
}

// ---------------------------------------------------------------------------
// Phase 3.3: NNInterface::observation_space_size must reserve one slot per
// RelicId. Previously hard-coded to 412 (which only covered 178 relic slots)
// and would overflow when CIRCLET (id 178) or RED_CIRCLET (id 179) appeared
// in the relics list.
// ---------------------------------------------------------------------------
void test_observation_space_size_covers_all_relics() {
    constexpr int kHead = 4 /*hp,maxHp,gold,floor*/ + 10 /*boss*/ + 220 /*deck*/;
    EXPECT_EQ(NNInterface::observation_space_size,
              kHead + static_cast<int>(RelicId::INVALID),
              "observation_space_size must equal head + #relics");
    EXPECT_EQ(NNInterface::relicSlotCount,
              static_cast<int>(RelicId::INVALID),
              "relicSlotCount must equal RelicId::INVALID");
    EXPECT_TRUE(kHead + static_cast<int>(RelicId::RED_CIRCLET)
                    < NNInterface::observation_space_size,
                "RED_CIRCLET index must be in-bounds");
}

} // anonymous namespace

int main() {
    test_relic_bits_round_trip();
    test_relic_bit_segments_cover_enum();
    test_observation_space_size_covers_all_relics();
    std::fprintf(stderr, "Ran %d assertions, %d failures.\n",
                 g_assertions, g_failures);
    return g_failures == 0 ? 0 : 1;
}
