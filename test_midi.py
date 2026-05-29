import mido
import time

# Identify the bridged ALSA-JACK port
ports = mido.get_output_names()
target_port = next((p for p in ports if 'system' in p.lower() or 'playback' in p.lower()), None)

if not target_port:
    print(f"Available ports: {ports}")
    print("Could not auto-detect JACK bridge port. Using fallback.")
    target_port = ports[0] if ports else None

if target_port:
    print(f"Injecting MIDI into: {target_port}")
    with mido.open_output(target_port) as port:
        # Max out Volume (CC 7) and Cutoff (CC 74)
        port.send(mido.Message('control_change', channel=0, control=7, value=127))
        port.send(mido.Message('control_change', channel=0, control=74, value=127))
        print("CC states injected.")
        
        # Fire a sustained C2 note
        port.send(mido.Message('note_on', channel=0, note=36, velocity=100))
        print("Note ON. Holding for 2 seconds...")
        time.sleep(2)
        
        port.send(mido.Message('note_off', channel=0, note=36, velocity=0))
        print("Note OFF.")
else:
    print("No MIDI output ports found. Ensure jackd is running with '-X seq'.")
