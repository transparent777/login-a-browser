"""
车联网 TSP 平台 — TBOX 模拟器
模拟车载终端：定时上报车辆数据 + 接收远程控制指令
"""

import paho.mqtt.client as mqtt
import json
import time
import random
import datetime
import threading

# ===== 默认配置 =====
DEFAULT_VIN = "LSVAU2A38N2100001"
BROKER = "localhost"
PORT = 1883

# 模拟上海陆家嘴的坐标
BASE_LONGITUDE = 121.4989
BASE_LATITUDE = 31.2415


def generate_vehicle_data(base_lon, base_lat):
    """生成模拟的车辆数据"""
    soc = max(10, min(100, 85 + random.uniform(-0.5, 0.5)))  # 电池电量缓慢变化
    speed = random.randint(0, 130)
    odometer = 32500 + random.uniform(0, 0.1)

    # 模拟位置移动（朝着一个方向微调）
    base_lon += random.uniform(-0.002, 0.002)
    base_lat += random.uniform(-0.002, 0.002)

    return {
        'soc': round(soc, 1),
        'speed': speed,
        'odometer': round(odometer, 2),
        'longitude': round(base_lon, 6),
        'latitude': round(base_lat, 6),
        'heading': random.randint(0, 360),
        'altitude': round(random.uniform(0, 100), 1),
        'battery_voltage': round(380 + random.uniform(-5, 5), 1),
        'battery_temp': round(25 + random.uniform(-3, 8), 1),
        'motor_speed': random.randint(0, 8000),
        'gear': random.choice(['D', 'P', 'R', 'N']),
        'status': 'driving' if speed > 5 else 'parking',
        'trip_id': f"trip_{int(time.time())}"
    }, base_lon, base_lat


def run_with_vin(vin):
    """以指定 VIN 运行 TBOX 模拟器"""
    topic_data = f"/vehicle/{vin}/data"
    topic_control = f"/vehicle/{vin}/control"

    base_lon = BASE_LONGITUDE + random.uniform(-0.01, 0.01)
    base_lat = BASE_LATITUDE + random.uniform(-0.01, 0.01)

    def on_connect(client, userdata, flags, rc):
        print(f"[TBOX {vin}] 已连接到 MQTT Broker (rc={rc})")
        client.subscribe(topic_control)
        print(f"[TBOX {vin}] 已订阅: {topic_control}")

    def on_message(client, userdata, msg):
        """收到远程控制指令"""
        cmd = json.loads(msg.payload.decode())
        print(f"[TBOX {vin}] 收到远程控制指令: {cmd}")

        def execute_cmd():
            time.sleep(2)  # 模拟执行延迟
            result_msg = json.dumps({
                'cmdId': cmd['cmdId'],
                'cmdType': cmd['cmdType'],
                'result': 'success',
                'message': f"指令 {cmd['cmdType']} 执行成功",
                'timestamp': datetime.datetime.now().isoformat()
            })
            client.publish(f"/vehicle/{vin}/control_result", result_msg, qos=1)
            print(f"[TBOX {vin}] 指令执行结果已反馈: {result_msg}")

        threading.Thread(target=execute_cmd, daemon=True).start()

    client = mqtt.Client(client_id=f"tbox-{vin}")
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER, PORT, 60)

    # 设置遗嘱消息（TBOX 断连时通知平台）
    will_msg = json.dumps({'vin': vin, 'status': 'offline', 'reason': 'connection_lost'})
    client.will_set(f"/vehicle/{vin}/status", will_msg, qos=1, retain=True)

    client.loop_start()

    print(f"[TBOX {vin}] 开始上报数据...")
    try:
        while True:
            data, base_lon, base_lat = generate_vehicle_data(base_lon, base_lat)
            client.publish(topic_data, json.dumps(data, ensure_ascii=False), qos=1)
            print(f"[TBOX {vin}] 上报数据: SOC={data['soc']}%, 速度={data['speed']}km/h, "
                  f"位置=({data['longitude']}, {data['latitude']})")
            time.sleep(5)  # 每 5 秒上报一次
    except KeyboardInterrupt:
        print(f"[TBOX {vin}] 停止上报")
        client.loop_stop()
        client.disconnect()


def main():
    print(f"TBOX 模拟器启动, VIN={DEFAULT_VIN}")
    print(f"MQTT Broker: {BROKER}:{PORT}")
    print("-" * 50)
    run_with_vin(DEFAULT_VIN)


if __name__ == '__main__':
    main()
