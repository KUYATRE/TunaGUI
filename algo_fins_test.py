import omronfins.finsudp as finsudp
from omronfins.finsudp import datadef
from PySide6.QtCore import QRunnable

class CheckConnectionWorker(QRunnable):
    def __init__(self, fins, prev_bit, callback):
        super().__init__()
        self.fins = fins
        self.prev_bit = prev_bit
        self.callback = callback

    def run(self):
        try:
            word_value = self.fins.read_mem_area(datadef.DM_WORD, 100, 0, 1, datadef.USHORT)
            bit_val = (word_value[0] >> 0) & 0x01
            status = (bit_val != self.prev_bit)
            self.callback(bit_val, status, None)
        except Exception as e:
            self.callback(None, False, e)


# try:
#     fins = finsudp.FinsUDP(0, 11)  # PC 노드 번호 11
#     fins.open('172.22.80.1', 9600)
#     fins.set_destination(dst_net_addr=0, dst_node_num=10, dst_unit_addr=0)
#
#     ret, word_value = fins.read_mem_area(datadef.DM_WORD, 100, 0, 1, datadef.USHORT)
#
#     if word_value:
#         value = word_value[0]  # 튜플에서 실제 워드 값 추출
#         bit_5 = (value >> 5) & 0x01
#         print(f"D100.05 = {bit_5}")
#     else:
#         print("D100 읽기 실패 또는 응답 없음")
#
# except Exception as e:
#     print(f"[FINS 오류] {e}")