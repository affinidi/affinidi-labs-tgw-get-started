# ──────────────────────────────────────────────────────────────────────────────
#  affinidi-labs-tgw-get-started — root Makefile
#
#  This Makefile delegates to the auth0-mcp-surface demo.
#  For full documentation, see: auth0-mcp-surface/Makefile
#
#  Quick start:
#    cd auth0-mcp-surface && make help       # See all available targets
#    cd auth0-mcp-surface && make local-up   # Run the full demo
# ──────────────────────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help

.PHONY: help chat-auth0-local-up

help: ## Show available targets
	@echo ""
	@echo "  affinidi-labs-tgw-get-started — Root Makefile"
	@echo ""
	@echo "  This repository contains the auth0-mcp-surface demo."
	@echo "  All targets are defined in auth0-mcp-surface/Makefile"
	@echo ""
	@echo "  Quick start:"
	@echo "    cd auth0-mcp-surface && make help       # See all available targets"
	@echo "    cd auth0-mcp-surface && make local-up   # Run the full demo"
	@echo ""
	@echo "  Or use the shortcut from the root:"
	@echo "    make chat-auth0-local-up                # Run the full demo from root"
	@echo ""

chat-auth0-local-up: ## Run auth0-mcp-surface demo (delegates to auth0-mcp-surface/Makefile)
	@$(MAKE) -C auth0-mcp-surface local-up
