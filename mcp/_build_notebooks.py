import json
import uuid
from pathlib import Path
from textwrap import dedent

OUT_DIR = Path(__file__).parent


def _cell_id() -> str:
    return uuid.uuid4().hex[:12]


def md(text: str) -> dict:
    return {"cell_type": "markdown", "id": _cell_id(), "metadata": {}, "source": dedent(text).strip("\n")}


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "id": _cell_id(),
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": dedent(text).strip("\n"),
    }


def todo(student: str, solution: str, *, is_solution: bool) -> dict:
    return code(solution if is_solution else student)


def make_notebook(cells: list[dict]) -> dict:
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.10"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def write_notebook(name: str, cells: list[dict]) -> None:
    path = OUT_DIR / f"{name}.ipynb"
    path.write_text(json.dumps(make_notebook(cells), indent=1), encoding="utf-8")
    print(f"wrote {path.name}")


# ---------------------------------------------------------------------------
# Shared text fragments
# ---------------------------------------------------------------------------

ASYNC_PREAMBLE_NOTE = """
> **A note on async in Jupyter.** MCP's stdio transport uses subprocesses, which means we need
> `asyncio`. Jupyter (IPython 7+) supports top-level `await`, so most cells just call
> `await ...` directly. If your environment uses a different event-loop policy, the setup cell
> applies `nest_asyncio` defensively, which is harmless when not needed.
"""


# ---------------------------------------------------------------------------
# Lab 1 — Building the MCP server
# ---------------------------------------------------------------------------

def build_lab1(is_solution: bool) -> list[dict]:
    suffix = " (Solutions)" if is_solution else ""

    # The full `shop_server.py` content. In the student notebook, the function bodies
    # are stubs; in the solution notebook, they are filled in.
    if is_solution:
        shop_server_src = r'''
        # %%writefile shop_server.py
        """A small MCP server that exposes the shop.db database from the TTYD labs.

        Run directly to talk on stdio:
            python shop_server.py
        """
        from __future__ import annotations

        import sqlite3
        from pathlib import Path

        from mcp.server.fastmcp import FastMCP

        # The shop.db database lives one folder up (in talk_to_your_data/).
        DB_PATH = Path(__file__).resolve().parent.parent / "talk_to_your_data" / "shop.db"

        mcp = FastMCP("shop")


        def _query(sql: str, params: tuple = ()) -> list[dict]:
            uri = f"file:{DB_PATH.as_posix()}?mode=ro"
            with sqlite3.connect(uri, uri=True) as conn:
                conn.row_factory = sqlite3.Row
                return [dict(r) for r in conn.execute(sql, params).fetchall()]


        # --------------------------- Tools ---------------------------

        @mcp.tool()
        def list_products(category: str | None = None) -> list[dict]:
            """List products in the catalogue, optionally filtered by category."""
            if category:
                return _query(
                    "SELECT product_id, name, category, price, stock FROM products "
                    "WHERE category = ? ORDER BY name",
                    (category,),
                )
            return _query("SELECT product_id, name, category, price, stock FROM products ORDER BY name")


        @mcp.tool()
        def top_products_by_rating(limit: int = 5) -> list[dict]:
            """Return the products with the highest average review rating."""
            return _query(
                "SELECT p.product_id, p.name, p.category, "
                "       ROUND(AVG(r.rating), 2) AS avg_rating, COUNT(r.review_id) AS n_reviews "
                "FROM products p JOIN reviews r ON r.product_id = p.product_id "
                "GROUP BY p.product_id "
                "HAVING n_reviews >= 3 "
                "ORDER BY avg_rating DESC, n_reviews DESC "
                "LIMIT ?",
                (int(limit),),
            )


        @mcp.tool()
        def get_customer_orders(customer_id: int) -> list[dict]:
            """Get all orders for a specific customer, most recent first."""
            return _query(
                "SELECT order_id, order_date, status, total_amount FROM orders "
                "WHERE customer_id = ? ORDER BY order_date DESC",
                (int(customer_id),),
            )


        @mcp.tool()
        def search_reviews(product_name: str) -> list[dict]:
            """Return all reviews whose product name contains the given substring (case-insensitive)."""
            return _query(
                "SELECT p.name AS product, r.rating, r.comment, r.review_date "
                "FROM reviews r JOIN products p ON p.product_id = r.product_id "
                "WHERE LOWER(p.name) LIKE LOWER(?) "
                "ORDER BY r.review_date DESC",
                (f"%{product_name}%",),
            )


        # ------------------------- Resources -------------------------

        @mcp.resource("schema://shop")
        def shop_schema() -> str:
            """The full CREATE TABLE DDL for the shop database."""
            rows = _query(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            return "\n\n".join(r["sql"] for r in rows if r["sql"])


        @mcp.resource("data://categories")
        def categories() -> str:
            """A newline-separated list of distinct product categories."""
            rows = _query("SELECT DISTINCT category FROM products ORDER BY category")
            return "\n".join(r["category"] for r in rows)


        # -------------------------- Prompts --------------------------

        @mcp.prompt()
        def summarize_orders(customer_id: int) -> str:
            """A prompt template asking for a friendly summary of a customer's orders."""
            return (
                f"You are a customer-support assistant. Use the available tools to fetch the "
                f"orders for customer #{customer_id}, then write a short, friendly summary: "
                f"how many orders they have placed, the total amount they have spent, and the "
                f"status breakdown. Be concise."
            )


        if __name__ == "__main__":
            mcp.run()
        '''
    else:
        shop_server_src = r'''
        # %%writefile shop_server.py
        """A small MCP server that exposes the shop.db database from the TTYD labs.

        Run directly to talk on stdio:
            python shop_server.py
        """
        from __future__ import annotations

        import sqlite3
        from pathlib import Path

        from mcp.server.fastmcp import FastMCP

        # The shop.db database lives one folder up (in talk_to_your_data/).
        DB_PATH = Path(__file__).resolve().parent.parent / "talk_to_your_data" / "shop.db"

        mcp = FastMCP("shop")


        def _query(sql: str, params: tuple = ()) -> list[dict]:
            uri = f"file:{DB_PATH.as_posix()}?mode=ro"
            with sqlite3.connect(uri, uri=True) as conn:
                conn.row_factory = sqlite3.Row
                return [dict(r) for r in conn.execute(sql, params).fetchall()]


        # --------------------------- Tools ---------------------------

        @mcp.tool()
        def list_products(category: str | None = None) -> list[dict]:
            """List products in the catalogue, optionally filtered by category."""
            # TODO 6.1: query the products table. If `category` is provided, filter on it.
            # Return a list of dicts with keys: product_id, name, category, price, stock.
            raise NotImplementedError


        @mcp.tool()
        def top_products_by_rating(limit: int = 5) -> list[dict]:
            """Return the products with the highest average review rating."""
            # TODO 6.2: join products and reviews, group by product, compute AVG(rating).
            # Only include products with at least 3 reviews. Order by avg_rating desc, then by
            # number of reviews desc. Cap the result with LIMIT.
            raise NotImplementedError


        @mcp.tool()
        def get_customer_orders(customer_id: int) -> list[dict]:
            """Get all orders for a specific customer, most recent first."""
            # TODO 6.3: return order_id, order_date, status, total_amount for the customer,
            # ordered by order_date descending.
            raise NotImplementedError


        @mcp.tool()
        def search_reviews(product_name: str) -> list[dict]:
            """Return all reviews whose product name contains the given substring (case-insensitive)."""
            # TODO 6.4: SELECT product name, rating, comment, review_date where the product
            # name matches a case-insensitive substring.
            raise NotImplementedError


        # ------------------------- Resources -------------------------

        @mcp.resource("schema://shop")
        def shop_schema() -> str:
            """The full CREATE TABLE DDL for the shop database."""
            # TODO 7.1: read CREATE TABLE statements from sqlite_master and return them joined
            # with blank lines between.
            raise NotImplementedError


        @mcp.resource("data://categories")
        def categories() -> str:
            """A newline-separated list of distinct product categories."""
            # TODO 7.2: SELECT DISTINCT category FROM products, return them joined with newlines.
            raise NotImplementedError


        # -------------------------- Prompts --------------------------

        @mcp.prompt()
        def summarize_orders(customer_id: int) -> str:
            """A prompt template asking for a friendly summary of a customer's orders."""
            # TODO 8.1: return a prompt string that instructs the model to call the tools,
            # fetch the orders for `customer_id`, and write a short, friendly summary.
            raise NotImplementedError


        if __name__ == "__main__":
            mcp.run()
        '''

    return [
        md(f"""
        # MCP Lab 1 — Building Your First MCP Server{suffix}

        The **Model Context Protocol** (MCP) is an open protocol for connecting LLM
        applications to external tools, data sources, and prompt libraries. Instead of every
        application reinventing tool integration, an MCP server exposes capabilities once and
        any MCP-aware client can use them — Claude Desktop, IDE plugins, custom agents.

        In this lab you build an MCP server from scratch.

        ## Learning objectives

        By the end of this lab you will be able to:

        1. Explain what MCP is and what problem it solves.
        2. Distinguish the three MCP primitives — **tools, resources, prompts** — and pick the
           right one for a given capability.
        3. Build a server with the official `mcp` Python SDK (`FastMCP`) that wraps a SQLite
           database.
        4. Launch the server as a stdio subprocess and inspect its capabilities from a client.
        5. Call tools, read resources, and fetch prompts programmatically.

        ## Prerequisites

        - `pip install -r requirements.txt`
        - `shop.db` exists at `../talk_to_your_data/shop.db` (run `python ../talk_to_your_data/seed_db.py` if not).
        - Python 3.10+.
        """),

        md("""
        ## 1. What is MCP?

        Most LLM applications today have the same problem: the model needs to call out to the
        world — read a database, hit an internal API, look at a file. The model can do that
        only through **tool calling**, which means somebody has to:

        - define the tool's JSON schema,
        - implement the tool,
        - register it with the LLM client,
        - wire authentication, error handling, observability for it,
        - do this *in every application* that wants to use it.

        MCP factors this out. A server exposes tools (and resources, and prompts) over a
        standard protocol. Any MCP-aware client — Claude Desktop, an IDE, your custom
        agent — can connect and use them with no per-application code.

        Two transports:

        - **stdio** — the server is a subprocess of the client; they speak JSON-RPC over its
          stdin/stdout. Simplest, used for local servers. This is what we use in the lab.
        - **HTTP / Server-Sent Events** — the server is a long-running HTTP service. Used for
          shared, remote servers.

        Either way, the protocol is the same: a JSON-RPC handshake, then `list_*` and `call_*`
        messages.
        """),

        md("""
        ## 2. The three primitives

        | Primitive | Who triggers it       | What it returns                          | Example                                  |
        |-----------|-----------------------|------------------------------------------|------------------------------------------|
        | **Tool**     | The model (function call) | A result of executing some action      | "search the database", "send an email"   |
        | **Resource** | The application/user (read) | Read-only data — text or binary       | "the schema file", "today's metrics CSV" |
        | **Prompt**   | The user (selected)         | A pre-authored message template       | "summarize the last 7 days of orders"    |

        - **Tools** are the most familiar piece — they are the same idea as OpenAI/Anthropic
          tool calling, just standardized.
        - **Resources** are data the model can *read* without taking an action. Think of a
          file the application surfaces into the prompt context.
        - **Prompts** are templates the user (not the model) can invoke. The server defines
          them; the client surfaces them in its UI (e.g. as slash commands).
        """),

        md("## 3. Setup"),

        code("""
        # %pip install -r requirements.txt
        """),

        code("""
        import asyncio
        import sys
        from pathlib import Path

        # Defensive: on some Windows + Jupyter combos the default event loop policy can't
        # spawn subprocesses; the proactor policy can. This is harmless if already set.
        if sys.platform == "win32":
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            except Exception:
                pass

        import nest_asyncio
        nest_asyncio.apply()

        DB_PATH = (Path.cwd().parent / "talk_to_your_data" / "shop.db").resolve()
        assert DB_PATH.exists(), f"shop.db not found at {DB_PATH}. Run seed_db.py first."
        print("shop.db ok:", DB_PATH)
        """),

        md(ASYNC_PREAMBLE_NOTE),

        md("""
        ## 4. A minimum viable server

        Let's build the smallest server that works — one tool that adds two numbers. The
        `FastMCP` class uses Python decorators to register handlers: `@mcp.tool()`,
        `@mcp.resource(uri)`, `@mcp.prompt()`. The function signature and docstring are
        introspected to build the JSON schema the model sees.
        """),

        code("""
        %%writefile hello_server.py
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("hello")


        @mcp.tool()
        def add(a: int, b: int) -> int:
            \"\"\"Add two integers and return the sum.\"\"\"
            return a + b


        if __name__ == "__main__":
            mcp.run()
        """),

        md("""
        ### Talking to the server from this notebook

        The server, when run, takes over the process and speaks the MCP protocol on its stdio.
        To talk to it from Python we **launch it as a subprocess** with
        `StdioServerParameters`, then create a `ClientSession` over its streams.

        We'll build a real client in Lab 2. For now this minimal block is enough to confirm
        the server works.
        """),

        code("""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        hello_params = StdioServerParameters(command=sys.executable, args=["hello_server.py"])

        async with stdio_client(hello_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                print("tools:", [t.name for t in tools.tools])

                result = await session.call_tool("add", {"a": 2, "b": 40})
                # Tool results are a list of content items (TextContent, ImageContent, …).
                # We extract the text fields.
                text = "".join(getattr(c, "text", "") for c in result.content)
                print("add(2, 40) =", text)
        """),

        md("""
        ## 5. Designing the shop server

        Now we'll build a more useful server: one that lets a model query the `shop.db`
        database from the Text-to-SQL labs. This is *intentional* — the same database is now
        accessible two ways:

        - Through the **text-to-SQL pipeline** (LLM generates SQL).
        - Through a set of **typed MCP tools** (LLM calls specific, audited functions).

        The MCP tool path is safer: every tool is hand-written, with explicit parameters and
        validation. The trade-off is breadth — you can only answer what your tools cover.

        ### What we'll expose

        **Tools** (the model can invoke):

        - `list_products(category: Optional[str])`
        - `top_products_by_rating(limit: int = 5)`
        - `get_customer_orders(customer_id: int)`
        - `search_reviews(product_name: str)`

        **Resources** (the application can read):

        - `schema://shop` — the database DDL
        - `data://categories` — the list of product categories

        **Prompts** (the user can select):

        - `summarize_orders(customer_id: int)` — friendly per-customer summary
        """),

        md("## 6. Implementing the tools"),
        md("""
        The next cell uses Jupyter's `%%writefile` magic to write `shop_server.py` from this
        cell's contents. Fill in the TODOs inside the cell, then run it: Jupyter saves the
        file, and Section 9 below launches a fresh server process from it.

        Tips for the SQL inside the tools:

        - Use the `_query(sql, params)` helper. It opens a read-only connection and returns a
          list of dicts.
        - Pass user input as **parameters**, never via f-strings.
        """),

        md("## 7. Implementing the resources"),
        md("## 8. Implementing the prompts"),

        code(shop_server_src),

        md("""
        ## 9. Inspecting your server

        Now that `shop_server.py` exists on disk, we launch it and ask: what tools, resources,
        and prompts does it advertise? This is exactly what an MCP-aware client (Claude
        Desktop, an IDE plugin, etc.) would do on connection.
        """),

        code("""
        shop_params = StdioServerParameters(command=sys.executable, args=["shop_server.py"])

        async with stdio_client(shop_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                print("=== tools ===")
                for t in tools.tools:
                    print(f"  {t.name}: {t.description}")

                resources = await session.list_resources()
                print("\\n=== resources ===")
                for r in resources.resources:
                    print(f"  {r.uri}: {r.description}")

                prompts = await session.list_prompts()
                print("\\n=== prompts ===")
                for p in prompts.prompts:
                    args = ", ".join(a.name for a in (p.arguments or []))
                    print(f"  {p.name}({args}): {p.description}")
        """),

        md("### Calling a tool"),

        code("""
        async with stdio_client(shop_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("top_products_by_rating", {"limit": 3})
                for c in result.content:
                    if hasattr(c, "text"):
                        print(c.text)
        """),

        md("### Reading a resource"),

        code("""
        async with stdio_client(shop_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                res = await session.read_resource("schema://shop")
                for c in res.contents:
                    if hasattr(c, "text"):
                        print(c.text)
        """),

        md("### Fetching a prompt"),

        code("""
        async with stdio_client(shop_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                prm = await session.get_prompt("summarize_orders", {"customer_id": "1"})
                for msg in prm.messages:
                    print(f"[{msg.role}] {msg.content.text}")
        """),

        md("""
        ## Summary

        You built an MCP server that exposes:

        - Four **tools** wrapping common shop queries.
        - Two **resources** for read-only schema/data.
        - One **prompt** for a pre-baked customer-summary workflow.

        And you watched a client introspect the server and use each primitive.

        In **Lab 2** we replace the throw-away client cells above with a real client and wire
        it to an OpenAI tool-calling agent — so a natural-language question goes through the
        agent → MCP → SQLite → back to a friendly answer.

        ## Exercises

        1. **A new tool.** Add `category_revenue(year: int)` that returns total revenue per
           product category for a given year. Decide which existing queries to compose.
        2. **A new resource.** Add `stats://shop` that returns a one-paragraph natural-
           language summary of the database (row counts, date range covered, number of
           categories). Resources are computed on demand, so this can be live.
        3. **A safer SQL tool.** Add a tool `run_safe_select(sql: str)` that wires the
           `validate_sql_strict` function from TTYD Lab 2 in front of an `execute_safely`
           call. Decide what to return when validation fails: a thrown error, or a structured
           `{ok: false, reason: ...}`?
        4. **Authentication-shaped problem.** Imagine adding `get_customer_orders` as a tool a
           *customer* could call. How would you carry the customer's identity to the server
           when the client launches it as a subprocess? (Sketch — don't implement.)
        """),
    ]


# ---------------------------------------------------------------------------
# Lab 2 — MCP client + tool-calling agent
# ---------------------------------------------------------------------------

def build_lab2(is_solution: bool) -> list[dict]:
    suffix = " (Solutions)" if is_solution else ""

    return [
        md(f"""
        # MCP Lab 2 — Client + Tool-Calling Agent{suffix}

        In Lab 1 you built an MCP server and poked at it from a few throw-away cells. Now
        we build a real **client**: a thin layer that opens a session to the server, lists
        its capabilities, and wires the tools into an OpenAI tool-calling **agent loop** so
        a user's plain-English question turns into MCP tool calls and back into an answer.

        ## Learning objectives

        By the end of this lab you will be able to:

        1. Explain the MCP client/server handshake and lifecycle.
        2. Open a `ClientSession`, list capabilities, and call tools from Python.
        3. Translate MCP tool descriptors into OpenAI tool-calling format.
        4. Implement a robust **tool-calling agent loop** that delegates execution to MCP.
        5. Use server-provided **prompts** as user-selectable workflows.

        ## Prerequisites

        - Lab 1 completed; `shop_server.py` lives in this folder and runs.
        - `OPENAI_API_KEY` set in your environment or in a `.env` file in this folder.
        - `shop.db` at `../talk_to_your_data/shop.db`.
        """),

        md("""
        ## 1. The protocol from the client's view

        From the client's perspective, every interaction with an MCP server is:

        1. **Launch** the server (subprocess for stdio, or HTTP request for HTTP transport).
        2. **Initialize** — JSON-RPC handshake: exchange protocol version, capabilities.
        3. **Discover** — `list_tools`, `list_resources`, `list_prompts`.
        4. **Use** — `call_tool(name, args)`, `read_resource(uri)`, `get_prompt(name, args)`.
        5. **Tear down** — close the session, server process exits.

        The `mcp` Python SDK provides `ClientSession` (the protocol object) and `stdio_client`
        (a context manager that handles the subprocess + JSON-RPC plumbing). Together they
        make the above five steps two lines of Python.
        """),

        md("## 2. Setup"),

        code("""
        # %pip install -r requirements.txt
        """),

        code("""
        import asyncio
        import json
        import os
        import sys
        from pathlib import Path

        if sys.platform == "win32":
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            except Exception:
                pass

        import nest_asyncio
        nest_asyncio.apply()

        from dotenv import load_dotenv
        from openai import OpenAI

        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        load_dotenv()
        client = OpenAI()
        MODEL = "gpt-4o-mini"

        SERVER_PARAMS = StdioServerParameters(command=sys.executable, args=["shop_server.py"])
        assert Path("shop_server.py").exists(), "Build shop_server.py in Lab 1 first."
        """),

        md("""
        ## 3. A minimal client

        Below: a helper that opens a session, runs a coroutine against it, and closes
        cleanly. This is the boilerplate we use for every interaction with the server.
        """),

        code("""
        async def with_session(coro_fn):
            \"\"\"Open a session to the shop server, run `coro_fn(session)`, return the result.\"\"\"
            async with stdio_client(SERVER_PARAMS) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await coro_fn(session)


        async def list_all(session):
            tools = await session.list_tools()
            resources = await session.list_resources()
            prompts = await session.list_prompts()
            return tools.tools, resources.resources, prompts.prompts


        tools, resources, prompts = await with_session(list_all)
        print("tools:", [t.name for t in tools])
        print("resources:", [str(r.uri) for r in resources])
        print("prompts:", [p.name for p in prompts])
        """),

        md("""
        ## 4. Calling tools directly

        Before plugging the server into an agent loop, make sure you can call tools by hand —
        agent debugging is *much* easier when you know the underlying call works in isolation.
        """),

        code("""
        async def call_top(session):
            return await session.call_tool("top_products_by_rating", {"limit": 3})


        result = await with_session(call_top)
        for c in result.content:
            if hasattr(c, "text"):
                print(c.text)
        """),

        md("""
        ## 5. Bridging MCP tools to OpenAI tool-calling

        The OpenAI Chat Completions API accepts a `tools` argument of the form

        ```json
        [{
            "type": "function",
            "function": {
                "name": "...",
                "description": "...",
                "parameters": {<JSON schema>}
            }
        }]
        ```

        MCP's `list_tools()` response gives us tools with `.name`, `.description`, and
        `.inputSchema` (already a JSON Schema dict). Translation is a one-line shape change.

        ### TODO 5.1 — `mcp_tool_to_openai`
        """),

        todo(
            student="""
            def mcp_tool_to_openai(tool) -> dict:
                # TODO: Return a dict matching the OpenAI tool format above.
                # Fields you need: tool.name, tool.description, tool.inputSchema
                raise NotImplementedError


            # Smoke test
            openai_tools = [mcp_tool_to_openai(t) for t in tools]
            print(json.dumps(openai_tools[0], indent=2))
            """,
            solution="""
            def mcp_tool_to_openai(tool) -> dict:
                return {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.inputSchema,
                    },
                }


            openai_tools = [mcp_tool_to_openai(t) for t in tools]
            print(json.dumps(openai_tools[0], indent=2))
            """,
            is_solution=is_solution,
        ),

        md("""
        ## 6. The agent loop

        The standard tool-calling pattern, regardless of which provider you use:

        1. Send the conversation so far + the tool catalogue to the model.
        2. The model either returns a final answer (done) **or** one-or-more tool calls.
        3. Execute each tool call. For us "execute" means `session.call_tool(name, args)`.
        4. Append the tool results to the conversation as `role: tool` messages.
        5. Loop back to (1).

        It's a few lines of code, but two details often go wrong:

        - **Append the assistant message including its tool_calls field** before the tool
          results. The API uses the `tool_call_id` to match each tool result to the call it
          answered.
        - **Stop on something.** Cap iterations so a buggy server-side loop can't run forever.

        ### TODO 6.1 — `run_agent`

        Implement an agent loop with the contract:

        ```
        async def run_agent(session, user_message, history, openai_tools, max_iters=8) -> str
        ```

        - Append the user message to `history`.
        - Loop up to `max_iters` times:
          - Call `chat.completions.create(model=MODEL, messages=history, tools=openai_tools)`.
          - Append the assistant message (with `tool_calls` if present) to `history`.
          - If there are no `tool_calls`, return the assistant content.
          - Otherwise, for each tool call: `session.call_tool(...)`, append the result as a
            `role: tool` message.
        - If you hit `max_iters`, return a sentinel string explaining you stopped.
        """),

        todo(
            student="""
            async def run_agent(session, user_message: str, history: list, openai_tools: list, max_iters: int = 8) -> str:
                history.append({"role": "user", "content": user_message})

                for _ in range(max_iters):
                    # TODO: call chat.completions.create
                    # TODO: extract msg = resp.choices[0].message
                    # TODO: append assistant message to history (must include tool_calls field
                    #       in the right shape — see the OpenAI docs)
                    # TODO: if msg.tool_calls is empty, return msg.content
                    # TODO: otherwise, for each tool call, call session.call_tool(name, args)
                    #       and append a {role: "tool", tool_call_id, content} message
                    raise NotImplementedError

                return "[agent stopped: max iterations reached]"
            """,
            solution="""
            async def run_agent(session, user_message: str, history: list, openai_tools: list, max_iters: int = 8) -> str:
                history.append({"role": "user", "content": user_message})

                for _ in range(max_iters):
                    resp = client.chat.completions.create(
                        model=MODEL,
                        messages=history,
                        tools=openai_tools,
                        temperature=0,
                    )
                    msg = resp.choices[0].message

                    # Append assistant message (including tool_calls field).
                    assistant_entry = {"role": "assistant", "content": msg.content}
                    if msg.tool_calls:
                        assistant_entry["tool_calls"] = [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in msg.tool_calls
                        ]
                    history.append(assistant_entry)

                    if not msg.tool_calls:
                        return msg.content or ""

                    for tc in msg.tool_calls:
                        try:
                            args = json.loads(tc.function.arguments or "{}")
                        except json.JSONDecodeError:
                            args = {}
                        tool_result = await session.call_tool(tc.function.name, args)
                        text = "".join(getattr(c, "text", "") for c in tool_result.content)
                        if tool_result.isError:
                            text = f"[tool error] {text}"
                        history.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": text,
                        })

                return "[agent stopped: max iterations reached]"
            """,
            is_solution=is_solution,
        ),

        md("""
        ### Driving the agent

        Now we put it all together: one session, one conversation history, several user
        turns. Watch how the model picks tools and chains calls.
        """),

        code("""
        SYSTEM_PROMPT = (
            "You are a shop assistant. You answer questions about an e-commerce database by "
            "calling the available tools. Always call a tool when the user asks about products, "
            "orders, or reviews — never guess. Keep replies concise."
        )

        USER_TURNS = [
            "Which products have the best reviews?",
            "What categories of products do we carry?",
            "Show me the orders for customer 1 and tell me what their favourite category is.",
        ]


        async def chat_session():
            async with stdio_client(SERVER_PARAMS) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listing = await session.list_tools()
                    openai_tools = [mcp_tool_to_openai(t) for t in listing.tools]

                    history = [{"role": "system", "content": SYSTEM_PROMPT}]
                    for turn in USER_TURNS:
                        print(f"\\n>>> user: {turn}")
                        reply = await run_agent(session, turn, history, openai_tools)
                        print(f"<<< assistant: {reply}")


        await chat_session()
        """),

        md("""
        ## 7. Using server prompts as workflows

        Server **prompts** are the part of MCP many tutorials skip, but they're powerful.
        Think of them as **user-selectable workflows** the server defines: parameterized
        message templates that the user can invoke ("run the customer-summary workflow on
        customer 7"), with the agent loop executing whatever tool calls the prompt implies.

        Below we fetch the `summarize_orders` prompt from the server and feed it through the
        same `run_agent` loop. The server is doing dual duty: providing the *task statement*
        (via the prompt) **and** the *capability to do it* (via the tools).
        """),

        code("""
        async def run_summary_for(customer_id: int):
            async with stdio_client(SERVER_PARAMS) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    listing = await session.list_tools()
                    openai_tools = [mcp_tool_to_openai(t) for t in listing.tools]

                    prm = await session.get_prompt("summarize_orders", {"customer_id": str(customer_id)})
                    # The prompt comes back as a list of messages. We unwrap the user text.
                    user_text = "\\n\\n".join(
                        m.content.text for m in prm.messages if hasattr(m.content, "text")
                    )

                    history = [{"role": "system", "content": "Use the available tools to answer."}]
                    return await run_agent(session, user_text, history, openai_tools)


        print(await run_summary_for(1))
        """),

        md("""
        ## 8. Composing multiple servers (briefly)

        The same client code talks to *any* MCP server. In real systems you'd run several:
        one for your database, one for the filesystem, one for an internal API. The agent
        merges their tool catalogues into a single `openai_tools` list and the model picks
        across all of them transparently.

        The reference filesystem server is published as an npm package
        (`@modelcontextprotocol/server-filesystem`) — `StdioServerParameters(command="npx",
        args=["@modelcontextprotocol/server-filesystem", "/some/path"])`. Combining it with
        your shop server is one extra session and one bigger `openai_tools` list. This is the
        composability MCP is built for.

        ## Summary

        You now have a complete MCP-driven agent:

        - A real client (`with_session`, `ClientSession`).
        - A schema bridge (`mcp_tool_to_openai`).
        - A robust agent loop (`run_agent`) that delegates tool execution to MCP.
        - A way to invoke server-provided prompt workflows through the same loop.

        Across the two labs you saw both ends of the MCP wire — author the server's
        contract once, then any client can consume it without extra plumbing.

        ## Exercises

        1. **Tool error recovery.** Modify `run_agent` so when a tool returns `isError`, the
           next iteration includes a system reminder telling the model to recover or ask the
           user. Test on `get_customer_orders(customer_id=999)` (which doesn't exist).
        2. **Streaming output.** Replace `chat.completions.create` with the streaming variant
           and print partial tokens as they arrive. Keep tool execution synchronous.
        3. **Two servers.** Run your shop server *and* the filesystem MCP server side by
           side. Merge their tools. Ask a question that needs both (e.g. "list product
           categories, then write them to ./categories.txt"). Note how the agent picks
           cross-server.
        4. **Add a resource to the conversation.** When the user mentions "the schema",
           fetch `schema://shop` and inject it as a system message before the next agent
           turn. (This is how IDE-style clients surface server resources.)
        5. **Cost guardrail.** Sum `response.usage.total_tokens` across the agent loop. If a
           single turn exceeds a budget, abort and return a polite message.
        """),
    ]


def main() -> None:
    write_notebook("01_mcp_server", build_lab1(is_solution=False))
    write_notebook("01_mcp_server_solutions", build_lab1(is_solution=True))
    write_notebook("02_mcp_client_agent", build_lab2(is_solution=False))
    write_notebook("02_mcp_client_agent_solutions", build_lab2(is_solution=True))


if __name__ == "__main__":
    main()
