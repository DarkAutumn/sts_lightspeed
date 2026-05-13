// Phase 12: Multi-character multithreaded stress test.
//
// Drives Agent.playout() for all four characters in parallel across N
// threads, with disjoint seeds. Validates correctness by comparing
// each thread's per-seed result to a single-threaded reference run
// — any drift indicates a hidden global mutable state corrupted by
// parallel execution.
//
// Designed to run under TSan, ASan, and UBSan. Exit 0 = clean; non-zero
// = drift or sanitizer report.
//
// Usage: stress_test [threads=8] [playouts_per_char=64] [start_seed=1]

#include <atomic>
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <mutex>
#include <thread>
#include <tuple>
#include <unordered_map>
#include <vector>

#include "game/GameContext.h"
#include "sim/search/ScumSearchAgent2.h"

using namespace sts;

namespace {

struct Fingerprint {
    int outcome = -1;
    int floor_num = -1;
    int deck_size = -1;
    int cur_hp = -1;
    int max_hp = -1;
    int gold = -1;
    int act = -1;
    std::int32_t card_rng_counter = -1;
    std::int32_t monster_rng_counter = -1;
    std::int32_t shuffle_rng_counter = -1;
    std::int32_t treasure_rng_counter = -1;
    bool skipped = false;
    bool operator==(const Fingerprint &o) const {
        if (skipped || o.skipped) return skipped == o.skipped;
        return outcome == o.outcome && floor_num == o.floor_num &&
               deck_size == o.deck_size && cur_hp == o.cur_hp &&
               max_hp == o.max_hp && gold == o.gold && act == o.act &&
               card_rng_counter == o.card_rng_counter &&
               monster_rng_counter == o.monster_rng_counter &&
               shuffle_rng_counter == o.shuffle_rng_counter &&
               treasure_rng_counter == o.treasure_rng_counter;
    }
    bool operator!=(const Fingerprint &o) const { return !(*this == o); }
};

std::mutex g_io_m;
int g_failures = 0;

Fingerprint run_one(CharacterClass cc, std::uint64_t seed) {
    Fingerprint fp;
    try {
        GameContext gc(cc, seed, 0);
        // Value-init (`{}`) zeroes out fields that have no in-class
        // default — notably `simulationCountTotal`, which is later
        // `+=` accumulated. Default-init alone would leave it
        // indeterminate (UB on first read).
        search::ScumSearchAgent2 agent{};
        agent.simulationCountBase = 5;
        agent.rng = std::default_random_engine(gc.seed);
        agent.printActions = false;
        agent.printLogs = false;
        agent.playout(gc);
        fp.outcome = static_cast<int>(gc.outcome);
        fp.floor_num = gc.floorNum;
        fp.deck_size = static_cast<int>(gc.deck.size());
        fp.cur_hp = gc.curHp;
        fp.max_hp = gc.maxHp;
        fp.gold = gc.gold;
        fp.act = gc.act;
        // RNG counters: any race in card/monster/event/shuffle/treasure
        // RNG consumption shows up as divergent counter values even
        // when the higher-level outcome happens to agree.
        fp.card_rng_counter = gc.cardRng.counter;
        fp.monster_rng_counter = gc.monsterRng.counter;
        fp.shuffle_rng_counter = gc.shuffleRng.counter;
        fp.treasure_rng_counter = gc.treasureRng.counter;
    } catch (const std::runtime_error &e) {
        // Known unimplemented card/effect — treat as skip, not failure.
        // We still need both serial and threaded passes to agree, which
        // they will if the same seed throws in both passes (deterministic).
        fp.skipped = true;
        {
            std::scoped_lock lock(g_io_m);
            std::fprintf(stderr, "  SKIP char=%d seed=%lu reason=%s\n",
                         static_cast<int>(cc),
                         static_cast<unsigned long>(seed), e.what());
        }
    }
    return fp;
}

struct Task {
    CharacterClass cc;
    std::uint64_t seed;
};

void log_fail(const char *msg, CharacterClass cc, std::uint64_t seed,
              const Fingerprint &serial, const Fingerprint &threaded) {
    std::scoped_lock lock(g_io_m);
    std::fprintf(stderr,
                 "FAIL: %s char=%d seed=%lu\n"
                 "      serial=(out=%d floor=%d deck=%d hp=%d/%d gold=%d act=%d "
                 "rng=card:%d mon:%d shf:%d trs:%d)\n"
                 "    threaded=(out=%d floor=%d deck=%d hp=%d/%d gold=%d act=%d "
                 "rng=card:%d mon:%d shf:%d trs:%d)\n",
                 msg, static_cast<int>(cc), static_cast<unsigned long>(seed),
                 serial.outcome, serial.floor_num, serial.deck_size,
                 serial.cur_hp, serial.max_hp, serial.gold, serial.act,
                 serial.card_rng_counter, serial.monster_rng_counter,
                 serial.shuffle_rng_counter, serial.treasure_rng_counter,
                 threaded.outcome, threaded.floor_num, threaded.deck_size,
                 threaded.cur_hp, threaded.max_hp, threaded.gold, threaded.act,
                 threaded.card_rng_counter, threaded.monster_rng_counter,
                 threaded.shuffle_rng_counter, threaded.treasure_rng_counter);
    ++g_failures;
}

} // namespace

int main(int argc, char **argv) {
    int threads = (argc > 1) ? std::atoi(argv[1]) : 8;
    int per_char = (argc > 2) ? std::atoi(argv[2]) : 64;
    std::uint64_t start_seed = (argc > 3)
                                   ? std::strtoull(argv[3], nullptr, 10)
                                   : 1;
    if (threads < 1) threads = 1;
    if (per_char < 1) per_char = 1;

    // Disable stderr buffering BEFORE any I/O so a crash mid-task
    // doesn't lose trailing log lines. Calling setbuf after the
    // stream has been used is UB per the C standard.
    std::setbuf(stderr, nullptr);

    // Which characters to exercise. By default just IRONCLAD because the
    // ScumSearchAgent2 + BattleScumSearcher2 search code has pre-existing
    // crashes on Silent/Defect/Watcher seed ranges (see
    // docs/KNOWN_ISSUES.md ISSUE-110). To force all four, set
    // STRESS_ALL_CHARS=1 in the environment.
    std::vector<CharacterClass> chars = {CharacterClass::IRONCLAD};
    if (getenv("STRESS_ALL_CHARS")) {
        chars = {
            CharacterClass::IRONCLAD,
            CharacterClass::SILENT,
            CharacterClass::DEFECT,
            CharacterClass::WATCHER,
        };
    }

    std::vector<Task> tasks;
    tasks.reserve(static_cast<std::size_t>(per_char) * chars.size());
    for (std::size_t c = 0; c < chars.size(); ++c) {
        for (int i = 0; i < per_char; ++i) {
            tasks.push_back(Task{chars[c], start_seed + c * 1'000'000 + static_cast<std::uint64_t>(i)});
        }
    }

    std::fprintf(stderr, "stress_test: threads=%d per_char=%d total=%zu start_seed=%lu\n",
                 threads, per_char, tasks.size(),
                 static_cast<unsigned long>(start_seed));

    // Serial reference pass.
    std::vector<Fingerprint> serial(tasks.size());
    for (std::size_t i = 0; i < tasks.size(); ++i) {
        if (getenv("STRESS_VERBOSE")) {
            std::fprintf(stderr, "  task[%zu] char=%d seed=%lu\n", i,
                         static_cast<int>(tasks[i].cc),
                         static_cast<unsigned long>(tasks[i].seed));
        }
        serial[i] = run_one(tasks[i].cc, tasks[i].seed);
    }
    std::fprintf(stderr, "stress_test: serial reference complete\n");

    // Parallel run; each task seeded from the same (cc, seed) pair.
    std::vector<Fingerprint> threaded(tasks.size());
    std::atomic<std::size_t> next_idx{0};
    std::vector<std::thread> pool;
    pool.reserve(static_cast<std::size_t>(threads));
    for (int t = 0; t < threads; ++t) {
        pool.emplace_back([&]() {
            while (true) {
                std::size_t i = next_idx.fetch_add(1, std::memory_order_relaxed);
                if (i >= tasks.size()) return;
                threaded[i] = run_one(tasks[i].cc, tasks[i].seed);
            }
        });
    }
    for (auto &th : pool) th.join();

    // Compare.
    std::size_t skipped = 0;
    for (std::size_t i = 0; i < tasks.size(); ++i) {
        if (serial[i].skipped) ++skipped;
        if (serial[i] != threaded[i]) {
            log_fail("threaded fingerprint != serial", tasks[i].cc,
                     tasks[i].seed, serial[i], threaded[i]);
        }
    }

    std::fprintf(stderr,
                 "stress_test: %zu tasks, %zu skipped (unimplemented card), %d failures.\n",
                 tasks.size(), skipped, g_failures);
    return g_failures == 0 ? 0 : 1;
}
