# Test fixtures

- `mock_engine.lua`: stand-in for the engine object model (proxies without `pairs`, one-level
  `log(obj)` listing in the format seen in a public player log from 2023). Used to run the dump
  script with a stock Lua 5.4 interpreter.
- `dump_mock.log`: output of the dump script run against `mock_engine.lua`, wrapped in log header
  lines in the engine format (CRLF, timestamps). Regenerate with `python scripts/make_dump_fixture.py`.

No real game files.
