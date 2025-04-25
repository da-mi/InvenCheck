from RPLCD.i2c import CharLCD
from time import sleep

# LCD configuration
lcd = CharLCD(
    i2c_expander='PCF8574',
    address=0x27,
    port=1,
    cols=20,
    rows=4,
    charmap='A02',
    auto_linebreaks=True
)

lcd.clear()
block = chr(255)

# Custom characters (5x8 matrices)
D_outer_top = [
    0b10000, 
    0b11000, 
    0b11100, 
    0b11100,
    0b11110, 
    0b11110, 
    0b11110, 
    0b11111
]
D_inner_top = [
    0b11111, 
    0b01111,
    0b00111, 
    0b00011,
    0b00011, 
    0b00011, 
    0b00011, 
    0b00011
]
D_outer_bot = D_outer_top[::-1]
D_inner_bot = D_inner_top[::-1]

K_lo_top = [
    0b00001, 
    0b00011, 
    0b00011, 
    0b00111,
    0b00111, 
    0b01111, 
    0b01111, 
    0b11111
]
K_hi_top = [
    0b11111, 
    0b11110, 
    0b11110, 
    0b11100,
    0b11100, 
    0b11000, 
    0b11000, 
    0b10000
]
K_lo_bot = K_lo_top[::-1]
K_hi_bot = K_hi_top[::-1]

# Register custom characters
lcd.create_char(0, D_outer_top)
lcd.create_char(1, D_inner_top)
lcd.create_char(2, D_outer_bot)
lcd.create_char(3, D_inner_bot)
lcd.create_char(4, K_lo_top)
lcd.create_char(5, K_hi_top)
lcd.create_char(6, K_lo_bot)
lcd.create_char(7, K_hi_bot)

# Draw 'T'
for row in range(4):
    if row == 0:
        lcd.cursor_pos = (row, 0)
        lcd.write_string(block * 6)
    else:
        lcd.cursor_pos = (row, 2)
        lcd.write_string(block * 2)

# Draw 'D'
for row in range(4):
    lcd.cursor_pos = (row, 7)
    lcd.write_string(block * 2)
    if row in [1, 2]:
        lcd.cursor_pos = (row, 11)
        lcd.write_string(block)
    if row in [0, 3]:
        lcd.cursor_pos = (row, 8)
        lcd.write_string(block * 3)
    if row == 0:
        lcd.cursor_pos = (row, 11)
        lcd.write_string(chr(0))
    elif row == 1:
        lcd.cursor_pos = (row, 10)
        lcd.write_string(chr(1))
    elif row == 2:
        lcd.cursor_pos = (row, 10)
        lcd.write_string(chr(3))
    elif row == 3:
        lcd.cursor_pos = (row, 11)
        lcd.write_string(chr(2))

# Draw 'K'
for row in range(4):
    lcd.cursor_pos = (row, 14)
    lcd.write_string(block * 2)
    if row == 0:
        lcd.cursor_pos = (row, 17)
        lcd.write_string(chr(4))
        lcd.cursor_pos = (row, 18)
        lcd.write_string(block)
        lcd.cursor_pos = (row, 19)
        lcd.write_string(chr(5))
    elif row == 1:
        lcd.cursor_pos = (row, 16)
        lcd.write_string(chr(4))
        lcd.cursor_pos = (row, 17)
        lcd.write_string(block)
        lcd.cursor_pos = (row, 18)
        lcd.write_string(chr(5))
    elif row == 2:
        lcd.cursor_pos = (row, 16)
        lcd.write_string(chr(6))
        lcd.cursor_pos = (row, 17)
        lcd.write_string(block)
        lcd.cursor_pos = (row, 18)
        lcd.write_string(chr(7))
    elif row == 3:
        lcd.cursor_pos = (row, 17)
        lcd.write_string(chr(6))
        lcd.cursor_pos = (row, 18)
        lcd.write_string(block)
        lcd.cursor_pos = (row, 19)
        lcd.write_string(chr(7))