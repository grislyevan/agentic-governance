#!/usr/bin/env bash
# Build the Detec capability brief as PDF or standalone HTML.
# Requires: pandoc (https://pandoc.org/installing.html)
# For PDF: also needs a LaTeX engine (pdflatex, xelatex, or tectonic).
#
# Usage:
#   cd branding && ./build-brief.sh          # PDF if LaTeX available, else HTML
#   cd branding && ./build-brief.sh html     # Force HTML output
#   cd branding && ./build-brief.sh pdf      # Force PDF output (requires LaTeX)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INPUT="$SCRIPT_DIR/capability-brief.md"
FORMAT="${1:-auto}"

if ! command -v pandoc &>/dev/null; then
    echo "Error: pandoc is not installed. Install it from https://pandoc.org/installing.html"
    exit 1
fi

build_html() {
    local OUTPUT="$SCRIPT_DIR/capability-brief.html"
    pandoc "$INPUT" \
        -o "$OUTPUT" \
        --standalone \
        --metadata title="Detec Capability Brief" \
        -c "https://cdn.jsdelivr.net/npm/water.css@2/out/dark.min.css" \
        --variable maxwidth=48em
    echo "Built: $OUTPUT"
}

build_pdf() {
    local OUTPUT="$SCRIPT_DIR/capability-brief.pdf"
    local ENGINE=""
    for eng in pdflatex xelatex lualatex tectonic; do
        if command -v "$eng" &>/dev/null; then
            ENGINE="$eng"
            break
        fi
    done
    if [ -z "$ENGINE" ]; then
        echo "Error: No LaTeX engine found. Install texlive-base or tectonic."
        echo "  macOS:  brew install --cask mactex-no-gui"
        echo "  Ubuntu: sudo apt install texlive-latex-recommended"
        echo "  Or:     cargo install tectonic"
        exit 1
    fi
    pandoc "$INPUT" \
        -o "$OUTPUT" \
        --pdf-engine="$ENGINE" \
        -V geometry:margin=0.75in \
        -V fontsize=10pt \
        -V colorlinks=true \
        -V linkcolor=blue \
        -V urlcolor=blue
    echo "Built: $OUTPUT (engine: $ENGINE)"
}

case "$FORMAT" in
    html) build_html ;;
    pdf)  build_pdf ;;
    auto)
        for eng in pdflatex xelatex lualatex tectonic; do
            if command -v "$eng" &>/dev/null; then
                build_pdf
                exit 0
            fi
        done
        echo "No LaTeX engine found; falling back to HTML output."
        build_html
        ;;
    *) echo "Usage: $0 [html|pdf|auto]"; exit 1 ;;
esac
