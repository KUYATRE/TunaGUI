"""
이거 일단 UAExpert로 NodeId 다 긁어온 다음에 작업해야할듯...개빡쎄네
"""
from opcua import Client

from ui_tuning import TuningPage
from algo_logAnalyser import get_file, detect_heater_zones

def setup_connection():
    # OPC UA 서버 URL (Omron PLC의 IP 주소 사용)
    plc_url = "opc.tcp://172.22.80.1:4840"

    # 변수 이름 (OPC UA 노드 ID 형식으로)
    node_id = "ns=2;s=RTI1[3]"  # TEST : 변수의 정확한 노드 ID 확인 필요

    # 클라이언트 연결 및 변수 읽기
    client = Client(plc_url)

    try:
        client.connect()
        print("OPC UA 연결 성공")

        # 노드 가져오기
        node = client.get_node(node_id)
        objects = client.get_objects_node()
        all_nodes = objects.get_children(recursive=True)

        # 값 읽기
        value = node.get_value()
        print(f"RTI1[3] 값: {value}")

    except Exception as e:
        print("오류 발생:", e)

    finally:
        client.disconnect()
        print("연결 종료")
        if objects and all_nodes:
            return objects, all_nodes
        else:
            return None, None

def explore_node(node, target_name):
    obj = TuningPage()
    file_path = obj.load_csv()
    print(f"file path: {file_path}")

    objects, all_nodes = setup_connection()

    if file_path:
        rows = get_file(file_path)
        zone_count = detect_heater_zones(rows[0])
        for zone in zone_count:
            for node in all_nodes:
                try:
                    name = node.get_browse_name().Name
                    if "Temperature" in name:
                        print(f"✔ Node Found: {name}")
                        print(f"  NodeId: {node.nodeid}")
                except:
                    continue