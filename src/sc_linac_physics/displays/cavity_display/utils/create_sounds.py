import os

import numpy as np
from scipy.io import wavfile


def create_beep(filename, frequency, duration, sample_rate=44100):
    """Create a simple beep sound"""
    t = np.linspace(0, duration, int(sample_rate * duration))

    # Generate sine wave
    wave = np.sin(2 * np.pi * frequency * t)

    # Apply envelope to avoid clicks
    envelope = np.ones_like(wave)
    fade_samples = int(0.01 * sample_rate)  # 10ms fade
    envelope[:fade_samples] = np.linspace(0, 1, fade_samples)
    envelope[-fade_samples:] = np.linspace(1, 0, fade_samples)

    wave = wave * envelope

    # Convert to 16-bit PCM
    wave = (wave * 32767).astype(np.int16)

    # Save
    wavfile.write(filename, sample_rate, wave)


# Create sounds directory
os.makedirs("../frontend/sounds", exist_ok=True)

# Create different sounds
create_beep(
    "../frontend/sounds/alarm.wav", frequency=800, duration=0.5
)  # Lower pitch, longer
create_beep(
    "../frontend/sounds/warning.wav", frequency=600, duration=0.3
)  # Even lower, shorter
create_beep(
    "../frontend/sounds/urgent.wav", frequency=1000, duration=0.3
)  # Higher pitch

print("Sound files created in sounds/ directory")
