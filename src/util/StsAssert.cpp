//
// Phase 20.A — engine diagnostic hardening.
//
// Implementation of util/StsAssert.h. See header for rationale.
//

#include "util/StsAssert.h"

#include <cstdlib>
#include <ostream>
#include <iostream>

#include "combat/BattleContext.h"
#include "sim/search/BattleScumSearcher2.h"

namespace sts::util {

    void dumpDebugContext(std::ostream &os) {
        // Both globals are `thread_local T *` defined in
        // BattleContext.cpp / BattleScumSearcher2.cpp respectively.
        // Null in any host that didn't enter a battle or didn't run a
        // searcher (e.g. raw pybind callers, unit tests).
        BattleContext *bc = g_debug_bc;
        if (bc != nullptr) {
            os << *bc << '\n';
        } else {
            os << "[no BattleContext set]\n";
        }

        search::BattleScumSearcher2 *scum = search::g_debug_scum_search;
        if (scum != nullptr) {
            scum->printSearchStack(os, true);
        } else {
            os << "[no BattleScumSearcher set]\n";
        }
    }

    [[noreturn]] void stsAssertFail(const char *expr,
                                    const char *file,
                                    int line,
                                    const char *msg) {
        // Print to stderr because that's where the test harness and
        // stress test look. Flush after each step so partial output
        // survives if abort() itself crashes during the dump.
        std::cerr << "\n[STS_ASSERT_FAIL] " << file << ':' << line
                  << "  " << expr;
        if (msg != nullptr && *msg != '\0') {
            std::cerr << "  -- " << msg;
        }
        std::cerr << '\n';
        std::cerr.flush();

        // Best-effort diagnostic dump. If THIS throws (e.g. operator<<
        // on a corrupted BattleContext), at least we already printed
        // the expr above.
        try {
            dumpDebugContext(std::cerr);
        } catch (...) {
            std::cerr << "[dumpDebugContext threw an exception]\n";
        }
        std::cerr.flush();

        std::abort();
    }

}  // namespace sts::util
