# reachy-aiden

reachy-aiden turns a Reachy Mini Wireless robot into a voice companion with its own persona, long-term memory, and extra tools. You can switch its voice backend between Hugging Face, OpenAI, and Gemini with one command. It is the setup behind Aiden, the robot companion I built and use every day, packaged so that anyone with a Reachy Mini Wireless can install it, give their robot its own name and personality, and get the same behavior.

It runs entirely on the robot and on cloud voice models. You do not need a computer running in the background once it is installed.

## Why it exists

Out of the box, the Reachy Mini conversation app talks, moves, and sees, but each session starts fresh, the robot answers anything it hears, and every app update resets your changes. Getting Aiden to wait for his name, remember past conversations, start on his own at boot, and survive updates took months of testing. This repository holds the results so the next owner can skip that work.

## Demo

[![Aiden (cloud) and Rose (local) in conversation](https://img.youtube.com/vi/L9EhXOoIOt4/hqdefault.jpg)](https://youtu.be/L9EhXOoIOt4)

## What you get

- **A persona you write.** A template persona with rules that were tuned on a real robot: the robot speaks when addressed by name and stays silent otherwise, has an emergency mute phrase, keeps your personal details private from guests, and has a presentation mode for classrooms.
- **Memory.** Every conversation is logged on the robot. Once a day, and at each boot or backend switch, an OpenAI model extracts the moments worth keeping. During conversation the robot searches those memories with a `recall_memories` tool. You can also add permanent memories by hand.
- **One-command backend switching.** `companion-switch huggingface`, `companion-switch openai`, or `companion-switch gemini` sets the provider, model, connection mode, voice, and keys together, then restarts the robot.
- **Protection from updates.** At every boot, a guard service checks for the changes an update removed and puts them back.
- **Wakes up on its own.** The robot starts its conversation app at boot, so it works away from home on any known Wi-Fi network.
- **Extra tools:** time, weather, speaker volume, microphone mute and gain, shutdown on "goodnight", and a self-description tool the robot uses to answer questions about how it works. An optional read-only Google Calendar tool is in `extras/`.
- **Turn-taking and movement tuning:** longer pauses before the robot replies, smoother face tracking, and head movements that return to center first.

## Before you buy: hardware

| Item | Notes |
| --- | --- |
| [Reachy Mini **Wireless**](https://store.pollen-robotics.com/collections/reachy-mini) | Required. The Wireless version has a Raspberry Pi inside, and this project installs onto that Pi. The Lite version has no onboard computer and is not supported. Check the store for current price and shipping time. |
| Wi-Fi network | The robot needs internet access for the cloud voice models. A phone hotspot works for travel (see `extras/wifi-watchdog`). |
| A computer | Windows, macOS, or Linux, for the one-time setup over SSH. |

What to expect when it arrives:

- The robot comes as a kit. Assemble it with Pollen Robotics' guide, then connect it to Wi-Fi and update it with the **Reachy Mini desktop app**.
- From the desktop app, install the **Reachy Mini Conversation App** and talk to the robot once to confirm that the microphones, speaker, and motors work. Do this before installing reachy-aiden. If the stock app does not work, this project will not fix it.
- Pollen Robotics documentation and community: [github.com/pollen-robotics/reachy_mini](https://github.com/pollen-robotics/reachy_mini) and the [Reachy Mini blog post on Hugging Face](https://huggingface.co/blog/reachy-mini).

## Software and accounts

| Requirement | Version or notes |
| --- | --- |
| Reachy Mini Conversation App | Tested with **0.6.2**. Other versions usually work; the installer reports anything it could not apply. |
| Robot software | The Python 3.12 environments that ship on the robot (`/venvs/apps_venv`, `/venvs/mini_daemon`). Nothing extra to install. |
| Hugging Face account | Optional. The default Hugging Face backend works without a key. A free [access token](https://huggingface.co/settings/tokens) avoids `401 Unauthorized` errors. |
| OpenAI API key | Needed for memory extraction and for the OpenAI voice backend. Usage is billed by OpenAI. [Get a key](https://platform.openai.com/api-keys). |
| Gemini API key | Only for the Gemini backend. [Get a key](https://aistudio.google.com/apikey). |

## Installation

All commands after step 1 run on the robot.

1. **Connect to the robot.** From a terminal on your computer (PowerShell on Windows):

   ```bash
   ssh pollen@reachy-mini.local
   ```

   Use the password from Pollen's documentation. If `reachy-mini.local` does not resolve (common on phone hotspots), use the robot's IP address from your router's or phone's list of connected devices.

2. **Download this project onto the robot:**

   ```bash
   cd ~
   git clone https://github.com/reijinarudo/reachy-aiden.git
   cd reachy-aiden
   ```

   If `git` is missing: `sudo apt-get install -y git`.

3. **Create your configuration file** from the example and fill it in:

   ```bash
   cp .env.example companion.env
   nano companion.env
   ```

   At minimum set `ROBOT_NAME`, `OWNER_NAME`, and `OPENAI_API_KEY` (for memory). Set `WEATHER_LATITUDE` and `WEATHER_LONGITUDE` for local weather. Save with Ctrl+O, Enter, then exit with Ctrl+X.

4. **Run the installer:**

   ```bash
   bash install.sh
   ```

   It copies your configuration to `/etc/reachy-companion/companion.env`, creates your robot's profile from the template, installs the tools, scripts, commands, and services, and applies the conversation app changes. It finishes with a report like this:

   ```text
   [APPLIED] App .env - backend=huggingface
   [APPLIED] Daemon launcher - profile=Pixel, wake-up on start
   [APPLIED] Session greeting (COMPANION_GREETING)
   ...
   10 change(s) made. 0 item(s) need attention.
   ```

   After installing, delete `companion.env` from the project folder (`rm companion.env`). The robot uses the copy in `/etc/reachy-companion/`.

5. **Write your persona.** Open `/home/pollen/profiles/<ROBOT_NAME>/instructions.txt` and replace every `{PLACEHOLDER}` with your own details. Your robot's name and yours are already filled in. Read [docs/PERSONA_GUIDE.md](docs/PERSONA_GUIDE.md) first; it explains which rules to keep and why.

6. **Restart the robot software:**

   ```bash
   sudo systemctl restart reachy-mini-daemon
   ```

   Wait about a minute. The robot raises its head, the conversation app starts, and the robot says its greeting ("Hello world." by default). Say its name and talk.

7. **Check that everything is running:**

   ```bash
   companion-status
   ```

## Configuration

All settings live in `/etc/reachy-companion/companion.env`. The annotated template is [.env.example](.env.example). After editing it, run:

```bash
sudo companion-reapply
sudo systemctl restart reachy-mini-daemon
```

| Setting | What it controls |
| --- | --- |
| `ROBOT_NAME`, `OWNER_NAME` | Profile folder name, tool descriptions, memory transcripts |
| `COMPANION_GREETING` | Words spoken when a session opens. Empty turns it off. |
| `BACKEND_PROVIDER` | `huggingface`, `openai`, or `gemini` |
| `HF_REALTIME_CONNECTION_MODE` | `deployed` (Pollen's cloud server) or `local` (your own server at `HF_REALTIME_WS_URL`) |
| `OPENAI_API_KEY`, `GEMINI_API_KEY`, `HF_TOKEN` | Keys for each service |
| `VOICE_OPENAI`, `VOICE_HUGGINGFACE`, `VOICE_GEMINI` | Voice used on each backend |
| `OPENAI_SILENCE_MS`, `HF_SILENCE_MS`, and the threshold values | How long the robot waits after you stop talking, and how loud speech must be |
| `MEMORY_ENABLED`, `SUMMARIZER_MODEL` | Memory extraction on or off, and which model does it |
| `WEATHER_*` | Default weather location and units |

The provider name does not tell you where your audio goes. With `BACKEND_PROVIDER=huggingface`, the connection mode decides it: `deployed` uses Pollen's hosted server and `local` uses whatever address is in `HF_REALTIME_WS_URL`. `companion-switch` sets both together.

## Usage

Talk to the robot by name. Some phrases from the persona template, shown here for a robot named Aiden:

| Say | Result |
| --- | --- |
| "Aiden, mute now" | Mutes the microphone. Unmute from the desktop app or with `amixer -c 0 sset 'Headset',0 cap`. |
| "Aiden, do you remember ...?" | Searches memories |
| "Aiden, address the room" | Presentation mode: a short self-introduction to an audience |
| "Aiden, thank you" | Ends the robot's turn, or ends presentation mode |
| "Goodnight, Aiden" | Says goodnight and powers down |

Commands on the robot:

| Command | Purpose |
| --- | --- |
| `companion-status` | Backend, app state, services, microphone, and patch status on one screen |
| `companion-switch huggingface` / `openai` / `gemini` | Change the voice backend |
| `companion-switch` | Show the current backend |
| `sudo companion-reapply` | Re-apply all changes, for example after an update |
| `sudo companion-reapply --check` | Report without changing anything |
| `companion-add-memory "text" --date YYYY-MM-DD --tags a,b` | Add a permanent memory, written from the robot's point of view |

More commands, including logs and recovery steps, are in [docs/COMMANDS.md](docs/COMMANDS.md).

## Updates, the stock app, and keeping your setup

This is the part most likely to cause trouble later, so read it before you update anything.

**What an update does.** When you update the robot or the conversation app from the Reachy Mini desktop app, Pollen's installer replaces the app's files in `/venvs/`. That removes the code changes this project makes and the launcher settings that load your profile. Your robot comes back with the stock persona, or does not start its conversation app at boot.

**What survives.** Your persona, tools, memories, logs, and configuration live in `/home/pollen` and `/etc/reachy-companion`, which updates do not touch.

**How this project protects you.**

1. `companion-boot-guard.service` runs at every boot, before the conversation app starts. If an update removed anything, it puts the changes back and restarts the daemon.
2. After any update you can also run `sudo companion-reapply` yourself and read its report. Each change is applied only where the expected code is found. If a new app version changed that code, the item is reported as `WARNING` and left alone, so an update never leaves a file half-edited.
3. Before each change, the original file is copied to `/home/pollen/companion-backups/`.

**The desktop app's settings panel.** The conversation app has its own settings screen for backend, profile, and voice. It writes to the same `.env` file that `companion-switch` manages. If you change the backend there, run `companion-switch <backend>` afterwards so the provider, connection mode, and voice stay consistent. Choosing a local Hugging Face server in that panel sends your audio to that address until you switch back.

**If you want full control,** you have two further options:

- Hold off on conversation app updates until you have read the release notes, then run `sudo companion-reapply --check` right after updating.
- Build your own conversation app on the Reachy Mini SDK and run it in place of Pollen's. An AI coding assistant such as Claude can write most of one with you. The tools in `tools/` and the memory scripts in `companion/` work with any app that follows the same tool interface.

## How it works

```text
 you speak
    |
 [Reachy Mini Wireless]  microphones -> conversation app (Pollen, patched) -> speaker, motors
    |                                  |
    |                                  +-- persona:  /home/pollen/profiles/<ROBOT_NAME>/
    |                                  +-- tools:    /home/pollen/tools/*.py
    |                                  +-- realtime voice model (Hugging Face / OpenAI / Gemini)
    |
    +-- conversation-logger  -> /home/pollen/conversation-logs/conversation-YYYY-MM-DD.jsonl
    +-- memory-summarizer (daily, 3 a.m.) and memory-catchup (boot, backend switch)
    |        -> /home/pollen/companion-memories/memories.jsonl
    +-- recall_memories tool reads memories.jsonl and permanent-memories.jsonl
```

## Project layout

```text
reachy-aiden/
├── install.sh, uninstall.sh       install and remove, run on the robot
├── .env.example                   every setting, with comments
├── bin/                           companion-switch, -reapply, -status, -add-memory
├── companion/                     apply_patches.py, memory scripts, boot scripts
├── tools/                         tools the robot can call during conversation
├── systemd/                       services and timer
├── profile_template/              persona, memory prompt, self-description, tools list
├── patches/
│   ├── files/move_head.py         modified upstream file (Apache-2.0)
│   └── reference/*.diff           every change to the upstream app, for review
├── extras/calendar/               optional Google Calendar tool
├── extras/wifi-watchdog/          optional restart after Wi-Fi reconnect
├── docs/                          commands, troubleshooting, persona guide
└── third_party/                   upstream license
```

## Troubleshooting

The most common problems and their fixes are in [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md): the robot hears nothing after a reboot, garbled voice after repeated restarts, `401 Unauthorized` on the Hugging Face backend, the robot answering when nobody addressed it, and persona edits that do not load.

## Credits

This project builds on the work of others:

- **[Reachy Mini Conversation App](https://github.com/pollen-robotics/reachy_mini_conversation_app)** by [Pollen Robotics](https://www.pollen-robotics.com/), Apache License 2.0. The realtime conversation loop, motion system, vision, and built-in tools are theirs. This project changes seven of its files in place; see `patches/reference/`. The original license is in `third_party/reachy_mini_conversation_app/LICENSE`.
- **[Reachy Mini SDK and robot software](https://github.com/pollen-robotics/reachy_mini)** by Pollen Robotics, with [Hugging Face](https://huggingface.co/).
- **Hugging Face realtime backend**, hosted by Pollen Robotics and Hugging Face.
- **[Open-Meteo](https://open-meteo.com/)** for the free weather and geocoding APIs used by the weather tool (data licensed CC BY 4.0).
- Developed with the help of Anthropic's Claude.

## Modifications

Everything below was designed, tested, and tuned by me on a working robot between April and October 2026.

**Changes inside Pollen's conversation app** (applied by `companion/apply_patches.py`):

1. Spoken greeting at the start of every session, so you know at a glance that the session is alive (configurable with `COMPANION_GREETING`).
2. Turn-taking tuned for conversation: the OpenAI backend waits 800 ms of silence and the Hugging Face backend waits 1200 ms before replying, with a higher speech threshold (0.7) so background noise does not trigger a reply.
3. Face tracking eased with smoothing, so the head follows a face without jerking, and off by default at startup.
4. Full-length transcript lines in the log (the stock app cuts them at 500 characters), so the memory pipeline sees whole conversations.
5. MediaPipe set as the default head tracker.
6. `move_head` rewritten: the head returns to center before turning, looks down at a gentler angle, and finishes the move before the robot speaks again.
7. Daemon launcher set to wake the motors at startup and to load your profile and tools folder.

**Added by this project:**

- Persona template and writing guide, distilled from months of testing what makes a small voice model wait its turn.
- Memory pipeline: conversation logger, daily summarizer with a memory extraction prompt, boot-time catch-up that refreshes today's memories safely, permanent memories, and the `recall_memories` tool with relevance ranking.
- `companion-switch`, which sets provider, model, Hugging Face connection mode, voice, and keys together.
- Boot guard and `companion-reapply`, which restore the changes after updates.
- Boot autostart, so the robot comes online without the desktop app.
- Microphone unmute at boot, which prevents the robot from starting up deaf after a saved mute.
- Persona hot reload when `instructions.txt` is saved.
- Tools: time, weather, speaker volume, microphone mute, microphone gain, shutdown, self-description, and an optional read-only Google Calendar.
- Optional Wi-Fi reconnect watchdog for travel between networks.

## License

My own code and documentation are released under the [MIT License](LICENSE). Files derived from Pollen Robotics' conversation app (`patches/files/move_head.py` and the diffs in `patches/reference/`) remain under the [Apache License 2.0](third_party/reachy_mini_conversation_app/LICENSE).

## Contact

Dr. Reginald Finley, [contact@drreginaldfinley.com](mailto:contact@drreginaldfinley.com), [drreginaldfinley.com](https://drreginaldfinley.com)
