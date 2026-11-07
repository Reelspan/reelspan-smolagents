# reelspan-smolagents

[Hugging Face smolagents](https://github.com/huggingface/smolagents) tools for [Reelspan](https://reelspan.com). Let a
`CodeAgent` or `ToolCallingAgent` publish videos, photos and text to TikTok, YouTube, Instagram, Facebook, X, Threads,
LinkedIn, Pinterest, Bluesky, Reddit and 12 more networks, check each network's result and read analytics.

```bash
pip install reelspan-smolagents
export REELSPAN_API_KEY=rs_live_...   # dashboard → Developers → API keys
```

```python
from smolagents import CodeAgent, InferenceClientModel
from reelspan_smolagents import reelspan_tools

agent = CodeAgent(tools=reelspan_tools(profile="acme"), model=InferenceClientModel())
agent.run("Post 'Dark mode is live 🌙' to X, Threads and Bluesky, then tell me the links.")
```

## Tools

| Tool | |
|---|---|
| `reelspan_profiles` | Profiles and their connected networks |
| `reelspan_text` | Text post (threads on X and Bluesky when long) |
| `reelspan_video` | Video from a URL (Drive/Dropbox links work) or a local path |
| `reelspan_photos` | One photo or a carousel |
| `reelspan_status` | Each network's result |
| `reelspan_history` | Recent posts |
| `reelspan_scheduled` | Posts waiting for their time |
| `reelspan_analytics` | Followers, reach and engagement |

Posting tools take `scheduled_date` + `timezone` and `settings` for network options (Upload-Post field names work too).

```python
reelspan_tools(
    profile="acme",                 # pin to one profile
    platforms=["linkedin", "x"],    # only these networks
    read_only=True,                 # no posting
)
```

## Every tool of the hosted MCP server

```bash
pip install "reelspan-smolagents[mcp]"
```

```python
from reelspan_smolagents import reelspan_mcp_tools

with reelspan_mcp_tools() as tools:   # schedule edits, retries, AI captions, library, webhooks…
    agent = CodeAgent(tools=tools, model=InferenceClientModel())
    agent.run("Which of my posts did best on TikTok last week?")
```

## Links

[API reference](https://reelspan.com/docs) · [Python SDK](https://github.com/Reelspan/reelspan-python) ·
[LangChain tools](https://github.com/Reelspan/langchain-reelspan)

MIT licensed. Security reports: see [SECURITY.md](SECURITY.md).
