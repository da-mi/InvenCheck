import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
import time

# --- Setup GPIO ---
BUZZER_PIN = 24
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUZZER_PIN, GPIO.OUT)

# Setup PWM at ~2kHz (tweakable)
buzzer_pwm = GPIO.PWM(BUZZER_PIN, 8000)  # 2kHz is a good starting tone

reader = SimpleMFRC522()

def beep(duration=0.1, frequency=2000):
    buzzer_pwm.ChangeFrequency(frequency)
    buzzer_pwm.start(90)
    time.sleep(duration)
    buzzer_pwm.stop()


try:
    print("InvenCheck NFC Reader - Waiting for tag...")
    beep(0.05, 1047*2)
    time.sleep(0.05)
    beep(0.05, 1319*2)
    time.sleep(0.05)
    beep(0.05, 1568*2)
    

    id, text = reader.read()
    print(f"\nTag detected:\nID: {id}\nText: {text}")

    # beep(0.05, 1568*2)
    # time.sleep(0.05)
    # beep(0.05, 1568*2)
    # time.sleep(0.05)
    # beep(0.1, 1568*2)

    beep(0.1, 2000)
    time.sleep(0.05)
    beep(0.2, 1000)
    # time.sleep(0.05)
    # beep(0.2, 150)
    # time.sleep(0.05)
    # beep(0.2, 150)
    

finally:
    GPIO.cleanup()

