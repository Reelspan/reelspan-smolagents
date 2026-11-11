# Changelog

## 0.1.1

- Dropped Whop, Listmonk, Nostr and Lemmy, which Reelspan no longer supports.

## 0.1.0

First release.

- Eight smolagents tools: profiles, text, video and photo posts (now or scheduled, with network settings), status,
  history, scheduled posts and analytics. Posting tools wait for each network's result.
- `reelspan_tools()` shares one client; `profile` pins every tool to one profile, `platforms` limits the networks,
  `read_only` drops posting.
- `reelspan_mcp_tools()` loads every tool of the hosted MCP server through `ToolCollection.from_mcp`.
