from RPLCD.i2c import CharLCD
from time import sleep

# Adjust address and columns/rows if needed
lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1,
              cols=20, rows=4, charmap='A00', auto_linebreaks=True)

# Clear the screen
lcd.clear()

# Write test lines
lcd.write_string("LCD 2004 Test OK")
lcd.cursor_pos = (1, 0)
lcd.write_string("Line 2 here!")
lcd.cursor_pos = (2, 0)
lcd.write_string("Line 3 ready.")
lcd.cursor_pos = (3, 0)
lcd.write_string("Waiting...")

# Loop animation
try:
    while True:
        lcd.cursor_pos = (3, 12)
        for i in range(3):
            lcd.write_string("." * (i+1))
            sleep(0.5)
            lcd.cursor_pos = (3, 12)
            lcd.write_string("   ")
except KeyboardInterrupt:
    lcd.clear()
    print("Exited.")
