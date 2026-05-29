# [INSERT_CODE_BLOCK_1]
#!/bin/bash

# Clear existing processes
killall jackd jalv a2jmidid python3 tmux 2>/dev/null

# 1. Audio Server
JACK_NO_AUDIO_RESERVATION=1 jackd -d alsa -d hw:0 -r 44100 -p 256 -n 2 -X seq &
sleep 3

# 2. ALSA to JACK MIDI Bridge
a2jmidid -e &
sleep 2

# 3. jalv (in detached tmux session)
tmux new-session -d -s jalv '~/jalv-1.6.8/build/jalv http://github.com/midilab/JC303'
sleep 2

# 4. Patch Bay (audio only — MIDI is wired by engine.py after channel filtering)
jack_connect JC303:audio_out_1 system:playback_1
jack_connect JC303:audio_out_2 system:playback_2

echo "Audio architecture initialized. Ready for TUI execution."

# 5. PotatoSynth Middleware & TUI
cd /home/potato/ || exit

# Start engine in the background and write stdout/stderr to a log file
python3 engine.py > /dev/shm/engine.log 2>&1 &
sleep 1

# Start TUI in the foreground
exec python3 tui.py