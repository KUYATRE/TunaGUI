from opcua import Client

# OPC UA 서버 URL (Omron PLC의 IP 주소 사용)
PLC_URL = "opc.tcp://172.22.80.1:4840"

# 변수 이름 (OPC UA 노드 ID 형식으로)
NODE_ID = "ns=2;s=RTI1[3]"  # 변수의 정확한 노드 ID 확인 필요

# 클라이언트 연결 및 변수 읽기
client = Client(PLC_URL)

try:
    client.connect()
    print("OPC UA 연결 성공")

    # 노드 가져오기
    node = client.get_node(NODE_ID)

    # 값 읽기
    value = node.get_value()
    print(f"RTI1[3] 값: {value}")

except Exception as e:
    print("오류 발생:", e)

finally:
    client.disconnect()
    print("연결 종료")
