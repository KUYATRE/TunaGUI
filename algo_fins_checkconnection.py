from PySide6.QtCore import QRunnable

class CheckConnectionWorker(QRunnable):
    def __init__(self, fins_client, prev_bit, callback, mem_area, word_addr, bit_offset):
        super().__init__()
        self.fins = fins_client
        self.prev_bit = prev_bit
        self.callback = callback
        self.mem_area = mem_area
        self.word_addr = word_addr
        self.bit_offset = bit_offset

    def run(self):
        try:
            bit_val = self.fins.read_word_bit(
                mem_area=self.mem_area,
                word_addr=self.word_addr,
                bit_offset=self.bit_offset
            )
            if bit_val is None:
                raise Exception("응답 없음")

            is_changed = (self.prev_bit is None) or (bit_val != self.prev_bit)
            self.callback(bit_val, is_changed, None)

        except Exception as e:
            self.callback(None, False, e)
