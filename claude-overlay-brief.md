# Project: Floating Claude Chat Bubble (Arch Linux)

## What I want

A small desktop app that acts like a floating chat bubble:

1. When I launch the app, a small round icon appears on my screen, sitting on top of other windows.
2. It's semi-transparent (about half see-through) when just sitting there.
3. When I hover my mouse over it, it gets a bit darker/more solid so I know it's clickable.
4. When I click it, a small chat window pops up near the bubble.
5. Inside that chat window there's a button to expand it to full screen, and a button/way to shrink it back down.
6. The chat itself talks to Claude using the Anthropic API — I type a message, it sends it, and shows the reply.

This is a personal tool just for me, running locally on my machine.

## Before writing code

Please ask me the following before you start building, instead of guessing:

1. **What desktop environment/window manager am I using?** (e.g. GNOME, KDE, Hyprland, i3, etc.) and whether I'm on X11 or Wayland. This changes how "always on top, floating window" needs to be built. If I don't know, give me a one-line terminal command to check and I'll paste the result back.
2. **Do I already have an Anthropic API key**, and how would I like to store it (a password manager tool built into Linux vs. a simple local config file)? Explain the trade-off in one or two sentences, don't just pick for me.
3. Confirm the **screen position** I want for the bubble (corner of the screen? follows mouse? fixed spot?) — default to bottom-right corner if I don't care.
4. Ask if I want the chat history to **persist between sessions** (saved to a file) or reset every time I close it.

## Technical direction (so you don't have to guess)

- Use **Python with PySide6** for the app itself — it handles transparent/floating windows well and makes calling the Claude API simple.
- Use the official **`anthropic` Python package** for talking to Claude.
- Keep the code organized in a few clear files rather than one giant file (e.g. one file for the bubble window, one for the chat window, one for the Claude API calls).
- Don't use Electron or a web-based framework — keep it lightweight.

## How to approach it

Please work in small steps, and check in with me after each one before moving to the next:

**Step 1:** Ask me the clarifying questions above first.
**Step 2:** Set up the basic project (folder structure, dependencies, a way to run it) and get a plain floating bubble showing on screen with no functionality yet — just to confirm the "always on top and transparent" part works on my system before building anything else on top of it.
**Step 3:** Add the hover-darkens effect.
**Step 4:** Add the click-to-open chat window (empty, no API yet).
**Step 5:** Add the full-screen/shrink toggle for the chat window.
**Step 6:** Wire up the Claude API so messages actually send and get replies.
**Step 7:** Add a simple way to launch the app normally (so I'm not typing a Python command every time).

At each step, tell me in plain language what you built and how to test it before continuing.

## Keep in mind

- I'm on Arch Linux.
- I don't need this to be fancy or production-grade — just clean, easy to read, and easy for me to modify later.
- If something about my system (window manager, display server) makes a feature difficult or impossible, tell me plainly and suggest the closest workable alternative rather than silently building a workaround I won't understand.
