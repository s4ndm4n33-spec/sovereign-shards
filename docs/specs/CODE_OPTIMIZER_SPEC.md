A P P E N D I X   F

Code Optimizer v1: Technical Specification

The Code Optimizer is the first product capability of the Sovereign Shards
framework. It accepts Python source code, analyses it against the Five
Masters engineering standards, and produces refactored output that is
cleaner, lighter, and functionally equivalent to the original — or
provably better.

This specification is designed to be replicable and reproducible. Any
developer with a working Sovereign Shard can build and verify this system.


1. PURPOSE

  Code goes in. Five Masters judge it. Issues are identified. Fixes are
  applied. Code comes out — leaner, cleaner, and compliant with the
  engineering standards that define what "good code" means in this system.

  The optimizer is NOT a linter. Linters report. The optimizer transforms.

  The optimizer is NOT an AI wrapper. Detection is pure AST — zero
  inference cost. The LLM is invoked only for rewrites that require
  semantic understanding (renaming for clarity, restructuring logic,
  collapsing redundancy). Deterministic fixes are applied directly.


2. ARCHITECTURE

  ┌─────────────┐    ┌──────────────┐    ┌──────────────┐
  │  INPUT       │───▶│  ANALYSIS    │───▶│  PLAN        │
  │  (source)    │    │  (AST+5M)    │    │  (fix list)  │
  └─────────────┘    └──────────────┘    └──────┬───────┘
                                                │
                     ┌──────────────┐    ┌──────▼───────┐
                     │  VERIFY      │◀───│  TRANSFORM   │
                     │  (sandbox)   │    │  (apply)     │
                     └──────┬───────┘    └──────────────┘
                            │
                     ┌──────▼───────┐
                     │  OUTPUT      │
                     │  (optimised) │
                     └──────────────┘

  Five stages. Each is independently testable.

  Stage 1 — INPUT
    Accept a file path or raw source string.
    Parse via ast.parse(). If SyntaxError, reject — the optimizer does
    not fix broken syntax.

  Stage 2 — ANALYSIS
    Run the full Five Masters evaluation (core/fivemasters.py).
    Run the refactoring scanner (app/agent/refactor.py) for cross-file
    context when a project root is provided.
    Produce a structured issue list: master, line, message, severity,
    and a new field — fix_type: "deterministic" or "semantic".

  Stage 3 — PLAN
    Sort issues by severity (errors first), then by line number.
    Group deterministic fixes (can be applied via AST transformation
    without model inference) and semantic fixes (require the LLM to
    understand intent).
    Produce an ordered fix plan. Each fix includes:
      - issue: the original Issue object
      - strategy: what transformation to apply
      - estimated_impact: lines affected

  Stage 4 — TRANSFORM
    Apply deterministic fixes via AST node replacement (no model).
    Apply semantic fixes by sending targeted prompts to the LLM with
    only the affected function/block as context (not the whole file).
    After each fix, re-parse the AST to confirm validity.
    If a fix breaks the AST, revert it and move to the next.

  Stage 5 — VERIFY
    Run the modified source through the sandbox:
      - ast.parse() — still valid Python
      - Five Masters re-evaluation — score must not decrease
      - If tests exist, run them — no regressions
    Produce a before/after report.


3. DETERMINISTIC FIXES (Zero Inference Cost)

  These transformations are applied purely through AST manipulation.
  No model. No tokens. No latency.

  MASTER         PATTERN                           TRANSFORMATION
  ──────────────────────────────────────────────────────────────────────
  Korotkevich    for i in range(len(x)):           for i, item in enumerate(x):
                   ... x[i] ...                      ... item ...

  Torvalds       except:                           except Exception:
                   pass                               logger.error(...)
                                                      raise

  Torvalds       except Exception:                 except Exception:
                   (no log, no raise)                 logger.error(...)
                                                      raise

  Carmack        def f(x, data=[]):                def f(x, data=None):
                                                      if data is None:
                                                          data = []

  Carmack        global var_name                   (refactor to parameter
                                                    passing — flag for
                                                    semantic fix if complex)

  Hamilton       open(...) outside try             wrap in try/except with
                                                    specific exception type

  Ritchie        camelCase function name           snake_case (with rename
                                                    propagation via refactor.py)


4. SEMANTIC FIXES (Model-Assisted)

  These require the LLM because the transformation depends on
  understanding what the code does, not just its structure.

  - Function too long (>60 lines): ask the model to identify logical
    boundaries and split into helper functions.
  - Excessive nesting (>4 levels): ask the model to restructure using
    early returns or guard clauses.
  - Dead code removal: the refactoring scanner identifies unused symbols,
    but the model confirms they're truly unused (not called dynamically).
  - Complex global refactoring: when a global variable is woven through
    multiple functions, the model plans the parameter-passing migration.

  Semantic fix prompts follow a strict template:

    You are refactoring a single Python function. The Five Masters
    identified this issue:
      [ISSUE]
    Here is the function:
      [CODE BLOCK]
    Rewrite ONLY this function. Preserve exact behaviour. Return only
    the Python code, no explanation.

  The model sees only the affected block — never the full file. This
  minimises context usage and prevents hallucinated changes elsewhere.


5. THE FIVE MASTERS SCORING CONTRACT

  Before/after scoring uses the existing evaluate_code() API.

  A Master "passes" if:
    - Zero errors attributed to that Master, AND
    - Two or fewer warnings attributed to that Master.

  Optimisation success requires:
    - after.score() >= before.score()
    - No new errors introduced
    - If tests exist: all still pass

  If any condition fails, the optimiser reverts ALL changes and returns
  the original source with a diagnostic report.


6. CORE ETHICS

  The Code Optimizer inherits the full alignment framework of the
  Sovereign Shards project. These are not guidelines — they are
  constraints enforced in code.

  6.1 — PRESERVE BEHAVIOUR

    The optimizer MUST NOT change what the code does. It changes how the
    code is written. Functional equivalence is the inviolable constraint.
    If equivalence cannot be proven (via tests or AST comparison), the
    fix is not applied.

  6.2 — NEVER MAKE CODE WORSE

    The Five Masters score after optimisation must be greater than or
    equal to the score before. If a "fix" introduces a new issue in a
    different Master's domain, it is reverted.

  6.3 — RESPECT THE DEVELOPER'S INTENT

    The optimizer does not impose style preferences beyond the Five
    Masters standards. If a developer uses a pattern that passes all
    five Masters, the optimizer does not touch it — even if a
    "cleaner" alternative exists. The Masters are the law. Nothing else.

  6.4 — TRANSPARENCY

    Every transformation is logged. The before/after report shows
    exactly what changed, why (which Master, which rule), and what
    the impact was. No black-box modifications. Ritchie demands that
    the mechanism is visible.

  6.5 — SAFE DEFAULTS

    If the optimizer encounters code it cannot safely transform — dynamic
    exec(), metaprogramming, C extensions, code that modifies its own
    AST — it flags the issue but does not attempt a fix. Hamilton's rule:
    when in doubt, do nothing.

  6.6 — LOCAL FIRST

    The optimizer runs entirely on the shard. No code leaves the machine.
    No telemetry. No cloud analysis. The developer's source code is
    sovereign — it stays on the hardware they own.


7. FILE STRUCTURE

  The optimizer adds three files to the existing codebase:

  app/agent/optimizer.py        — Main pipeline (5 stages)
  app/agent/transforms.py       — Deterministic AST transformations
  tests/test_optimizer.py       — Test suite for the optimizer

  No new dependencies. No new config. The optimizer uses:
    - core/fivemasters.py (analysis)
    - app/agent/refactor.py (cross-file context)
    - app/agent/sandbox.py (verification)
    - app/client.py (LLM for semantic fixes, optional)


8. CLI INTERFACE

  The optimizer is invoked via the existing /command router:

    /optimize path/to/file.py        Optimize a single file
    /optimize path/to/directory      Optimize all .py files in a directory
    /optimize --dry-run file.py      Report issues without applying fixes
    /optimize --no-model file.py     Deterministic fixes only (no LLM)
    /optimize --diff file.py         Show unified diff of changes

  The --no-model flag is critical for environments where the model
  server is not running or RAM is constrained. Deterministic fixes
  alone can resolve a significant portion of Five Masters violations.


9. OUTPUT FORMAT

  ┌──────────────────────────────────────────────────────────────────┐
  │  Five Masters Code Optimizer — Report                           │
  │                                                                 │
  │  File: app/agent/planner.py                                     │
  │  Before: 3/5 Masters  │  After: 5/5 Masters                    │
  │                                                                 │
  │  Fixes Applied: 4                                               │
  │  ├─ [Korotkevich] L42: range(len()) → enumerate()              │
  │  ├─ [Torvalds]    L58: bare except → except Exception + log    │
  │  ├─ [Carmack]     L12: mutable default arg → None guard        │
  │  └─ [Hamilton]    L77: unguarded open() → try/except wrapped   │
  │                                                                 │
  │  Skipped: 1                                                     │
  │  └─ [Ritchie] L23: function 72 lines — needs semantic split    │
  │     (use --model to enable LLM-assisted refactoring)            │
  │                                                                 │
  │  Tests: 12 passed, 0 failed, 0 errors                          │
  └──────────────────────────────────────────────────────────────────┘


10. REPLICABILITY REQUIREMENTS

  To reproduce this system from scratch:

  1. A working Python 3.10+ interpreter (stdlib only — ast, os,
     pathlib, shutil, tempfile, subprocess, re, json, dataclasses).

  2. The Five Masters evaluation engine (core/fivemasters.py).
     377 lines. Five AST visitors. Produces a scored report.

  3. The AST transformation library (app/agent/transforms.py).
     Each transform is a function: (ast.Module, Issue) → ast.Module.
     Pure AST. No string manipulation. No regex on code.

  4. The sandbox (app/agent/sandbox.py) for verification.

  5. Optionally, a running LLM server for semantic fixes.
     The optimizer degrades gracefully without it — deterministic
     fixes still apply.

  The entire system can be rebuilt by anyone who reads this spec and
  has access to the Python standard library. That is the point. If
  Sovereign Intelligence means anything, it means the tools are yours
  to build, not yours to rent.


11. ROADMAP

  v1.0 — Single-File Optimizer (this spec)
    Deterministic + semantic fixes for individual Python files.

  v2.0 — Multi-File Optimizer
    Uses refactor.py's ProjectMap to optimise across file boundaries.
    Rename propagation, dead import cleanup, circular dependency
    resolution. The task graph parallelises independent file optimisations.

  v3.0 — Codebase Forge
    Point it at a repository. It maps the architecture (refactor.py),
    prioritises files by Five Masters score (worst first), and works
    through them systematically. Every change is sandbox-verified.
    Circuit breaker halts if too many consecutive fixes fail.

  The Forge is the capstone. Code goes in. The Five Masters judge it.
  What comes out is cleaner, lighter, smarter code that performs just
  as well if not better than the original — saving space and increasing
  efficiency. Systems that persist.
