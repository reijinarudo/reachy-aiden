# Troubleshooting

Start every diagnosis by looking at the logs. Most problems in this project turned out to have a different cause than the first guess, and the logs showed the cause each time.

```bash
companion-status
sudo journalctl --since "5 minutes ago" --no-pager | tail -40
sudo journalctl -u reachy-mini-daemon --since "10 minutes ago" --no-pager | tail -40
```

## The robot hears nothing after a reboot

The microphone has two capture controls on ALSA card 0:

- `'Headset',0` is the on/off switch. `[on]` means unmuted.
- `'Headset',1` is the capture level, 0 to 60. After a daemon restart it sometimes comes back at 0.

```bash
amixer -c 0 sget 'Headset',0           # look for [on] on Front Left and Front Right
amixer -c 0 sset 'Headset',0 cap       # unmute
amixer -c 0 sset 'Headset',1 60        # restore the level
```

`companion-mic-unmute.service` does both at every boot.

Do not run `sudo alsactl store` while the robot is muted, including after a voice mute earlier in the session. That command saves the current mixer state as the boot default, and the robot would then start muted every time. Check `amixer -c 0 sget 'Headset',0` first.

The conversation app's listening indicator reads the level control, so it can show activity while the on/off switch is off. If the app says it hears you and the robot does not answer, check `'Headset',0`.

## The robot answers when nobody spoke to it, or talks over you

1. Check the persona. Keep the "When I Speak" section and the closing anchor from the template. See [PERSONA_GUIDE.md](PERSONA_GUIDE.md).
2. Raise the silence time in `/etc/reachy-companion/companion.env` (`HF_SILENCE_MS` or `OPENAI_SILENCE_MS`, in steps of 200), then `sudo companion-reapply` and restart the daemon.
3. Raise the threshold (`HF_VAD_THRESHOLD`, `OPENAI_VAD_THRESHOLD`) toward 0.8 in a noisy room.

## Garbled voice, repeated sounds, or a warped voice

This happens after many app restarts in a row. The session ends up in a bad state; the persona and memory files are unaffected. Reload the session on the current backend:

```bash
companion-switch huggingface     # or whichever backend you use
```

If it persists, restart the daemon: `sudo systemctl restart reachy-mini-daemon`.

## Hugging Face backend: `401 Unauthorized`

The log shows `401 Unauthorized` from `pollen-robotics-reachy-mini-realtime-url.hf.space/session`. Create a new read token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens), put it in `HF_TOKEN` in `/etc/reachy-companion/companion.env`, then:

```bash
sudo companion-reapply
companion-switch huggingface
```

A repeating `central_signaling_relay ... Authentication failed` message appears on every backend and is unrelated to this error.

## Hugging Face backend: "waiting for the server" or no answer

Check the connection mode:

```bash
companion-switch
```

`HF connection: local` means the app is trying to reach your own server at `HF_REALTIME_WS_URL`. If you meant to use Pollen's cloud server, set `HF_REALTIME_CONNECTION_MODE=deployed` in the config and run `companion-switch huggingface`. The settings panel in the desktop app can change this value without you noticing.

## Persona edits do not take effect

- Save the file in place: an SFTP editor (WinSCP, or Notepad++ with the NppFTP plugin), `nano`, or a `sed -i` command. Replacing the file with `mv` or by uploading a new copy can break the watcher. Restart it with `sudo systemctl restart instructions-watcher`.
- Force a reload: `curl -s -X POST http://localhost:8000/api/apps/restart-current-app`

## The app will not start

- `"already running"`: use `curl -s -X POST http://localhost:8000/api/apps/restart-current-app`.
- `"No app is currently running"`: use `curl -s -X POST http://localhost:8000/api/apps/start-app/reachy_mini_conversation_app`.
- Still stuck: `sudo systemctl restart reachy-mini-daemon`, then reboot as the last step.

## After an update the robot lost its persona or tools

```bash
sudo companion-reapply
sudo systemctl restart reachy-mini-daemon
```

Read the report. `WARNING` lines mean the new app version changed code this project edits. The robot still runs; that one adjustment is missing until the patch is updated.

## The robot cannot be reached on a phone hotspot

`reachy-mini.local` relies on mDNS, which many hotspots block. Use the robot's IP address from the hotspot's list of connected devices: `ssh pollen@192.168.x.x`. The address may change each time.

## Memory is not working

```bash
sudo journalctl -u memory-catchup.service -n 30 --no-pager
ls -l /home/pollen/conversation-logs/ /home/pollen/companion-memories/
sudo journalctl --since "2 minutes ago" --no-pager | grep recall_memories
```

- No log files: check `systemctl status conversation-logger`.
- Logs but no memories: check `OPENAI_API_KEY` and `MEMORY_ENABLED=1` in the config.
- Memories exist but the robot does not use them: confirm `recall_memories` appears in the tool list in the journal at startup, and ask with a cue such as "do you remember".
- Testing recall repeatedly creates memories about the testing itself. Open `memories.jsonl` and delete those lines now and then.
