//
// Phase 20.A — engine diagnostic hardening.
//
// Centralized assert / diagnostic-dump helpers used by the various
// #ifdef sts_asserts blocks in the engine. The pre-Phase-20 pattern
// was to unconditionally dereference thread-local globals
// (g_debug_bc, search::g_debug_scum_search) when an invariant
// failed. That works when the engine is running under a
// BattleScumSearcher, but in any other host (the pybind bindings,
// unit tests, the stress test, the RL gym wrapper) those globals
// can be null — and the diagnostic itself then SIGSEGV'd, hiding
// the real bug behind a fake one. This header provides a safe
// dump that null-checks both globals before use, plus a
// `stsAssertFail` helper that prints a clean message and aborts.
//

#ifndef STS_UTIL_STS_ASSERT_H
#define STS_UTIL_STS_ASSERT_H

#include <iosfwd>

namespace sts::util {

    // Dump as much engine context as is safely available to `os`.
    // - If `g_debug_bc != nullptr`: prints the BattleContext via its
    //   ostream operator. Otherwise prints "[no BattleContext set]".
    // - If `search::g_debug_scum_search != nullptr`: prints the
    //   searcher's action stack via its `printSearchStack(os, true)`
    //   method. Otherwise prints "[no BattleScumSearcher set]".
    // Never throws and never dereferences a null pointer.
    void dumpDebugContext(std::ostream &os);

    // Print `[STS_ASSERT_FAIL] file:line  expr  -- msg` to stderr,
    // followed by `dumpDebugContext`, flush stderr, then `std::abort()`.
    // Marked [[noreturn]].
    [[noreturn]] void stsAssertFail(const char *expr,
                                    const char *file,
                                    int line,
                                    const char *msg);

}  // namespace sts::util

// Always-on assertion macro (independent of NDEBUG). Use sparingly
// at engine boundaries where a bad value indicates a bug we MUST
// report cleanly.
//
// Example:
//   STS_ASSERT(card.id != CardId::INVALID,
//              "MakeTempCardInHand: refusing to enqueue INVALID card");
#define STS_ASSERT(cond, msg)                                                  \
    do {                                                                       \
        if (!(cond)) {                                                         \
            ::sts::util::stsAssertFail(#cond, __FILE__, __LINE__, msg);        \
        }                                                                      \
    } while (0)

#endif  // STS_UTIL_STS_ASSERT_H
