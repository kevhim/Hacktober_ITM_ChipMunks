#!/usr/bin/env bash
# ==============================================================================
# Chaos-Harness Hermes Agent Skill Installer
# Conforms to Agent Skill Open Standard (agentskills.io)
# ==============================================================================

set -euo pipefail

# Text colors for terminal formatting
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Determine script and repository root directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SKILLS_SRC="${REPO_ROOT}/skills"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
HERMES_SKILLS_DEST="${HERMES_HOME}/skills"

# Flags
DRY_RUN=0
USE_COPY=0

# Parse arguments
for arg in "$@"; do
    case "$arg" in
        --dry-run)
            DRY_RUN=1
            ;;
        --copy)
            USE_COPY=1
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Installs Chaos-Harness skills into Hermes Agent directory (~/.hermes/skills)."
            echo ""
            echo "Options:"
            echo "  --dry-run   Preview installation actions without creating files"
            echo "  --copy      Copy skill files instead of creating symbolic links"
            echo "  --help, -h  Display this help message"
            exit 0
            ;;
    esac
done

echo -e "${BOLD}${BLUE}============================================================${NC}"
echo -e "${BOLD}${CYAN}  💥 Chaos-Harness: Hermes Agent Skill Suite Installer${NC}"
echo -e "${BOLD}${BLUE}============================================================${NC}"
echo -e "Repository Root : ${REPO_ROOT}"
echo -e "Source Skills   : ${SKILLS_SRC}"
echo -e "Target Directory: ${HERMES_SKILLS_DEST}"
echo -e "Mode            : $([ $DRY_RUN -eq 1 ] && echo -e "${YELLOW}DRY-RUN (Simulated)${NC}" || echo -e "${GREEN}ACTIVE INSTALL${NC}")"
echo -e "Method          : $([ $USE_COPY -eq 1 ] && echo "Copy" || echo "Symlink")"
echo ""

# Expected core skills in the Chaos-Harness suite
EXPECTED_SKILLS=(
    "injection-fuzzer"
    "schema-breaker"
    "pii-leak-prober"
    "hallucination-trap"
    "auto-hardener"
)

# Ensure target directory exists
if [ $DRY_RUN -eq 0 ]; then
    mkdir -p "${HERMES_SKILLS_DEST}"
fi

INSTALLED_COUNT=0
FOUND_COUNT=0

# Process skills
for skill in "${EXPECTED_SKILLS[@]}"; do
    SRC_DIR="${SKILLS_SRC}/${skill}"
    DEST_DIR="${HERMES_SKILLS_DEST}/${skill}"

    echo -ne "  • ${BOLD}${skill}${NC}: "

    if [ -d "${SRC_DIR}" ] && [ -f "${SRC_DIR}/SKILL.md" ]; then
        FOUND_COUNT=$((FOUND_COUNT + 1))
        if [ $DRY_RUN -eq 1 ]; then
            echo -e "${GREEN}[VALID]${NC} Found source manifest at ${SRC_DIR}/SKILL.md"
        else
            # Remove existing link or directory if necessary
            if [ -L "${DEST_DIR}" ] || [ -d "${DEST_DIR}" ]; then
                rm -rf "${DEST_DIR}"
            fi

            if [ $USE_COPY -eq 1 ]; then
                cp -r "${SRC_DIR}" "${DEST_DIR}"
                echo -e "${GREEN}[COPIED]${NC} -> ${DEST_DIR}"
            else
                ln -sf "${SRC_DIR}" "${DEST_DIR}"
                echo -e "${GREEN}[LINKED]${NC} -> ${DEST_DIR}"
            fi
            INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
        fi
    else
        # Skill source directory doesn't exist yet (e.g. teammate PR in progress)
        if [ $DRY_RUN -eq 1 ]; then
            echo -e "${YELLOW}[PENDING]${NC} Source directory not yet populated (will install once Person 2 merges PR)"
        else
            # Create a placeholder registered skill directory so Hermes Agent discovers it
            mkdir -p "${DEST_DIR}"
            cat <<EOF > "${DEST_DIR}/SKILL.md"
---
name: ${skill}
description: Chaos-Harness ${skill} skill compliant with Agent Skill Open Standard (agentskills.io)
version: 1.0.0
author: Chaos-Harness Team
provider: gemma-4
---

# ${skill}
Automated red-teaming and safety probe compliant with Hermes Agent and Antigravity.
EOF
            echo -e "${YELLOW}[STAGED]${NC} Registered compliant manifest in ${DEST_DIR}"
            INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
        fi
    fi
done

echo ""
echo -e "${BOLD}${BLUE}============================================================${NC}"
if [ $DRY_RUN -eq 1 ]; then
    echo -e "${GREEN}✓ Dry run complete.${NC} Discovered ${FOUND_COUNT}/${#EXPECTED_SKILLS[@]} active skills in repository."
else
    echo -e "${GREEN}✓ Installation complete!${NC} ${INSTALLED_COUNT} skills configured in ${HERMES_SKILLS_DEST}."
fi
echo -e "${BOLD}${BLUE}============================================================${NC}"
echo -e "To verify with Hermes Agent, run:"
echo -e "  ${CYAN}hermes skills list --config deploy_and_benchmarks/hermes_config.yaml${NC}"
echo ""
