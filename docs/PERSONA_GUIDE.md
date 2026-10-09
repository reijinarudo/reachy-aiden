# Writing your robot's persona

The persona file is `/home/pollen/profiles/<ROBOT_NAME>/instructions.txt`. The voice model reads it at the start of every session. It is the main thing that makes your robot sound like a specific character, and also the main thing that decides when it speaks.

These lessons came from months of testing with a real robot in a real house, with family, guests, students, and other devices talking nearby.

## 1. Tell the robot what to do

Voice models follow instructions stated as actions. A rule written as a list of forbidden phrases tends to produce those exact phrases, because quoting them puts the words in front of the model. A rule that describes silence or calm makes the model talk about being silent or calm.

| Gets worse results | Gets better results |
| --- | --- |
| Never say "I'm staying quiet." | When the turn is not mine, my output is empty. |
| Be calm and do not interrupt. | I respond only when I hear my name. |

## 2. Make the name the trigger

The template's "When I Speak" section is the most important part of the file. The robot responds when its name is in the utterance or when it is in the middle of a back-and-forth, and stays silent otherwise. Without it, the robot answers the television, the phone call in the next room, and its own echo.

If your robot keeps jumping in, make this section more literal before you change anything else. Raise the silence time in the config as a second step.

## 3. Keep the closing anchor

The last section restates who the robot is and what its name means. The beginning and end of a long prompt carry the most weight with the model. As your memory and persona grow, the anchor keeps the robot from drifting, from addressing you by its own name, or from answering when its name is only mentioned.

## 4. Keep the persona lean

Everything in this file is sent to the voice provider at the start of every session. Long files cost more, load slower, and dilute the rules that matter. Put long facts in places the robot looks up on demand:

- Things it should remember: `companion-add-memory`
- How it works: `architecture-details.txt` in the same folder, read by the `get_architecture` tool

## 5. Write in the first person

"I am Aiden. I respond when..." works better than "You are Aiden. You should respond when...". The robot speaks as itself, and the memories are written the same way.

## 6. Privacy

Assume anyone in the room can hear anything the robot knows. The template includes an optional pass phrase: the robot treats every speaker as a guest until it hears the phrase, and shares personal details only after that. Pick a phrase that speech-to-text transcribes consistently. Words from another language work well. List the misspellings you see in the conversation log, because the transcriber will produce them.

## 7. Change one thing at a time

When a behavior is wrong, change one rule, save, test, and read the conversation log before changing the next. Several edits at once, especially late at night, have broken working personas more often than any bug.

## 8. Check what you changed

Saving the file restarts the app within a few seconds. Watch the result:

```bash
tail -f /home/pollen/conversation-logs/conversation-$(date +%Y-%m-%d).jsonl
```
