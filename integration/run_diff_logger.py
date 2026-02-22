#!/usr/bin/env python3
"""Interactive diff logger for sts_lightspeed.

This script monitors the real Slay the Spire game (via CommunicationMod),
syncs the simulator state in real-time, and logs all discrepancies.

Usage:
    # Basic usage (auto-detect seed from game)
    python integration/run_diff_logger.py

    # With specific seed
    python integration/run_diff_logger.py --seed 12345

    # Watch mode (no simulator, just observe)
    python integration/run_diff_logger.py --watch

    # With all options
    python integration/run_diff_logger.py \
        --seed 12345 \
        --character IRONCLAD \
        --ascension 10 \
        --output-dir integration/results \
        --interval 0.1 \
        --verbose
"""
import argparse
import signal
import sys
from pathlib import Path

# Add paths for imports
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))

from harness.diff_logger import DiffLogger, create_session_config


# Global logger reference for signal handling
_logger: DiffLogger = None


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global _logger
    print("\n\nReceived shutdown signal, stopping logger...")
    if _logger:
        _logger.stop()
    sys.exit(0)


def main():
    """Main entry point for the diff logger CLI."""
    global _logger

    parser = argparse.ArgumentParser(
        description="Interactive diff logger for sts_lightspeed",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Auto-detect seed, full sync mode
  %(prog)s --watch                   # Watch mode (no simulator)
  %(prog)s --seed 12345 --verbose    # Specific seed with verbose output
  %(prog)s --mode verify             # Verify mode (compare only)

Output:
  Session files are written to integration/results/sessions/session_YYYYMMDD_HHMMSS/
  A symlink 'latest' always points to the most recent session.

  Files generated:
    - events.jsonl      : Append-only event log (JSON Lines)
    - combat.log        : Human-readable combat journal
    - summary.md        : Session summary (generated on exit)
    - discrepancies/    : Individual discrepancy reports (JSON + MD)
        """
    )

    # Game/simulator options
    parser.add_argument(
        '--seed',
        type=int,
        default=0,
        help='Game seed (0 to auto-detect from game)'
    )
    parser.add_argument(
        '--character',
        type=str,
        default='AUTO',
        choices=['AUTO', 'IRONCLAD', 'SILENT', 'DEFECT', 'WATCHER'],
        help='Character class (AUTO to detect from game)'
    )
    parser.add_argument(
        '--ascension',
        type=int,
        default=0,
        help='Ascension level (0 for none)'
    )

    # Mode options
    parser.add_argument(
        '--mode',
        type=str,
        default='full',
        choices=['full', 'watch', 'verify'],
        help='Sync mode: full (replay to sim), watch (observe only), verify (compare only)'
    )
    parser.add_argument(
        '--watch',
        action='store_true',
        help='Shorthand for --mode watch'
    )

    # Output options
    parser.add_argument(
        '--output-dir',
        type=str,
        default='integration/results',
        help='Base directory for session output (default: integration/results)'
    )
    parser.add_argument(
        '--interval',
        type=float,
        default=0.1,
        help='Polling interval in seconds (default: 0.1)'
    )

    # Bridge options
    parser.add_argument(
        '--state-dir',
        type=str,
        default='/tmp/sts_bridge',
        help='Bridge state directory (default: /tmp/sts_bridge)'
    )

    # Verbosity
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress non-essential output'
    )

    args = parser.parse_args()

    # Handle --watch shorthand
    mode = 'watch' if args.watch else args.mode

    # Create session config
    config = create_session_config(
        output_base_dir=args.output_dir,
        seed=args.seed,
        character=args.character,
        ascension=args.ascension,
        mode=mode,
        interval=args.interval,
        verbose=args.verbose and not args.quiet,
        state_dir=args.state_dir
    )

    # Create logger
    _logger = DiffLogger(config)

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Print startup banner
    if not args.quiet:
        print("=" * 60)
        print("STS LIGHTSPEED - Interactive Diff Logger")
        print("=" * 60)
        print(f"Session ID: {config.session_id}")
        print(f"Mode: {mode}")
        print(f"Output: {config.output_dir}")
        print()

    # Start the logger
    if not _logger.start():
        print("Failed to start diff logger. Is the game running with CommunicationMod?")
        return 1

    # Run the main loop
    try:
        _logger.run()
    except Exception as e:
        print(f"Error during logging: {e}")
        return 1
    finally:
        _logger.stop()

    # Return exit code based on discrepancies
    if _logger.has_critical_discrepancies():
        if not args.quiet:
            print("\nCRITICAL discrepancies found! Check the reports for details.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
