# Leaderboard

Scores are reported against the 10-scenario conformance suite
(`memory_tool_conformance.conformance.run_conformance`).

*Auto-updated by CI on every push to main.*  Last run: 2026-05-02 18:56 UTC.

| Implementation | Score | Notes |
|---|:-:|---|
| `memory_tool_conformance.reference.fs_memory:FilesystemMemory` | **10 / 10** | Built-in reference implementation |

## Adding your server

1. Implement a factory function that returns a conformant instance:
   ```python
   def make_server():
       return MyMemoryServer(...)
   ```
2. Run the suite:
   ```bash
   memory-conformance --target mypkg.memory:make_server --name "my-server"
   ```
3. Open a PR adding a row to `leaderboard_entries.json`:
   ```json
   [
     {
       "name": "my-server",
       "target": "mypkg.memory:make_server",
       "notes": "My custom backend"
     }
   ]
   ```
