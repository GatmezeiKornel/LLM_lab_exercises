import json
import uuid
from pathlib import Path
from textwrap import dedent

OUT_DIR = Path(__file__).parent


# ---------------------------------------------------------------------------
# Cell helpers
# ---------------------------------------------------------------------------

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
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
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
# Lab 1 — Text-to-SQL pipeline
# ---------------------------------------------------------------------------

def build_lab1(is_solution: bool) -> list[dict]:
    suffix = " (Solutions)" if is_solution else ""
    return [
        md(f"""
        # Lab 1 — Text-to-SQL Pipeline{suffix}

        In this lab you build the core of a "talk to your data" system: a pipeline that
        takes a natural-language question, produces a SQL query, validates it, executes it,
        and judges the answer.

        ## Learning objectives

        By the end of this lab you will be able to:

        1. Turn a database schema into a useful **system prompt** for a code-generating LLM.
        2. Use **few-shot examples** to steer query style and coverage.
        3. Apply **static checks** to a generated SQL string using an AST parser (`sqlglot`),
           rejecting non-`SELECT` statements, unknown tables, and unbounded scans.
        4. Execute the query safely against SQLite and return a tidy result.
        5. Evaluate correctness two ways: **dynamic comparison** to a gold query when one exists,
           and **LLM-as-judge** when it does not.
        6. Assemble all of the above into a small **evaluation harness** that you can run over a
           test set.

        ## Prerequisites

        - `python seed_db.py` has been run and `shop.db` exists next to this notebook.
        - `OPENAI_API_KEY` is set in your environment or in a `.env` file in this folder.
        """),

        md("## 1. Setup"),

        code("""
        # If you have not yet installed dependencies:
        # %pip install -r requirements.txt
        """),

        code("""
        import os
        import json
        import sqlite3
        from pathlib import Path

        import pandas as pd
        from dotenv import load_dotenv
        from openai import OpenAI
        import sqlglot
        from sqlglot import exp

        load_dotenv()

        DB_PATH = Path("shop.db")
        assert DB_PATH.exists(), "Run `python seed_db.py` first to create shop.db."

        MODEL = "gpt-4o-mini"     # cheap & fast; swap for gpt-4o for higher quality
        JUDGE_MODEL = "gpt-4o-mini"

        client = OpenAI()  # reads OPENAI_API_KEY from the environment
        """),

        md("""
        ## 2. The database

        `shop.db` models a tiny e-commerce backend. Five tables:

        | table        | purpose                                              |
        |--------------|------------------------------------------------------|
        | `customers`  | One row per customer (name, email, country).         |
        | `products`   | Catalogue (name, category, price, stock).            |
        | `orders`     | Header per order (customer, date, status, total).    |
        | `order_items`| Line items: which products were in which order.      |
        | `reviews`    | Star ratings + free-text comments.                   |

        We'll work directly with `sqlite3` to keep dependencies minimal.
        """),

        code("""
        def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
            \"\"\"Run SQL against shop.db and return the result as a DataFrame.\"\"\"
            with sqlite3.connect(DB_PATH) as conn:
                return pd.read_sql_query(sql, conn, params=params)

        query_df("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        """),

        code("""
        # Peek at a few rows from each table
        for table in ["customers", "products", "orders", "order_items", "reviews"]:
            print(f"--- {table} ---")
            print(query_df(f"SELECT * FROM {table} LIMIT 3").to_string(index=False))
            print()
        """),

        md("""
        ## 3. Naive text-to-SQL

        The simplest thing that could work: tell the model "you are a SQL expert", give it the
        question, and parse out a SQL string. No schema, no examples, no checks.

        Let's see what goes wrong.
        """),

        code("""
        def naive_translate(question: str) -> str:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert SQL author. Reply with a single SQL query and no commentary."},
                    {"role": "user", "content": question},
                ],
                temperature=0,
            )
            return resp.choices[0].message.content.strip()

        print(naive_translate("How many customers do we have?"))
        """),

        md("""
        Try a more ambiguous question. Without the schema the model has to **guess** column names —
        sometimes it guesses right, sometimes it invents fields that don't exist.
        """),

        code("""
        print(naive_translate("Which products have we sold most of, by quantity?"))
        """),

        md("""
        ## 4. Schema-aware prompting

        Giving the model the schema is the single biggest quality improvement. We'll extract the
        `CREATE TABLE` statements from SQLite's catalogue and inject them into the system prompt.

        ### Why DDL specifically?

        `CREATE TABLE` statements carry column names, types, NOT NULL constraints, CHECK
        constraints, and FK references — everything the model needs to write a valid query.
        Sending raw rows is wasteful and risks leaking data into prompts; sending DDL is compact
        and lossless.
        """),

        code("""
        def get_schema_ddl() -> str:
            sql = \"\"\"
                SELECT sql FROM sqlite_master
                WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'
                ORDER BY name;
            \"\"\"
            with sqlite3.connect(DB_PATH) as conn:
                rows = conn.execute(sql).fetchall()
            return "\\n\\n".join(r[0] for r in rows if r[0])

        print(get_schema_ddl())
        """),

        md("""
        ### TODO 4.1 — implement `translate_to_sql`

        Write a function that takes a natural-language `question` and returns a SQL string.

        Requirements:

        - Include the schema DDL in the system prompt.
        - Instruct the model to return **only** the SQL — no markdown fences, no commentary.
        - Strip any code-fence wrapping (` ```sql ... ``` `) defensively, in case the model adds it
          anyway.
        - Use `temperature=0` for reproducibility.
        """),

        todo(
            student="""
            def translate_to_sql(question: str) -> str:
                # TODO: build a system prompt that includes get_schema_ddl()
                # TODO: call the OpenAI chat API
                # TODO: extract the assistant message and strip markdown fences if present
                raise NotImplementedError

            # Quick sanity check:
            # print(translate_to_sql("How many orders are in 'delivered' status?"))
            """,
            solution="""
            def _strip_fence(text: str) -> str:
                t = text.strip()
                if t.startswith("```"):
                    # Drop the opening fence (with optional language tag) and the closing fence.
                    t = t.split("\\n", 1)[1] if "\\n" in t else t
                    if t.endswith("```"):
                        t = t[: -3]
                return t.strip()


            def translate_to_sql(question: str) -> str:
                system = (
                    "You are an expert SQLite SQL author.\\n"
                    "Given a user question, return ONE SQL query that answers it.\\n"
                    "Use only the tables and columns shown in the schema below.\\n"
                    "Reply with the SQL only — no prose, no markdown fences.\\n\\n"
                    "Schema:\\n" + get_schema_ddl()
                )
                resp = client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": question},
                    ],
                    temperature=0,
                )
                return _strip_fence(resp.choices[0].message.content)


            print(translate_to_sql("How many orders are in 'delivered' status?"))
            """,
            is_solution=is_solution,
        ),

        code("""
        # Try it on a few realistic questions
        questions = [
            "How many customers are from Hungary (country code HU)?",
            "What is the average rating per product category?",
            "Which customer has spent the most overall?",
        ]
        for q in questions:
            print(f"Q: {q}")
            print(translate_to_sql(q))
            print()
        """),

        md("""
        ## 5. Few-shot examples

        Schema alone gets us most of the way. Few-shot examples close the gap on style and edge
        cases — `JOIN` ordering, `GROUP BY` discipline, how to spell "this year", etc.

        Below we add three examples to the prompt. Notice that they share *style* with what we
        want back (lowercase keywords, explicit aliases, no `SELECT *`).
        """),

        code("""
        FEW_SHOT = [
            {
                "q": "How many customers signed up in 2024?",
                "sql": "select count(*) as n_customers from customers where strftime('%Y', created_at) = '2024';",
            },
            {
                "q": "Top 5 products by total revenue.",
                "sql": (
                    "select p.name, sum(oi.quantity * oi.unit_price) as revenue "
                    "from order_items oi join products p on p.product_id = oi.product_id "
                    "group by p.name order by revenue desc limit 5;"
                ),
            },
            {
                "q": "Average rating for product 'Wireless Mouse'.",
                "sql": (
                    "select avg(r.rating) as avg_rating from reviews r "
                    "join products p on p.product_id = r.product_id where p.name = 'Wireless Mouse';"
                ),
            },
        ]


        def translate_to_sql_fewshot(question: str) -> str:
            system = (
                "You are an expert SQLite SQL author.\\n"
                "Return ONE SQL query that answers the user's question.\\n"
                "Use only the tables and columns shown in the schema. SQL only — no prose, no fences.\\n\\n"
                "Schema:\\n" + get_schema_ddl()
            )
            messages = [{"role": "system", "content": system}]
            for ex in FEW_SHOT:
                messages.append({"role": "user", "content": ex["q"]})
                messages.append({"role": "assistant", "content": ex["sql"]})
            messages.append({"role": "user", "content": question})

            resp = client.chat.completions.create(model=MODEL, messages=messages, temperature=0)
            return resp.choices[0].message.content.strip()


        print(translate_to_sql_fewshot("Revenue by product category, descending."))
        """),

        md("""
        ## 6. Static checks

        Never run a model-generated query without first asking: *is it well-formed, is it safe,
        does it only touch tables we expect?* This is a cheap, deterministic line of defence
        that doesn't need to call the LLM again.

        We'll use [`sqlglot`](https://github.com/tobymao/sqlglot), a pure-Python SQL parser, to
        turn the query into an AST and inspect it.

        Three checks we care about right now (the security lab adds more):

        1. **Parses** — `sqlglot.parse_one(sql, dialect='sqlite')` doesn't raise.
        2. **SELECT-only** — the top-level node is a `Select`, not an `Insert`/`Update`/`Delete`/`Drop`.
        3. **Tables are in the allow-list** — every referenced table belongs to our schema.
        """),

        md("### TODO 6.1 — `is_select_only`"),

        todo(
            student="""
            def is_select_only(sql: str) -> bool:
                # TODO: parse with sqlglot (dialect='sqlite')
                # TODO: return True if the root expression is a SELECT, else False
                # Reject anything that contains DDL / DML expressions anywhere in the tree.
                raise NotImplementedError


            # Smoke tests
            assert is_select_only("SELECT 1") is True
            assert is_select_only("select * from customers where customer_id = 1") is True
            assert is_select_only("DELETE FROM customers") is False
            assert is_select_only("DROP TABLE customers") is False
            assert is_select_only("UPDATE customers SET email = 'x'") is False
            print("ok")
            """,
            solution="""
            FORBIDDEN = (
                exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create,
                exp.AlterTable, exp.TruncateTable,
            )


            def is_select_only(sql: str) -> bool:
                try:
                    tree = sqlglot.parse_one(sql, dialect="sqlite")
                except Exception:
                    return False
                if not isinstance(tree, exp.Select):
                    return False
                # Defence in depth: reject any forbidden node anywhere in the tree (e.g. CTEs
                # that smuggle in a DELETE on a dialect that allows it).
                return not any(isinstance(node, FORBIDDEN) for node in tree.walk())


            assert is_select_only("SELECT 1") is True
            assert is_select_only("select * from customers where customer_id = 1") is True
            assert is_select_only("DELETE FROM customers") is False
            assert is_select_only("DROP TABLE customers") is False
            assert is_select_only("UPDATE customers SET email = 'x'") is False
            print("ok")
            """,
            is_solution=is_solution,
        ),

        md("### TODO 6.2 — `referenced_tables`"),

        todo(
            student="""
            def referenced_tables(sql: str) -> set[str]:
                # TODO: parse the SQL and return the set of base table names it references.
                # Hint: walk the AST and collect `exp.Table` nodes; each has a `.name` attribute.
                raise NotImplementedError


            assert referenced_tables("select * from customers c join orders o on o.customer_id = c.customer_id") == {"customers", "orders"}
            print("ok")
            """,
            solution="""
            def referenced_tables(sql: str) -> set[str]:
                tree = sqlglot.parse_one(sql, dialect="sqlite")
                return {t.name for t in tree.find_all(exp.Table)}


            assert referenced_tables("select * from customers c join orders o on o.customer_id = c.customer_id") == {"customers", "orders"}
            print("ok")
            """,
            is_solution=is_solution,
        ),

        md("""
        ### TODO 6.3 — `validate_sql`

        Combine the checks. Return `(ok, reason)`. `ok` is `True` only when:

        - the query parses,
        - it is SELECT-only,
        - every referenced table is in `allowed_tables`.
        """),

        todo(
            student="""
            ALLOWED_TABLES = {"customers", "products", "orders", "order_items", "reviews"}


            def validate_sql(sql: str, allowed: set[str] = ALLOWED_TABLES) -> tuple[bool, str]:
                # TODO: try to parse; on failure return (False, "...")
                # TODO: check is_select_only
                # TODO: check referenced_tables ⊆ allowed
                raise NotImplementedError


            ok, why = validate_sql("SELECT name FROM customers LIMIT 5")
            print(ok, why)
            ok, why = validate_sql("DELETE FROM customers")
            print(ok, why)
            ok, why = validate_sql("SELECT * FROM secret_table")
            print(ok, why)
            """,
            solution="""
            ALLOWED_TABLES = {"customers", "products", "orders", "order_items", "reviews"}


            def validate_sql(sql: str, allowed: set[str] = ALLOWED_TABLES) -> tuple[bool, str]:
                try:
                    sqlglot.parse_one(sql, dialect="sqlite")
                except Exception as e:
                    return False, f"parse_error: {e}"
                if not is_select_only(sql):
                    return False, "not_select_only"
                bad = referenced_tables(sql) - allowed
                if bad:
                    return False, f"unknown_tables: {sorted(bad)}"
                return True, "ok"


            print(validate_sql("SELECT name FROM customers LIMIT 5"))
            print(validate_sql("DELETE FROM customers"))
            print(validate_sql("SELECT * FROM secret_table"))
            """,
            is_solution=is_solution,
        ),

        md("""
        ## 7. Execution

        Static checks passed — now we run the query. Two safety guards still apply at run time:

        - **Read-only connection** (`mode=ro` via SQLite URI).
        - **Row cap** — slice the DataFrame to a maximum number of rows after fetch.
        """),

        code("""
        MAX_ROWS = 100


        def execute_sql(sql: str, max_rows: int = MAX_ROWS) -> pd.DataFrame:
            uri = f"file:{DB_PATH.as_posix()}?mode=ro"
            with sqlite3.connect(uri, uri=True) as conn:
                df = pd.read_sql_query(sql, conn)
            return df.head(max_rows)


        sql = translate_to_sql_fewshot("Top 3 customers by number of orders.")
        print("Generated SQL:\\n", sql, "\\n")
        ok, why = validate_sql(sql)
        print("Validation:", ok, why)
        if ok:
            display = execute_sql(sql)
            print(display.to_string(index=False))
        """),

        md("""
        ## 8. Dynamic correctness (gold answer)

        When we have a **gold SQL** for a question, we can run both queries and compare result
        sets. This is the cheapest, most reliable signal in a regression suite: if the column
        sets and rows match, the candidate is correct *for this question* regardless of how the
        SQL is shaped.

        ### TODO 8.1 — `results_match`

        Implement a comparison that is robust to:

        - **Row order** (most analytics questions don't specify an order)
        - **Column order** (different SQL can return columns in different orders)
        - **Column naming** when the values are identical but the alias differs — see hint
        """),

        todo(
            student="""
            def results_match(a: pd.DataFrame, b: pd.DataFrame, ignore_column_names: bool = False) -> bool:
                # TODO: compare DataFrames as sets of rows.
                # If ignore_column_names is True, compare by sorted-tuple-of-values instead of by named columns.
                # If False, require the same column set and matching rows.
                # Hint: convert each row to a tuple, build a Counter, compare.
                raise NotImplementedError


            a = pd.DataFrame({"x": [1, 2, 3]})
            b = pd.DataFrame({"x": [3, 1, 2]})
            assert results_match(a, b)
            c = pd.DataFrame({"y": [3, 1, 2]})
            assert not results_match(a, c)
            assert results_match(a, c, ignore_column_names=True)
            print("ok")
            """,
            solution="""
            from collections import Counter


            def results_match(a: pd.DataFrame, b: pd.DataFrame, ignore_column_names: bool = False) -> bool:
                if ignore_column_names:
                    return Counter(map(tuple, a.values.tolist())) == Counter(map(tuple, b.values.tolist()))
                if set(a.columns) != set(b.columns):
                    return False
                b_aligned = b[list(a.columns)]
                return Counter(map(tuple, a.values.tolist())) == Counter(map(tuple, b_aligned.values.tolist()))


            a = pd.DataFrame({"x": [1, 2, 3]})
            b = pd.DataFrame({"x": [3, 1, 2]})
            assert results_match(a, b)
            c = pd.DataFrame({"y": [3, 1, 2]})
            assert not results_match(a, c)
            assert results_match(a, c, ignore_column_names=True)
            print("ok")
            """,
            is_solution=is_solution,
        ),

        code("""
        # Compare a generated query against a gold one
        question = "How many delivered orders are there?"
        gold = "SELECT COUNT(*) AS n FROM orders WHERE status = 'delivered'"

        candidate = translate_to_sql_fewshot(question)
        print("Candidate:", candidate)

        df_gold = execute_sql(gold)
        df_cand = execute_sql(candidate)
        print("\\nGold:\\n", df_gold)
        print("\\nCandidate:\\n", df_cand)
        print("\\nMatch:", results_match(df_gold, df_cand, ignore_column_names=True))
        """),

        md("""
        ## 9. LLM-as-judge (no gold answer)

        Gold queries are expensive to write and cover only a tiny fraction of real questions. For
        the long tail, we ask a model to judge whether the SQL and its result *plausibly answer*
        the user's question.

        The judge prompt has three jobs:

        1. **Constrain the output** to a small JSON schema so it is machine-parseable.
        2. **Force a verdict** (`pass` / `fail`) and a short reason.
        3. **Pass a result preview**, not the whole result, to keep prompts cheap and to avoid
           biasing the judge with sheer volume of data.

        Limitations to know:

        - A judge is correlated with the generator (same model family, similar blind spots).
          Use a *different* model when the budget allows.
        - Judges drift. Pin the prompt and re-evaluate on a held-out gold set periodically.

        ### TODO 9.1 — `judge_answer`
        """),

        todo(
            student="""
            JUDGE_SYSTEM = \"\"\"You judge whether a SQL query plus its result answers a user's question.
            Reply with a single JSON object: {"verdict": "pass" | "fail", "reason": "<one short sentence>"}.
            Do not include any other text.\"\"\"


            def judge_answer(question: str, sql: str, result_df: pd.DataFrame) -> dict:
                # TODO: build a user message containing question, sql, and a short result preview
                #       (e.g., the first 10 rows formatted as CSV or TSV).
                # TODO: call the API with response_format={"type": "json_object"}
                # TODO: parse and return the JSON.
                raise NotImplementedError


            verdict = judge_answer(
                "How many delivered orders are there?",
                "SELECT COUNT(*) AS n FROM orders WHERE status = 'delivered'",
                execute_sql("SELECT COUNT(*) AS n FROM orders WHERE status = 'delivered'"),
            )
            print(verdict)
            """,
            solution="""
            JUDGE_SYSTEM = \"\"\"You judge whether a SQL query plus its result answers a user's question.
            Reply with a single JSON object: {"verdict": "pass" | "fail", "reason": "<one short sentence>"}.
            Do not include any other text.\"\"\"


            def judge_answer(question: str, sql: str, result_df: pd.DataFrame) -> dict:
                preview = result_df.head(10).to_csv(index=False)
                user_msg = (
                    f"Question:\\n{question}\\n\\n"
                    f"SQL:\\n{sql}\\n\\n"
                    f"Result (first 10 rows, CSV):\\n{preview}"
                )
                resp = client.chat.completions.create(
                    model=JUDGE_MODEL,
                    messages=[
                        {"role": "system", "content": JUDGE_SYSTEM},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0,
                    response_format={"type": "json_object"},
                )
                return json.loads(resp.choices[0].message.content)


            verdict = judge_answer(
                "How many delivered orders are there?",
                "SELECT COUNT(*) AS n FROM orders WHERE status = 'delivered'",
                execute_sql("SELECT COUNT(*) AS n FROM orders WHERE status = 'delivered'"),
            )
            print(verdict)
            """,
            is_solution=is_solution,
        ),

        md("""
        ## 10. Putting it together — a small eval harness

        We now have all the pieces. Let's run them as a pipeline over a test set with mixed
        cases — some with a gold SQL (so we use the dynamic check), some without (so we fall
        back to the LLM judge).
        """),

        code("""
        TEST_SET = [
            {
                "question": "How many customers are from Hungary (country code HU)?",
                "gold_sql": "SELECT COUNT(*) AS n FROM customers WHERE country = 'HU'",
            },
            {
                "question": "How many orders have status 'cancelled'?",
                "gold_sql": "SELECT COUNT(*) AS n FROM orders WHERE status = 'cancelled'",
            },
            {
                "question": "Top 3 product categories by revenue.",
                "gold_sql": None,   # no gold — fall back to LLM judge
            },
            {
                "question": "Which customer wrote the most reviews?",
                "gold_sql": None,
            },
            {
                "question": "Delete all customers from Germany.",
                "gold_sql": None,   # adversarial — should be rejected by validate_sql
            },
        ]
        """),

        md("### TODO 10.1 — `evaluate_pipeline`"),

        todo(
            student="""
            def evaluate_pipeline(test_set: list[dict]) -> pd.DataFrame:
                # For each item:
                #   1. translate to SQL (use translate_to_sql_fewshot)
                #   2. run validate_sql; if it fails, record status='rejected' and skip execution
                #   3. execute the SQL
                #   4. if gold_sql is present: compare with results_match (ignore_column_names=True)
                #      else: ask judge_answer
                #   5. record per-question outcome
                # Return a DataFrame with columns:
                #   question, sql, valid, status (rejected|pass|fail|error), reason
                raise NotImplementedError


            # report = evaluate_pipeline(TEST_SET)
            # print(report.to_string(index=False))
            """,
            solution="""
            def evaluate_pipeline(test_set: list[dict]) -> pd.DataFrame:
                rows = []
                for item in test_set:
                    q = item["question"]
                    gold = item.get("gold_sql")
                    sql = translate_to_sql_fewshot(q)
                    ok, why = validate_sql(sql)
                    if not ok:
                        rows.append({"question": q, "sql": sql, "valid": False, "status": "rejected", "reason": why})
                        continue
                    try:
                        df = execute_sql(sql)
                    except Exception as e:
                        rows.append({"question": q, "sql": sql, "valid": True, "status": "error", "reason": str(e)})
                        continue
                    if gold:
                        df_gold = execute_sql(gold)
                        passed = results_match(df_gold, df, ignore_column_names=True)
                        rows.append({
                            "question": q, "sql": sql, "valid": True,
                            "status": "pass" if passed else "fail",
                            "reason": "match_gold" if passed else "mismatch_gold",
                        })
                    else:
                        verdict = judge_answer(q, sql, df)
                        rows.append({
                            "question": q, "sql": sql, "valid": True,
                            "status": verdict.get("verdict", "fail"),
                            "reason": verdict.get("reason", ""),
                        })
                return pd.DataFrame(rows)


            report = evaluate_pipeline(TEST_SET)
            with pd.option_context("display.max_colwidth", 80):
                print(report.to_string(index=False))
            """,
            is_solution=is_solution,
        ),

        md("""
        ## Summary

        You now have:

        - A schema-aware, few-shot text-to-SQL translator.
        - A static validator that rejects non-`SELECT` and out-of-schema queries before they
          touch the database.
        - A read-only execution path with a row cap.
        - Two complementary correctness signals: result-set comparison (when a gold SQL exists)
          and LLM-as-judge (when it doesn't).
        - A harness that ties it all together into a measurable, repeatable evaluation.

        In Lab 2 we treat the same system from a **security** angle: what happens when the user
        is hostile, or when one user's data must be invisible to another?

        ## Exercises

        1. **Error recovery.** When `execute_sql` raises (e.g. an ambiguous column), feed the
           error message back to the translator and let it try again. Cap retries at 2.
        2. **Self-consistency.** Generate `n=3` candidate SQLs with `temperature=0.7`, execute
           each, and return the result that the majority agree on.
        3. **Cross-judge.** Replace `judge_answer` with two judges from different model families
           and only mark `pass` when both agree.
        4. **Cost report.** Extend `evaluate_pipeline` to record `usage.total_tokens` per call
           and report average tokens per question.
        """),
    ]


# ---------------------------------------------------------------------------
# Lab 2 — Text-to-SQL security
# ---------------------------------------------------------------------------

def build_lab2(is_solution: bool) -> list[dict]:
    suffix = " (Solutions)" if is_solution else ""
    return [
        md(f"""
        # Lab 2 — Text-to-SQL Security{suffix}

        Lab 1 produced a working text-to-SQL pipeline. This lab makes it **safe to ship**.

        We'll work in layers, from cheap to expensive:

        1. **Threat model.** What can go wrong, and which layer should stop each thing.
        2. **Output guardrails.** SELECT-only, table allow-list, row cap, statement count.
        3. **Execution guardrails.** Read-only connection, statement timeout.
        4. **Data isolation.** A per-user view pattern that makes it *physically impossible*
           for one user's question to read another user's rows.
        5. **Defence in depth.** Combine everything and attack it.

        ## Prerequisites

        - You completed Lab 1, or you are happy reading the reference solution.
        - `shop.db` exists next to this notebook (`python seed_db.py`).
        - `OPENAI_API_KEY` is set.
        """),

        md("## 1. Setup"),

        code("""
        import os
        import sqlite3
        from pathlib import Path

        import pandas as pd
        from dotenv import load_dotenv
        from openai import OpenAI
        import sqlglot
        from sqlglot import exp

        load_dotenv()
        DB_PATH = Path("shop.db")
        MODEL = "gpt-4o-mini"
        client = OpenAI()
        """),

        md("""
        ## 2. Threat model

        Take five minutes and ask: *if a malicious user can type anything into the question
        box, what bad outcomes are possible?* Below is a non-exhaustive starter list. The
        rest of the lab is organized around defending each of them.

        | # | Threat                                                       | Stopped by                                              |
        |---|--------------------------------------------------------------|---------------------------------------------------------|
        | 1 | "Delete all customers" — destructive DML/DDL                 | SELECT-only AST check                                   |
        | 2 | "What's in `users_secret`?" — read-anything                  | Table allow-list                                        |
        | 3 | Query that scans a 10M-row table for hours                   | Row cap + statement timeout                             |
        | 4 | Multi-statement payload: `SELECT 1; DROP TABLE customers;`   | Reject multiple top-level statements                    |
        | 5 | "Show me Alice's orders" (asked by Bob)                      | Per-user view / row-level isolation                     |
        | 6 | Prompt injection that smuggles a `UNION` to other tables     | Static SELECT scope + isolation (a malicious SQL still cannot reach outside the user's view) |

        Threats 1–4 are **output guardrails** (what the SQL is allowed to *say*).
        Threat 5 is **data isolation** (what the SQL is allowed to *see*, regardless of what
        it says).
        Threat 6 is a combination — neither layer alone is enough; both are.
        """),

        md("""
        ## 3. Output guardrails

        Re-introduce the validators from Lab 1, plus two new checks:

        - **Single statement.** `sqlglot.parse` returns a list; reject inputs with more than one.
        - **Enforced LIMIT.** If the query is unbounded, inject `LIMIT n` rather than failing
          (better UX than rejecting an otherwise valid question).
        """),

        code("""
        ALLOWED_TABLES = {"customers", "products", "orders", "order_items", "reviews"}
        MAX_ROWS = 100
        FORBIDDEN = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.AlterTable, exp.TruncateTable)


        def parse_one_or_raise(sql: str) -> exp.Expression:
            \"\"\"Reject inputs that contain more than one top-level statement.\"\"\"
            statements = [s for s in sqlglot.parse(sql, dialect="sqlite") if s is not None]
            if len(statements) != 1:
                raise ValueError(f"expected exactly one statement, got {len(statements)}")
            return statements[0]
        """),

        md("### TODO 3.1 — `enforce_limit`"),

        todo(
            student="""
            def enforce_limit(sql: str, max_rows: int = MAX_ROWS) -> str:
                # Parse the SQL.
                # If the top-level SELECT has no LIMIT, attach LIMIT max_rows.
                # If it has a LIMIT > max_rows, clamp it to max_rows.
                # Return the SQL string.
                # Hint: `tree.args.get("limit")` returns the existing LIMIT node or None.
                #       `tree.limit(max_rows)` returns a new tree with the LIMIT applied.
                raise NotImplementedError


            print(enforce_limit("SELECT name FROM customers"))
            print(enforce_limit("SELECT name FROM customers LIMIT 5"))
            print(enforce_limit("SELECT name FROM customers LIMIT 10000"))
            """,
            solution="""
            def enforce_limit(sql: str, max_rows: int = MAX_ROWS) -> str:
                tree = parse_one_or_raise(sql)
                existing = tree.args.get("limit")
                if existing is None:
                    tree = tree.limit(max_rows)
                else:
                    try:
                        current = int(existing.expression.this)
                    except Exception:
                        current = max_rows + 1
                    if current > max_rows:
                        tree = tree.limit(max_rows)
                return tree.sql(dialect="sqlite")


            print(enforce_limit("SELECT name FROM customers"))
            print(enforce_limit("SELECT name FROM customers LIMIT 5"))
            print(enforce_limit("SELECT name FROM customers LIMIT 10000"))
            """,
            is_solution=is_solution,
        ),

        md("### TODO 3.2 — `validate_sql_strict`"),

        todo(
            student="""
            def validate_sql_strict(sql: str, allowed: set[str] = ALLOWED_TABLES) -> tuple[bool, str]:
                # Must:
                #   - be exactly one statement (parse_one_or_raise)
                #   - be a SELECT
                #   - contain no FORBIDDEN expression types anywhere in the tree
                #   - reference only tables in `allowed`
                # Return (ok, reason).
                raise NotImplementedError


            for sample in [
                "SELECT * FROM customers",
                "SELECT 1; DROP TABLE customers",
                "DELETE FROM customers",
                "SELECT * FROM secret_table",
                "WITH x AS (DELETE FROM customers RETURNING *) SELECT * FROM x",
            ]:
                print(sample, "->", validate_sql_strict(sample))
            """,
            solution="""
            def validate_sql_strict(sql: str, allowed: set[str] = ALLOWED_TABLES) -> tuple[bool, str]:
                try:
                    tree = parse_one_or_raise(sql)
                except Exception as e:
                    return False, f"parse_error: {e}"
                if not isinstance(tree, exp.Select):
                    return False, "not_select"
                if any(isinstance(n, FORBIDDEN) for n in tree.walk()):
                    return False, "forbidden_node"
                tables = {t.name for t in tree.find_all(exp.Table)}
                bad = tables - allowed
                if bad:
                    return False, f"unknown_tables: {sorted(bad)}"
                return True, "ok"


            for sample in [
                "SELECT * FROM customers",
                "SELECT 1; DROP TABLE customers",
                "DELETE FROM customers",
                "SELECT * FROM secret_table",
                "WITH x AS (DELETE FROM customers RETURNING *) SELECT * FROM x",
            ]:
                print(sample, "->", validate_sql_strict(sample))
            """,
            is_solution=is_solution,
        ),

        md("""
        ## 4. Execution guardrails

        Even a perfectly validated `SELECT` can still hurt you:

        - A cartesian join over five tables.
        - A regex over a million `comment` strings.
        - A `LIKE '%...%'` triggering a full scan.

        Two cheap defences at the connection layer:

        1. **Read-only mode** — `sqlite3.connect("file:shop.db?mode=ro", uri=True)`. Bullet-
           proof: even a SELECT-only AST that mutated the DB via a SQLite extension would be
           blocked here.
        2. **Statement timeout** — SQLite exposes `set_progress_handler`. We register a
           callback that raises after N "ticks", which is roughly proportional to how long
           the query has been running.
        """),

        code("""
        class QueryTimeout(Exception):
            pass


        def execute_safely(sql: str, max_rows: int = MAX_ROWS, timeout_ticks: int = 1_000_000) -> pd.DataFrame:
            \"\"\"Read-only execution with a soft timeout and a hard row cap.

            `timeout_ticks` is *not* wall-clock time — it is the number of SQLite VM operations
            between progress callbacks. 1,000,000 is roughly a second on modern hardware.
            For real systems use a wall-clock timeout via a thread or subprocess.
            \"\"\"
            uri = f"file:{DB_PATH.as_posix()}?mode=ro"
            ticks = {"n": 0}

            def handler():
                ticks["n"] += 1
                if ticks["n"] > 100:
                    raise QueryTimeout("timeout")
                return 0  # 0 = continue, non-zero = abort

            with sqlite3.connect(uri, uri=True) as conn:
                conn.set_progress_handler(handler, timeout_ticks // 100)
                df = pd.read_sql_query(sql, conn)
            return df.head(max_rows)


        # Happy path
        print(execute_safely("SELECT name FROM customers LIMIT 5"))
        """),

        md("""
        ## 5. Data isolation — the per-user view pattern

        Output guardrails answer *what may the query do?*. They do **not** answer *which rows may
        the query see?*. For that, you need to make the rows the user shouldn't see invisible
        at the connection level — so even a perfectly valid SQL statement cannot reach them.

        Postgres has first-class **row-level security** (RLS) policies. SQLite doesn't. The
        portable pattern (also used in many SaaS deployments behind Postgres) is:

        > For each logged-in user, expose a **view** that is filtered to only their rows, and
        > give them a database role that can only read that view.

        Concretely:

        - Create a per-request **scratch database** that contains views like
          `my_orders`, `my_order_items`, `my_reviews`, filtered by `customer_id = :uid`.
        - Generate SQL against the scratch schema, not the global one.
        - The model never sees the real `customer_id` column and can never join its way to
          another user's rows.

        We'll implement this with SQLite's `ATTACH DATABASE` + `CREATE TEMP VIEW`, which is
        small enough to inspect end-to-end.
        """),

        md("### TODO 5.1 — `open_user_session`"),

        todo(
            student="""
            def open_user_session(customer_id: int) -> sqlite3.Connection:
                # Open a read-only connection to shop.db.
                # Create TEMP VIEWs that expose only this customer's data:
                #   my_profile     -> the single customer row
                #   my_orders      -> their orders
                #   my_order_items -> the order_items joined to their orders
                #   my_reviews     -> their reviews
                # Use parameterized statements so customer_id cannot be SQL-injected.
                # Return the open connection.
                raise NotImplementedError


            conn = open_user_session(1)
            print(pd.read_sql_query("SELECT * FROM my_profile", conn))
            print(pd.read_sql_query("SELECT order_id, status, total_amount FROM my_orders LIMIT 3", conn))
            conn.close()
            """,
            solution="""
            def open_user_session(customer_id: int) -> sqlite3.Connection:
                if not isinstance(customer_id, int):
                    raise TypeError("customer_id must be int")
                uri = f"file:{DB_PATH.as_posix()}?mode=ro"
                conn = sqlite3.connect(uri, uri=True)
                # We embed the integer ID directly — but only after type-checking it above.
                # Parameter binding doesn't work inside CREATE VIEW bodies on SQLite.
                cur = conn.cursor()
                cur.execute(f"CREATE TEMP VIEW my_profile AS SELECT customer_id, name, email, country, created_at FROM customers WHERE customer_id = {customer_id}")
                cur.execute(f"CREATE TEMP VIEW my_orders AS SELECT order_id, order_date, status, total_amount FROM orders WHERE customer_id = {customer_id}")
                cur.execute(f"CREATE TEMP VIEW my_order_items AS "
                            f"SELECT oi.order_item_id, oi.order_id, oi.product_id, oi.quantity, oi.unit_price "
                            f"FROM order_items oi JOIN orders o ON o.order_id = oi.order_id "
                            f"WHERE o.customer_id = {customer_id}")
                cur.execute(f"CREATE TEMP VIEW my_reviews AS SELECT review_id, product_id, rating, comment, review_date FROM reviews WHERE customer_id = {customer_id}")
                return conn


            conn = open_user_session(1)
            print(pd.read_sql_query("SELECT * FROM my_profile", conn))
            print(pd.read_sql_query("SELECT order_id, status, total_amount FROM my_orders LIMIT 3", conn))
            conn.close()
            """,
            is_solution=is_solution,
        ),

        md("""
        ### TODO 5.2 — text-to-SQL against the user view

        Build a translator that targets the *user-scoped schema*, not the real one. The model
        is told only about `my_profile`, `my_orders`, `my_order_items`, `my_reviews`, plus the
        read-only `products` catalogue.

        Notice what this buys you: even if the model wrote `SELECT * FROM my_orders`, it
        physically cannot see another customer's orders, because the view filters them out.
        """),

        todo(
            student="""
            USER_SCHEMA_DDL = \"\"\"
            -- catalogue (shared, read-only)
            CREATE TABLE products (
                product_id INTEGER PRIMARY KEY, name TEXT, category TEXT, price REAL, stock INTEGER
            );
            -- the current user's data
            CREATE VIEW my_profile     (customer_id, name, email, country, created_at);
            CREATE VIEW my_orders      (order_id, order_date, status, total_amount);
            CREATE VIEW my_order_items (order_item_id, order_id, product_id, quantity, unit_price);
            CREATE VIEW my_reviews     (review_id, product_id, rating, comment, review_date);
            \"\"\"

            ALLOWED_USER_TABLES = {"products", "my_profile", "my_orders", "my_order_items", "my_reviews"}


            def translate_user_sql(question: str) -> str:
                # TODO: build a system prompt that contains USER_SCHEMA_DDL and forbids
                # referencing customers / orders / order_items / reviews directly.
                # Reply with SQL only.
                raise NotImplementedError


            sql = translate_user_sql("How much did I spend on Electronics in total?")
            print(sql)
            """,
            solution="""
            USER_SCHEMA_DDL = \"\"\"
            -- catalogue (shared, read-only)
            CREATE TABLE products (
                product_id INTEGER PRIMARY KEY, name TEXT, category TEXT, price REAL, stock INTEGER
            );
            -- the current user's data
            CREATE VIEW my_profile     (customer_id, name, email, country, created_at);
            CREATE VIEW my_orders      (order_id, order_date, status, total_amount);
            CREATE VIEW my_order_items (order_item_id, order_id, product_id, quantity, unit_price);
            CREATE VIEW my_reviews     (review_id, product_id, rating, comment, review_date);
            \"\"\"

            ALLOWED_USER_TABLES = {"products", "my_profile", "my_orders", "my_order_items", "my_reviews"}


            def translate_user_sql(question: str) -> str:
                system = (
                    "You write SQLite SQL queries that answer questions about the current user's data.\\n"
                    "You may ONLY reference these objects: products, my_profile, my_orders, my_order_items, my_reviews.\\n"
                    "Do NOT reference customers, orders, order_items, or reviews directly.\\n"
                    "SQL only, no fences, no commentary.\\n\\nSchema:\\n" + USER_SCHEMA_DDL
                )
                resp = client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": question},
                    ],
                    temperature=0,
                )
                return resp.choices[0].message.content.strip().strip("`")


            sql = translate_user_sql("How much did I spend on Electronics in total?")
            print(sql)
            """,
            is_solution=is_solution,
        ),

        md("""
        ### Putting the user-scoped pipeline together

        Below we wrap everything: open a session for user 1, translate, validate against the
        user-scoped allow-list, then execute against the user's connection. Note that
        `execute_safely` accepts a connection argument — see the cell.
        """),

        code("""
        def validate_user_sql(sql: str) -> tuple[bool, str]:
            try:
                tree = parse_one_or_raise(sql)
            except Exception as e:
                return False, f"parse_error: {e}"
            if not isinstance(tree, exp.Select):
                return False, "not_select"
            if any(isinstance(n, FORBIDDEN) for n in tree.walk()):
                return False, "forbidden_node"
            tables = {t.name for t in tree.find_all(exp.Table)}
            bad = tables - ALLOWED_USER_TABLES
            if bad:
                return False, f"forbidden_tables: {sorted(bad)}"
            return True, "ok"


        def ask_as_user(customer_id: int, question: str) -> pd.DataFrame:
            sql = translate_user_sql(question)
            ok, why = validate_user_sql(sql)
            print(f"[user {customer_id}] SQL: {sql}")
            print(f"[user {customer_id}] validation: {ok} ({why})")
            if not ok:
                raise PermissionError(why)
            conn = open_user_session(customer_id)
            try:
                return pd.read_sql_query(sql, conn).head(MAX_ROWS)
            finally:
                conn.close()


        ask_as_user(1, "What is the total amount of all my orders?")
        """),

        md("""
        ## 6. Demonstrating isolation — three attacks, three defences

        Below are three attempted misuses. After each one, take a moment to ask yourself
        *which layer caught this?*
        """),

        md("### 6.1 — Destructive command"),

        code("""
        # The model is told never to mutate; even if a user begs, validate_sql_strict catches it.
        bad_sql = "DELETE FROM customers"
        print(validate_sql_strict(bad_sql))
        """),

        md("### 6.2 — Reading another user's data, the obvious way"),

        code("""
        # User 1 asks about user 2's orders.
        attempt = "SELECT order_id, total_amount FROM orders WHERE customer_id = 2"
        # Against the user-scoped allow-list this is rejected — the table 'orders' isn't allowed.
        print(validate_user_sql(attempt))
        """),

        md("""
        ### 6.3 — Reading another user's data, the sneaky way

        Suppose the model is somehow tricked (prompt injection, hostile question) into writing
        a query that *only* uses allowed objects but tries to reach a different customer's data
        through them. With the user view in place, the row filter is already applied — the
        rows are not in the result set, regardless of the WHERE clause.
        """),

        code("""
        # Even this passes validation (it only references my_orders), but the view physically
        # has no rows for customer_id != current user, so the WHERE clause matches nothing.
        sneaky = "SELECT order_id, total_amount FROM my_orders WHERE order_id IN (SELECT order_id FROM my_orders)"
        ok, why = validate_user_sql(sneaky)
        print("validation:", ok, why)

        # Open a session as user 1, then check: are there any rows where the row actually
        # belongs to user 2? There shouldn't be.
        conn = open_user_session(1)
        leak_check = pd.read_sql_query(
            \"\"\"SELECT COUNT(*) AS leaked_rows
               FROM my_orders mo
               JOIN main.orders o ON o.order_id = mo.order_id
               WHERE o.customer_id != 1\"\"\",
            conn,
        )
        print(leak_check)
        conn.close()
        """),

        md("""
        > Note: that leak-check query had to reach into `main.orders` (the real table) to even
        > pose the question. In a production setting you would not expose that table on the
        > user-scoped connection at all — for example by attaching `shop.db` under a sealed
        > schema and only granting access to the views. SQLite's permission model is weak;
        > Postgres's `GRANT` system makes this enforcement first-class.
        """),

        md("""
        ## 7. Defence in depth — end-to-end run

        One small interactive demo. We loop over a few questions and run them as two different
        users; you should see the same question return different rows depending on who asks.
        """),

        code("""
        questions = [
            "How many orders have I placed?",
            "Show me the products I have reviewed and my rating.",
            "What categories have I spent the most on?",
        ]

        for uid in (1, 2):
            print(f"\\n=== Asking as customer_id = {uid} ===")
            for q in questions:
                print(f"\\nQ: {q}")
                try:
                    df = ask_as_user(uid, q)
                    print(df.to_string(index=False))
                except Exception as e:
                    print("blocked:", e)
        """),

        md("""
        ## Summary

        You built three layers of defence and saw each one stop a different attack class:

        1. **Output guardrails** (AST checks, allow-list, single-statement, enforced LIMIT)
           — cheap, deterministic, applied before execution.
        2. **Execution guardrails** (read-only connection, soft timeout, row cap) — defend
           against ill-behaved-but-legal queries.
        3. **Per-user views** — the only layer that defends against the model *correctly*
           writing a query against the wrong data. Without this, a sufficiently clever
           prompt-injection could read across users.

        None of these layers is sufficient alone. Each one is cheap; together they are very
        hard to get around.

        ## Exercises

        1. **PII redaction.** Add a step that masks any `email` column in the response before
           returning it. The model must still be able to write queries referencing emails for
           filtering, but the values must never reach the user.
        2. **Audit log.** Append every translation + execution to a `query_log` table
           (separate database). Include the question, generated SQL, validation result, row
           count, and a hash of the user ID.
        3. **Adversarial test set.** Build a list of 10 hostile prompts (DML, cross-user
           reads, prompt injections) and assert that all of them are rejected. Add this as a
           regression test.
        4. **Postgres port.** Sketch how you would replace the temp-view trick with native
           Postgres RLS policies (`CREATE POLICY ... USING (customer_id = current_setting('app.user_id')::int)`).
           What is gained, what is lost?
        """),
    ]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    write_notebook("01_text_to_sql_pipeline", build_lab1(is_solution=False))
    write_notebook("01_text_to_sql_pipeline_solutions", build_lab1(is_solution=True))
    write_notebook("02_text_to_sql_security", build_lab2(is_solution=False))
    write_notebook("02_text_to_sql_security_solutions", build_lab2(is_solution=True))


if __name__ == "__main__":
    main()
