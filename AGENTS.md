# Development guidelines

- Keep the project modular and make changes small and focused.
- Keep orchestration in `agent/core`, model communication contracts and adapters in `agent/llm`, and tool definitions and registration in `agent/tools`.
- The core must not depend on LM Studio-specific details; put provider configuration behind the LLM layer.
- Add type hints to Python code, including function parameters and return values.
- Preserve existing behavior unless a requested change explicitly requires changing it.
- Add or update tests when behavior changes. Do not create artificial tests just to populate directories.
- Run the existing test suite after changes and report any tests that could not run.
- Do not add dependencies without a clear justification.
- Avoid unrelated code changes and large abstractions that do not serve a current need.
