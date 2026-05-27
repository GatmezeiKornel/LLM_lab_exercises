# AI & LLM Systems — Lab Exercises

Two lab tracks covering practical patterns for building LLM-powered systems:

1. **Talk to Your Data (Text-to-SQL)** — translating natural language to SQL, validating and judging the result, and securing the whole pipeline against misuse.
2. **Model Context Protocol (MCP)** — building a custom MCP server (tools, prompts, resources), a minimal client, and wiring it to a tool-calling LLM agent.

The two tracks are designed to complement each other: in the MCP track, the server you build exposes the same SQLite database from the Text-to-SQL track, so students see how a "talk to your data" backend can be packaged as a reusable MCP service.

## Repository layout

```
.
├── talk_to_your_data/
│   ├── 01_text_to_sql_pipeline.ipynb            # Student notebook (TODOs)
│   ├── 01_text_to_sql_pipeline_solutions.ipynb  # Reference solution
│   ├── 02_text_to_sql_security.ipynb            # Student notebook (TODOs)
│   ├── 02_text_to_sql_security_solutions.ipynb  # Reference solution
│   ├── seed_db.py                               # Builds shop.db (SQLite)
│   └── requirements.txt
└── mcp/
    ├── 01_mcp_server.ipynb                      # Student notebook (TODOs)
    ├── 01_mcp_server_solutions.ipynb            # Reference solution
    ├── 02_mcp_client_agent.ipynb                # Student notebook (TODOs)
    ├── 02_mcp_client_agent_solutions.ipynb      # Reference solution
    └── requirements.txt
```

## Prerequisites

- Python 3.10+
- An OpenAI API key (set as the `OPENAI_API_KEY` environment variable, or in a `.env` file in the working directory)
- Basic SQL, Python, and Jupyter familiarity

## Getting started

```bash
# Pick a track and install its dependencies
cd talk_to_your_data
pip install -r requirements.txt
python seed_db.py            # Creates shop.db
jupyter lab                  # Open 01_text_to_sql_pipeline.ipynb
```

The MCP labs (`mcp/`) reuse `shop.db` from the Text-to-Your-Data folder, so run `seed_db.py` first either way.

## How the labs are structured

Every lab notebook follows the same pattern:

- **Concept sections** explain *why* a technique exists and what it protects against.
- **Demo cells** are pre-written so students can run and observe behaviour.
- **TODO cells** are clearly marked (`# TODO: ...`). Students implement these.
- A matching `*_solutions.ipynb` contains the reference implementation.

Each notebook ends with a short **Exercises** section that goes beyond the guided TODOs — open-ended tasks suitable for graded homework.

## Cost note

The notebooks default to `gpt-4o-mini`, which is inexpensive. Running every cell in all four notebooks end-to-end should cost well under one US dollar. A model constant at the top of each notebook makes it easy to swap.
