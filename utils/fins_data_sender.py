from services.fins_comm import FinsUDPClient

def fins_connect():
    fins = FinsUDPClient(plc_ip='172.22.80.1')
    return fins

def data_send(mem_area, word_addr, word_value):
    fins = fins_connect()
    fins.write_word(mem_area=mem_area, word_addr=word_addr, word_value=word_value)
    return None



