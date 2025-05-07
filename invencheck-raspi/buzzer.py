"""
Buzzer class definition
Passive buzzer connected to a Raspberry Pi

Damiano Milani
2025
"""

import RPi.GPIO as GPIO
import time

class Buzzer:
    NOTES = {
        # Octave 0–7 (standard)
        'B0': 31, 'C1': 33, 'CS1': 35, 'D1': 37, 'DS1': 39, 'E1': 41, 'F1': 44, 'FS1': 46, 'G1': 49, 'GS1': 52,
        'A1': 55, 'AS1': 58, 'B1': 62, 'C2': 65, 'CS2': 69, 'D2': 73, 'DS2': 78, 'E2': 82, 'F2': 87, 'FS2': 93,
        'G2': 98, 'GS2': 104, 'A2': 110, 'AS2': 117, 'B2': 123, 'C3': 131, 'CS3': 139, 'D3': 147, 'DS3': 156,
        'E3': 165, 'F3': 175, 'FS3': 185, 'G3': 196, 'GS3': 208, 'A3': 220, 'AS3': 233, 'B3': 247, 'C4': 262,
        'CS4': 277, 'D4': 294, 'DS4': 311, 'E4': 330, 'F4': 349, 'FS4': 370, 'G4': 392, 'GS4': 415, 'A4': 440,
        'AS4': 466, 'B4': 494, 'C5': 523, 'CS5': 554, 'D5': 587, 'DS5': 622, 'E5': 659, 'F5': 698, 'FS5': 740,
        'G5': 784, 'GS5': 831, 'A5': 880, 'AS5': 932, 'B5': 988, 'C6': 1047, 'CS6': 1109, 'D6': 1175, 'DS6': 1245,
        'E6': 1319, 'F6': 1397, 'FS6': 1480, 'G6': 1568, 'GS6': 1661, 'A6': 1760, 'AS6': 1865, 'B6': 1976,
        'C7': 2093, 'CS7': 2217, 'D7': 2349, 'DS7': 2489, 'E7': 2637, 'F7': 2794, 'FS7': 2960, 'G7': 3136,
        'GS7': 3322, 'A7': 3520, 'AS7': 3729, 'B7': 3951, 'C8': 4186, 'D8': 4434, 'E8': 4698, 'F8': 4978, 
        'G8': 5274, 'A8': 5587, 'B8': 5919, 'C9': 6000,
        'REST': 0
    }


    def __init__(self, pin, default_freq=2000):
        self.pin = pin
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.OUT)
        self.pwm = GPIO.PWM(self.pin, default_freq)

    def beep(self, frequency=None, duration=0.1):
        if frequency and frequency > 0:
            self.pwm.ChangeFrequency(frequency)
            self.pwm.start(20)
        time.sleep(duration)
        self.pwm.stop()

    def note(self, name, duration=0.1):
        freq = self.NOTES.get(name.upper(), 0)
        self.beep(freq, duration)

    def play_song(self, song, tempo=1.0, pause=0.05):
        for note, duration in song:
            actual_duration = duration * tempo
            if note.upper() == 'REST':
                time.sleep(actual_duration)
            else:
                freq = self.NOTES.get(note.upper(), 440)  # fallback to A4
                self.note(note, actual_duration)
            time.sleep(pause * tempo)


    # Preset tones
    def read(self):
        self.beep(3000, 0.05)

    def online(self):
        for tone in [(2094,0.05), (2638,0.05), (3136,0.05)]:
            self.beep(tone[0],tone[1])
            time.sleep(0.05)

    def checkin(self):
        for tone in [(3000,0.05), (3000,0.05), (3000,0.1)]:
            self.beep(tone[0],tone[1])
            time.sleep(0.05)
        
    def checkout(self):
        for tone in [(2000,0.1), (1500,0.1), (880,0.1)]:
            self.beep(tone[0],tone[1])
            time.sleep(0.05)

    def error(self):
        for tone in [(150,0.2), (150,0.2), (150,0.2)]:
            self.beep(tone[0],tone[1])
            time.sleep(0.05)


    def sweep_test(self):
        print("Sweeping from C4 to 6kHz...")
        for note in self.NOTES:
            print(f"Playing {note} ({Buzzer.NOTES[note]} Hz)")
            self.note(note, 0.1)
            time.sleep(0.001)


if __name__ == "__main__":
    buzzer = Buzzer(pin=24)

    sw = [
        ('A3', 0.5), ('A3', 0.5), ('A3', 0.5),
        ('F3', 0.35), ('C4', 0.15), ('A3', 0.5),
        ('F3', 0.35), ('C4', 0.15), ('A3', 0.8),

        ('E4', 0.5), ('E4', 0.5), ('E4', 0.5),
        ('F4', 0.35), ('C4', 0.15), ('GS3', 0.5),
        ('F3', 0.35), ('C4', 0.15), ('A3', 0.8),
    ]

    buzzer.play_song(sw, tempo=1.0)
