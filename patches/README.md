# Changes to Pollen's conversation app

`companion/apply_patches.py` makes these changes on the robot. This folder exists so you can review exactly what is changed before installing.

- `reference/*.diff`: each change as a unified diff against `reachy_mini_conversation_app` 0.6.2. The greeting diff shows the original fixed "Hello world." line; the installed version reads the text from `COMPANION_GREETING`. The VAD values in the diffs are the defaults; yours come from the config file.
- `files/move_head.py`: the full modified `move_head` tool, which replaces the original when its contents match 0.6.2 exactly.

The original code is Copyright Pollen Robotics and licensed under the Apache License 2.0 (`third_party/reachy_mini_conversation_app/LICENSE`). The modified file carries a notice stating that it was changed.
