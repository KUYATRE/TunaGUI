import socket

class FinsUDPClient:
    def __init__(self, plc_ip, plc_port=9600, plc_node=1, pc_node=179):
        self.plc_ip = plc_ip
        self.plc_port = plc_port
        self.plc_node = plc_node
        self.pc_node = pc_node
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(2)

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None
            print("소켓 연결 종료")

    def build_fins_header(self):
        return bytearray([
            128, 0, 2, 0,
            self.plc_node, 0,
            0, self.pc_node, 0,
            0
        ])

    def build_read_command(self, mem_area, word_addr, bit_offset, word_count=1):
        addr_hi = (word_addr >> 8) & 255
        addr_lo = word_addr & 255
        return bytearray([
            1, 1,
            mem_area,
            addr_hi, addr_lo, bit_offset,
            (word_count >> 8) & 255, word_count & 255
        ])

    def build_write_command(self, mem_area, word_addr, bit_offset, word_value):
        addr_hi = (word_addr >> 8) & 255
        addr_lo = word_addr & 255
        data_hi = (word_value >> 8) & 255
        data_lo = word_value & 255

        return bytearray([
            1, 2,
            mem_area,
            addr_hi, addr_lo, bit_offset,
            0, 1,
            data_hi, data_lo
        ])

    def send_command(self, command):
        fins_frame = self.build_fins_header() + command
        try:
            self.sock.sendto(fins_frame, (self.plc_ip, self.plc_port))
            data, _ = self.sock.recvfrom(1024)
            return data
        except socket.timeout:
            return None

    def read_word(self, word_addr, mem_area):
        cmd = self.build_read_command(mem_area, word_addr, 0, 1)
        response = self.send_command(cmd)
        if response is None or response[12:14] != b'\x00\x00':
            return None
        return int.from_bytes(response[-2:], byteorder='big')

    def read_word_bit(self, mem_area, word_addr, bit_offset):
        cmd = self.build_read_command(mem_area, word_addr, bit_offset)
        response = self.send_command(cmd)
        if response is None:
            print("응답 없음 timeout")
            return None
        if response[12:14] != b'\x00\x00':
            print("읽기 실패", response[12:].hex())
            return None

        value = int.from_bytes(response[-2:], byteorder='big')
        bit = (value >> bit_offset) & 1
        print("Read", mem_area, word_addr, bit_offset, "=", bit)
        return bit

    def write_word_bit(self, mem_area, word_addr, bit_offset, turn_on=True):
        current_value = self.read_word(word_addr, mem_area)
        if current_value is None:
            print("현재 값을 읽을 수 없습니다.")
            return False

        if turn_on:
            new_value = current_value | (1 << bit_offset)
        else:
            new_value = current_value & ~(1 << bit_offset)

        cmd = self.build_write_command(mem_area, word_addr, 0, new_value)
        response = self.send_command(cmd)
        if response is None:
            print("응답 없음 timeout")
            return False
        if response[12:] != b'\x00\x00':
            print("쓰기 실패", response[12:].hex())
            return False
        print("Write", mem_area, word_addr, bit_offset, "=", turn_on)
        return True

    def write_bit(self, mem_area, word_addr, bit_offset, turn_on=True):
        addr_hi = (word_addr >> 8) & 0xff
        addr_lo = word_addr & 0xff
        bit_no = bit_offset & 0xff
        bit_val = 0x01 if turn_on else 0x00

        cmd = bytearray([
            0x01, 0x02,
            mem_area,
            addr_hi, addr_lo, bit_no,
            0x00, 0x01,
            bit_val
        ])

        response = self.send_command(cmd)
        if response is None:
            print("응답 없음 (timeout)")
            return False
        if response[12:14] != b'\x00\x00':
            print("비트 쓰기 실패", response[12:].hex())
            return False

        print(f"Bit Write: {mem_area:#X}_{word_addr}.{bit_offset:02} = {'ON' if turn_on else 'OFF'}")
        return True



# ===================TEST CODE===================
if __name__ == "__main__":
    client = FinsUDPClient("172.22.80.1")

    client.read_word_bit(mem_area=0xA0, word_addr=0, bit_offset=0)

    client.write_word_bit(mem_area=161, word_addr=1, bit_offset=2, turn_on=True)

    client.write_word_bit(mem_area=0xA0, word_addr=16800, bit_offset=1, turn_on=False)