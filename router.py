import mido  # type: ignore
import yaml  # type: ignore
import sys
import subprocess

TMUX_SESSION = 'jalv'

def load_config():
    try:
        with open('mapping.yaml', 'r') as file:
            return yaml.safe_load(file)
    except Exception as e:
        print(f"Error loading YAML: {e}")
        sys.exit(1)

def find_port(keyword):
    for port in mido.get_input_names():
        if keyword.lower() in port.lower():
            return port
    return None

def send_to_jalv(cmd):
    subprocess.run(
        ['tmux', 'send-keys', '-t', f'{TMUX_SESSION}:0', cmd, 'Enter'],
        check=True
    )

def main():
    config = load_config()
    in_port_name = find_port(config['tracker_input_port'])

    if not in_port_name:
        print(f"Input port '{config['tracker_input_port']}' not found.")
        sys.exit(1)

    # Verify tmux session exists
    result = subprocess.run(
        ['tmux', 'has-session', '-t', TMUX_SESSION],
        capture_output=True
    )
    if result.returncode != 0:
        print(f"No tmux session named '{TMUX_SESSION}' found.")
        print(f"Start jalv with: tmux new-session -d -s {TMUX_SESSION} '~/jalv-1.6.8/build/jalv http://github.com/midilab/JC303'")
        sys.exit(1)

    cc_map = config.get('cc_map', {})

    print(f"Listening on MIDI port: {in_port_name}")
    print(f"Sending to tmux session: {TMUX_SESSION}")
    print("Routing CC to jalv. Ctrl+C to stop.\n")

    try:
        with mido.open_input(in_port_name) as in_port:
            for msg in in_port:
                if msg.type == 'control_change':
                    if msg.control in cc_map:
                        param = cc_map[msg.control]
                        val = msg.value / 127.0
                        cmd = f"{param} = {val:.3f}"
                        send_to_jalv(cmd)
                        print(f"CC{msg.control} -> {cmd}")
    except KeyboardInterrupt:
        print("\nRouter stopped.")

if __name__ == '__main__':
    main()
