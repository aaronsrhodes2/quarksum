#!/bin/bash
# nagatha_run.sh — Run Nagatha from YOUR terminal (not the VM)
# Drop this in MatterShaper/ and run it from there.
#
# Usage:
#   ./nagatha_run.sh              — shows your Ollama models + library
#   ./nagatha_run.sh compose      — build the water glass scene
#   ./nagatha_run.sh map          — map just a water glass object
# ─────────────────────────────────────────────────────────────────────

set -e
cd "$(dirname "$0")"

# ── Step 1: Show available Ollama models ──────────────────────────────
echo ""
echo "┌─────────────────────────────────────────────────────────┐"
echo "│  Your Ollama models:                                    │"
echo "└─────────────────────────────────────────────────────────┘"
ollama list 2>/dev/null || echo "  (ollama not found in PATH — is it running?)"

# ── Step 2: Pick the model ────────────────────────────────────────────
# Change this to whichever model you saw above, e.g.:
#   MODEL="llama3.1:8b"
#   MODEL="llama3.2:3b"
#   MODEL="mistral:7b"
#   MODEL="gemma2:9b"
#   MODEL="qwen2.5:7b"
MODEL="${NAGATHA_MODEL:-$(ollama list 2>/dev/null | awk 'NR==2{print $1}')}"

echo ""
echo "  Using model: $MODEL"
echo "  (set NAGATHA_MODEL=yourmodel to override)"
echo ""

# ── Step 3: Run ───────────────────────────────────────────────────────
ACTION="${1:-list}"

case "$ACTION" in
  list)
    echo "─── Library contents ────────────────────────────────────────"
    python3 agent/nagatha.py --list --backend ollama --model "$MODEL"
    echo ""
    echo "To build the water glass scene, run:"
    echo "  ./nagatha_run.sh compose"
    ;;

  map)
    echo "─── Mapping: water glass ────────────────────────────────────"
    python3 agent/nagatha.py "water glass" \
        --backend ollama \
        --model "$MODEL" \
        --approve auto
    ;;

  compose)
    echo "─── Composing: water glass scene ────────────────────────────"
    python3 agent/nagatha.py \
        --compose "a water glass sitting on a wooden table, lit by a single candle" \
        --backend ollama \
        --model "$MODEL" \
        --approve auto
    ;;

  fetch)
    echo "─── Fetching Wikidata physical properties ────────────────────"
    echo "  Querying 100 common objects (0.6 s between requests)."
    echo "  Saves to object_maps/wikidata_cache.json"
    echo "  Safe to interrupt — checkpoints every 10 items."
    echo ""
    python3 agent/fetch_wikidata.py
    ;;

  fetch-report)
    echo "─── Wikidata cache report ───────────────────────────────────"
    python3 agent/fetch_wikidata.py --report
    ;;

  server)
    echo "─── Starting Nagatha web server ─────────────────────────────"
    echo "  Gallery + Nagatha prompt at http://localhost:7734"
    echo "  Ctrl-C to stop."
    echo ""
    python3 agent/nagatha_server.py
    ;;

  *)
    echo "Unknown action: $ACTION"
    echo ""
    echo "Usage: $0 [action]"
    echo ""
    echo "  list          Show the object library"
    echo "  map           Map a water glass object"
    echo "  compose       Build the water glass scene"
    echo "  fetch         Pull physical data for 100 objects from Wikidata"
    echo "  fetch-report  Show what's already in the Wikidata cache"
    echo "  server        Start the web UI at http://localhost:7734"
    exit 1
    ;;
esac
