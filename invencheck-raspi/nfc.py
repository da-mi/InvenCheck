import board
import busio
from digitalio import DigitalInOut
from adafruit_pn532.spi import PN532_SPI

class NFCReader:
    def __init__(self):
        spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
        cs_pin = DigitalInOut(board.D8)  # CE0
        self.pn532 = PN532_SPI(spi, cs_pin, debug=False)
        self.pn532.SAM_configuration()
        print("PN532 ready")

    def read_uid(self, timeout=1.0):
        while True:
            uid = self.pn532.read_passive_target(timeout=timeout)
            if uid:
                return ''.join('{:02X}'.format(x) for x in uid)
            