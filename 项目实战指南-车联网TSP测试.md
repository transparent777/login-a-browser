# 车联网 TSP 平台测试 — 实战项目指南

> 目标：一天内搭建一个迷你的 TSP 平台 + 模拟 TBOX，写出测试用例和自动化脚本
> 技术栈：Python + Flask + Mosquitto + SQLite + Postman + JMeter（可选）
> 效果：面试时可以说"我自己搭建过一个 TSP 测试环境"

---

## 项目整体架构

```
┌──────────────────┐
│  TBOX 模拟器      │ ──Python 脚本, 定时发送车辆数据
│  (tbox_sim.py)   │   通过 MQTT 发布到 Broker
└────────┬─────────┘
         │ MQTT (Topic: /vehicle/{VIN}/data)
         ▼
┌──────────────────┐
│  MQTT Broker     │ ──Mosquitto (开源, 免费)
│  (mosquitto)     │
└────────┬─────────┘
         │ 订阅
         ▼
┌──────────────────┐     ┌──────────────────┐
│  TSP 平台         │ ←→ │  SQLite 数据库     │
│  (tsp_server.py) │     │  (tsp.db)         │
│  Flask 框架       │     │                   │
│                   │     │  - vehicle_info   │
│  - 数据接收接口    │     │  - vehicle_status │
│  - 远程控制接口    │     │  - alert_record   │
│  - 告警规则判断    │     │  - trajectory     │
│  - 轨迹查询接口    │     │  - control_cmd    │
│  - 车辆管理 API   │     │  - ota_task      │
└────────┬─────────┘     └──────────────────┘
         │ HTTP REST API
         ▼
┌──────────────────┐
│  测试客户端        │
│                   │
│  - Postman 集合   │
│  - 自动化测试脚本  │
│  (test_api.py)   │
└──────────────────┘
```

---

## 第一步：环境准备（30 分钟）

### 1.1 安装 Python 依赖
```bash
pip install flask paho-mqtt requests pytest sqlite3
```

### 1.2 安装 Mosquitto（MQTT Broker）
- **Windows**：下载 https://mosquitto.org/download/ → 安装 → 服务自动启动
- **Mac**：`brew install mosquitto`
- **Linux**：`sudo apt install mosquitto mosquitto-clients`

验证安装：
```bash
# 开一个终端，订阅测试 Topic
mosquitto_sub -h localhost -t "/vehicle/test/data" -v

# 开另一个终端，发布测试消息
mosquitto_pub -h localhost -t "/vehicle/test/data" -m '{"test": "hello"}'
```

---

## 第二步：搭建 TSP 平台核心代码（1 小时）

### 2.1 数据库初始化 — `db_init.py`

```python
import sqlite3

def init_db():
    conn = sqlite3.connect('tsp.db')
    cursor = conn.cursor()

    # 车辆信息表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicle_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vin TEXT UNIQUE NOT NULL,          -- 车辆识别码
            plate_number TEXT,                 -- 车牌号
            brand TEXT,                        -- 品牌
            model TEXT,                        -- 型号
            owner_name TEXT,                   -- 车主
            owner_phone TEXT,                  -- 车主电话
            tbox_sn TEXT,                      -- TBOX 序列号
            iccid TEXT,                        -- SIM 卡号
            register_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'offline'      -- online / offline / driving / charging
        )
    ''')

    # 车辆实时状态表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicle_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vin TEXT NOT NULL,
            soc REAL,                          -- 电池电量百分比
            speed REAL,                        -- 车速 km/h
            odometer REAL,                     -- 总里程 km
            longitude REAL,                    -- 经度
            latitude REAL,                     -- 纬度
            heading REAL,                      -- 方向角
            battery_voltage REAL,              -- 电池电压
            battery_temp REAL,                 -- 电池温度
            motor_speed REAL,                  -- 电机转速
            gear TEXT,                         -- 档位 P/R/N/D
            status TEXT,                       -- driving / parking / charging
            report_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vin) REFERENCES vehicle_info(vin)
        )
    ''')

    # 轨迹数据表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trajectory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vin TEXT NOT NULL,
            trip_id TEXT,                      -- 行程 ID
            longitude REAL,
            latitude REAL,
            speed REAL,
            heading REAL,
            altitude REAL,
            accuracy REAL,                     -- GPS 精度
            gps_time DATETIME,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 告警记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alert_record (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vin TEXT NOT NULL,
            alert_type TEXT NOT NULL,          -- overspeed / fence / low_battery / high_temp / fatigue
            alert_level TEXT DEFAULT 'warning', -- warning / critical / emergency
            alert_content TEXT,
            is_resolved INTEGER DEFAULT 0,     -- 0 未解除 1 已解除
            resolved_time DATETIME,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 远程控制指令表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS control_cmd (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vin TEXT NOT NULL,
            cmd_type TEXT NOT NULL,            -- unlock / lock / ac_on / ac_off / flash_light / window
            cmd_params TEXT,                   -- JSON 格式的指令参数
            cmd_status TEXT DEFAULT 'pending', -- pending / sent / success / failed / timeout
            result_msg TEXT,
            send_time DATETIME,
            execute_time DATETIME,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # OTA 升级任务表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ota_task (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_name TEXT NOT NULL,
            firmware_version TEXT NOT NULL,
            target_version TEXT NOT NULL,
            firmware_url TEXT,
            firmware_md5 TEXT,                 -- 校验用
            target_vehicle_count INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            fail_count INTEGER DEFAULT 0,
            task_status TEXT DEFAULT 'created', -- created / pushing / finished
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 插入测试车辆数据
    test_vehicles = [
        ('LSVAU2A38N2100001', '沪A12345', '比亚迪', '汉EV', '张三', '13800001111', 'TBOX001', '89860112345678900001'),
        ('LSVAU2A38N2100002', '京B67890', '特斯拉', 'Model 3', '李四', '13800002222', 'TBOX002', '89860112345678900002'),
        ('LSVAU2A38N2100003', '粤C11111', '蔚来', 'ET5', '王五', '13800003333', 'TBOX003', '89860112345678900003'),
    ]

    for v in test_vehicles:
        try:
            cursor.execute('''
                INSERT INTO vehicle_info (vin, plate_number, brand, model, owner_name, owner_phone, tbox_sn, iccid, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'offline')
            ''', v)
        except sqlite3.IntegrityError:
            pass  # 已存在则跳过

    conn.commit()
    conn.close()
    print("数据库初始化完成！")

if __name__ == '__main__':
    init_db()
```

### 2.2 TSP 平台服务端 — `tsp_server.py`

```python
from flask import Flask, request, jsonify
import sqlite3
import json
import datetime
import threading
import paho.mqtt.client as mqtt

app = Flask(__name__)

# ===================== MQTT 订阅（接收 TBOX 上报数据） =====================

def on_connect(client, userdata, flags, rc):
    print(f"MQTT 已连接, 返回码: {rc}")
    # 订阅所有车辆的数据上报 Topic（用通配符 + 匹配 VIN）
    client.subscribe("/vehicle/+/data")
    print("已订阅: /vehicle/+/data")

def on_message(client, userdata, msg):
    """收到 TBOX 上报的数据"""
    try:
        payload = json.loads(msg.payload.decode())
        vin = msg.topic.split('/')[2]  # 从 Topic 中提取 VIN
        print(f"[MQTT 接收] VIN={vin}, 数据={payload}")

        conn = sqlite3.connect('tsp.db')
        cursor = conn.cursor()

        # 1. 更新车辆状态
        cursor.execute('''
            INSERT INTO vehicle_status
                (vin, soc, speed, odometer, longitude, latitude, heading,
                 battery_voltage, battery_temp, motor_speed, gear, status, report_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            vin,
            payload.get('soc'),
            payload.get('speed'),
            payload.get('odometer'),
            payload.get('longitude'),
            payload.get('latitude'),
            payload.get('heading'),
            payload.get('battery_voltage'),
            payload.get('battery_temp'),
            payload.get('motor_speed'),
            payload.get('gear', 'P'),
            payload.get('status', 'parking'),
            datetime.datetime.now()
        ))

        # 2. 更新车辆在线状态
        cursor.execute('UPDATE vehicle_info SET status = ? WHERE vin = ?',
                       (payload.get('status', 'online'), vin))

        # 3. 写入轨迹表
        if payload.get('longitude') and payload.get('latitude'):
            cursor.execute('''
                INSERT INTO trajectory
                    (vin, trip_id, longitude, latitude, speed, heading, gps_time)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                vin,
                payload.get('trip_id', ''),
                payload.get('longitude'),
                payload.get('latitude'),
                payload.get('speed'),
                payload.get('heading'),
                datetime.datetime.now()
            ))

        # 4. 告警规则判断
        check_alerts(cursor, vin, payload)

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"[MQTT 处理异常] {e}")

def check_alerts(cursor, vin, data):
    """内置告警规则"""
    # 超速告警（> 120 km/h）
    speed = data.get('speed', 0) or 0
    if speed > 120:
        cursor.execute('''
            INSERT INTO alert_record (vin, alert_type, alert_level, alert_content)
            VALUES (?, 'overspeed', 'critical', ?)
        ''', (vin, f"车速 {speed}km/h 超过阈值 120km/h"))

    # 低电量告警（SOC < 20%）
    soc = data.get('soc', 100) or 100
    if soc < 20:
        cursor.execute('''
            INSERT INTO alert_record (vin, alert_type, alert_level, alert_content)
            VALUES (?, 'low_battery', 'warning', ?)
        ''', (vin, f"电量 {soc}% 低于阈值 20%"))

    # 电池高温告警（> 60°C）
    batt_temp = data.get('battery_temp', 25) or 25
    if batt_temp > 60:
        cursor.execute('''
            INSERT INTO alert_record (vin, alert_type, alert_level, alert_content)
            VALUES (?, 'high_temp', 'critical', ?)
        ''', (vin, f"电池温度 {batt_temp}°C 超过阈值 60°C"))

# 启动 MQTT 客户端（在后台线程）
def start_mqtt():
    mqtt_client = mqtt.Client(client_id="tsp-server")
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect("localhost", 1883, 60)
    mqtt_client.loop_forever()

# ===================== REST API =====================

# --- 车辆管理 ---

@app.route('/api/vehicles', methods=['GET'])
def get_vehicles():
    """查询车辆列表"""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)
    status = request.args.get('status', '')

    conn = sqlite3.connect('tsp.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    sql = 'SELECT * FROM vehicle_info WHERE 1=1'
    params = []
    if status:
        sql += ' AND status = ?'
        params.append(status)

    sql += ' LIMIT ? OFFSET ?'
    params.extend([page_size, (page - 1) * page_size])

    cursor.execute(sql, params)
    vehicles = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'code': 200, 'data': vehicles, 'total': len(vehicles)})


@app.route('/api/vehicles/<vin>', methods=['GET'])
def get_vehicle_detail(vin):
    """查询车辆详情 + 最新状态"""
    conn = sqlite3.connect('tsp.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM vehicle_info WHERE vin = ?', (vin,))
    vehicle = cursor.fetchone()
    if not vehicle:
        conn.close()
        return jsonify({'code': 404, 'message': '车辆不存在'}), 404

    cursor.execute('''
        SELECT * FROM vehicle_status
        WHERE vin = ? ORDER BY report_time DESC LIMIT 1
    ''', (vin,))
    latest_status = cursor.fetchone()

    conn.close()

    result = dict(vehicle)
    result['latest_status'] = dict(latest_status) if latest_status else None
    return jsonify({'code': 200, 'data': result})


@app.route('/api/vehicles', methods=['POST'])
def register_vehicle():
    """注册车辆"""
    data = request.json
    conn = sqlite3.connect('tsp.db')
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO vehicle_info (vin, plate_number, brand, model, owner_name, owner_phone, tbox_sn, iccid, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'offline')
        ''', (
            data['vin'], data.get('plate_number', ''), data.get('brand', ''),
            data.get('model', ''), data.get('owner_name', ''),
            data.get('owner_phone', ''), data.get('tbox_sn', ''),
            data.get('iccid', '')
        ))
        conn.commit()
        conn.close()
        return jsonify({'code': 201, 'message': '车辆注册成功'})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'code': 400, 'message': 'VIN 已被注册'}), 400

# --- 远程控制 ---

@app.route('/api/control/<vin>', methods=['POST'])
def send_control_cmd(vin):
    """向车辆下发远程控制指令"""
    data = request.json
    cmd_type = data.get('cmdType')
    cmd_params = data.get('params', {})

    allowed_cmds = ['unlock', 'lock', 'ac_on', 'ac_off', 'flash_light', 'horn', 'window_open', 'window_close']
    if cmd_type not in allowed_cmds:
        return jsonify({'code': 400, 'message': f'不支持的指令类型: {cmd_type}'}), 400

    # 检查车辆是否在线
    conn = sqlite3.connect('tsp.db')
    cursor = conn.cursor()
    cursor.execute('SELECT status FROM vehicle_info WHERE vin = ?', (vin,))
    vehicle = cursor.fetchone()

    if not vehicle:
        conn.close()
        return jsonify({'code': 404, 'message': '车辆不存在'}), 404

    if vehicle[0] == 'offline':
        conn.close()
        return jsonify({'code': 400, 'message': '车辆离线，无法执行远程控制'}), 400

    # 记录指令
    now = datetime.datetime.now()
    cursor.execute('''
        INSERT INTO control_cmd (vin, cmd_type, cmd_params, cmd_status, send_time)
        VALUES (?, ?, ?, 'sent', ?)
    ''', (vin, cmd_type, json.dumps(cmd_params), now))

    cmd_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # 通过 MQTT 下发指令到 TBOX
    mqtt_sender = mqtt.Client(client_id="tsp-control-sender")
    mqtt_sender.connect("localhost", 1883, 60)
    cmd_msg = json.dumps({
        'cmdId': cmd_id,
        'cmdType': cmd_type,
        'params': cmd_params,
        'timestamp': now.isoformat()
    })
    mqtt_sender.publish(f"/vehicle/{vin}/control", cmd_msg, qos=1)
    mqtt_sender.disconnect()

    return jsonify({'code': 200, 'message': '指令已下发', 'data': {'cmdId': cmd_id}})


@app.route('/api/control/<vin>/history', methods=['GET'])
def get_control_history(vin):
    """查询车辆远程控制历史"""
    conn = sqlite3.connect('tsp.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM control_cmd
        WHERE vin = ? ORDER BY create_time DESC LIMIT 50
    ''', (vin,))
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify({'code': 200, 'data': records})

# --- 轨迹查询 ---

@app.route('/api/trajectory/<vin>', methods=['GET'])
def get_trajectory(vin):
    """查询车辆轨迹（按时间范围）"""
    start_time = request.args.get('startTime')
    end_time = request.args.get('endTime')

    conn = sqlite3.connect('tsp.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    sql = 'SELECT * FROM trajectory WHERE vin = ?'
    params = [vin]

    if start_time:
        sql += ' AND gps_time >= ?'
        params.append(start_time)
    if end_time:
        sql += ' AND gps_time <= ?'
        params.append(end_time)

    sql += ' ORDER BY gps_time ASC LIMIT 2000'

    cursor.execute(sql, params)
    points = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({
        'code': 200,
        'data': {
            'vin': vin,
            'pointCount': len(points),
            'points': points
        }
    })

# --- 告警查询 ---

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """查询告警列表"""
    vin = request.args.get('vin', '')
    alert_type = request.args.get('alertType', '')
    is_resolved = request.args.get('isResolved', '')
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)

    conn = sqlite3.connect('tsp.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    sql = 'SELECT * FROM alert_record WHERE 1=1'
    params = []

    if vin:
        sql += ' AND vin = ?'
        params.append(vin)
    if alert_type:
        sql += ' AND alert_type = ?'
        params.append(alert_type)
    if is_resolved != '':
        sql += ' AND is_resolved = ?'
        params.append(int(is_resolved))

    sql += ' ORDER BY create_time DESC LIMIT ? OFFSET ?'
    params.extend([page_size, (page - 1) * page_size])

    cursor.execute(sql, params)
    alerts = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({'code': 200, 'data': alerts, 'total': len(alerts)})


@app.route('/api/alerts/<int:alert_id>/resolve', methods=['PUT'])
def resolve_alert(alert_id):
    """手动解除告警"""
    conn = sqlite3.connect('tsp.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE alert_record SET is_resolved = 1, resolved_time = ?
        WHERE id = ?
    ''', (datetime.datetime.now(), alert_id))
    conn.commit()
    conn.close()
    return jsonify({'code': 200, 'message': '告警已解除'})

# --- 运营统计 ---

@app.route('/api/statistics/dashboard', methods=['GET'])
def get_dashboard():
    """运营看板数据"""
    conn = sqlite3.connect('tsp.db')
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM vehicle_info')
    total_vehicles = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM vehicle_info WHERE status != 'offline'")
    online_vehicles = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM alert_record WHERE is_resolved = 0")
    active_alerts = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM trajectory WHERE create_time > datetime("now", "-1 day")')
    today_trajectory_points = cursor.fetchone()[0]

    conn.close()

    return jsonify({'code': 200, 'data': {
        'totalVehicles': total_vehicles,
        'onlineVehicles': online_vehicles,
        'onlineRate': f'{online_vehicles / total_vehicles * 100:.1f}%' if total_vehicles > 0 else '0%',
        'activeAlerts': active_alerts,
        'todayTrajectoryPoints': today_trajectory_points
    }})


if __name__ == '__main__':
    # 初始化数据库
    import db_init
    db_init.init_db()

    # 启动 MQTT 监听线程
    mqtt_thread = threading.Thread(target=start_mqtt, daemon=True)
    mqtt_thread.start()
    print("MQTT 监听已启动")

    # 启动 Flask API 服务
    print("TSP 平台 API 启动: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
```

---

## 第三步：编写 TBOX 模拟器（30 分钟）

### 3.1 `tbox_sim.py` — 模拟一辆车的 TBOX

```python
import paho.mqtt.client as mqtt
import json
import time
import random
import datetime

# ===== 配置 =====
VIN = "LSVAU2A38N2100001"  # 改成你要模拟的车辆 VIN
BROKER = "localhost"
PORT = 1883
TOPIC_DATA = f"/vehicle/{VIN}/data"
TOPIC_CONTROL = f"/vehicle/{VIN}/control"

# 模拟上海陆家嘴的坐标
BASE_LONGITUDE = 121.4989
BASE_LATITUDE = 31.2415

# ===== MQTT 回调 =====

def on_connect(client, userdata, flags, rc):
    print(f"[TBOX {VIN}] 已连接到 MQTT Broker (rc={rc})")
    # 订阅远程控制指令 Topic
    client.subscribe(TOPIC_CONTROL)
    print(f"[TBOX {VIN}] 已订阅: {TOPIC_CONTROL}")

def on_message(client, userdata, msg):
    """收到远程控制指令"""
    cmd = json.loads(msg.payload.decode())
    print(f"[TBOX {VIN}] 收到远程控制指令: {cmd}")

    # 模拟执行指令
    def execute_cmd():
        time.sleep(2)  # 模拟执行延迟
        result_msg = json.dumps({
            'cmdId': cmd['cmdId'],
            'cmdType': cmd['cmdType'],
            'result': 'success',
            'message': f"指令 {cmd['cmdType']} 执行成功",
            'timestamp': datetime.datetime.now().isoformat()
        })
        client.publish(f"/vehicle/{VIN}/control_result", result_msg, qos=1)
        print(f"[TBOX {VIN}] 指令执行结果已反馈: {result_msg}")

    import threading
    threading.Thread(target=execute_cmd, daemon=True).start()

# ===== 模拟车辆数据生成 =====

def generate_vehicle_data():
    """生成模拟的车辆数据"""
    soc = max(10, min(100, 85 + random.uniform(-0.5, 0.5)))  # 电池电量缓慢变化
    speed = random.randint(0, 130)
    odometer = 32500 + random.uniform(0, 0.1)

    # 模拟位置移动（朝着一个方向）
    global BASE_LONGITUDE, BASE_LATITUDE
    BASE_LONGITUDE += random.uniform(-0.002, 0.002)
    BASE_LATITUDE += random.uniform(-0.002, 0.002)

    return {
        'soc': round(soc, 1),
        'speed': speed,
        'odometer': round(odometer, 2),
        'longitude': round(BASE_LONGITUDE, 6),
        'latitude': round(BASE_LATITUDE, 6),
        'heading': random.randint(0, 360),
        'altitude': round(random.uniform(0, 100), 1),
        'battery_voltage': round(380 + random.uniform(-5, 5), 1),
        'battery_temp': round(25 + random.uniform(-3, 8), 1),
        'motor_speed': random.randint(0, 8000),
        'gear': random.choice(['D', 'P', 'R', 'N']),
        'status': 'driving' if speed > 5 else 'parking',
        'trip_id': f"trip_{int(time.time())}"
    }

# ===== 主程序 =====

def main():
    client = mqtt.Client(client_id=f"tbox-{VIN}")
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER, PORT, 60)

    # 设置遗嘱消息（TBOX 断连时通知平台）
    will_msg = json.dumps({'vin': VIN, 'status': 'offline', 'reason': 'connection_lost'})
    client.will_set(f"/vehicle/{VIN}/status", will_msg, qos=1, retain=True)

    client.loop_start()  # 启动后台网络循环

    print(f"[TBOX {VIN}] 开始上报数据...")
    try:
        while True:
            data = generate_vehicle_data()
            client.publish(TOPIC_DATA, json.dumps(data, ensure_ascii=False), qos=1)
            print(f"[TBOX {VIN}] 上报数据: SOC={data['soc']}%, 速度={data['speed']}km/h, "
                  f"位置=({data['longitude']}, {data['latitude']})")
            time.sleep(5)  # 每 5 秒上报一次（模拟 30 秒会更真实）
    except KeyboardInterrupt:
        print(f"[TBOX {VIN}] 停止上报")
        client.loop_stop()
        client.disconnect()

if __name__ == '__main__':
    main()
```

---

## 第四步：编写自动化测试脚本（30 分钟）

### 4.1 `test_api.py` — API 自动化测试

```python
import requests
import pytest
import json
import sqlite3

BASE_URL = "http://localhost:5000"

# ======================== 测试 Fixture ========================

@pytest.fixture(scope='module')
def test_vin():
    return "LSVAU2A38N2100001"

# ======================== 车辆管理测试 ========================

class TestVehicleManagement:

    def test_get_vehicle_list(self):
        """测试查询车辆列表"""
        resp = requests.get(f"{BASE_URL}/api/vehicles")
        assert resp.status_code == 200
        data = resp.json()
        assert data['code'] == 200
        assert len(data['data']) > 0
        print(f"  ✓ 车辆列表查询成功, 共 {len(data['data'])} 辆车")

    def test_get_vehicle_detail(self, test_vin):
        """测试查询车辆详情"""
        resp = requests.get(f"{BASE_URL}/api/vehicles/{test_vin}")
        assert resp.status_code == 200
        data = resp.json()
        assert data['data']['vin'] == test_vin
        assert 'latest_status' in data['data']
        print(f"  ✓ 车辆详情查询成功: {data['data']['plate_number']}")

    @pytest.mark.parametrize("status", ['online', 'offline', 'driving', 'charging'])
    def test_filter_vehicles_by_status(self, status):
        """测试按状态筛选车辆"""
        resp = requests.get(f"{BASE_URL}/api/vehicles?status={status}")
        assert resp.status_code == 200
        data = resp.json()
        for vehicle in data['data']:
            assert vehicle['status'] == status
        print(f"  ✓ 状态筛选 '{status}' 通过")

    def test_register_duplicate_vin(self):
        """测试重复 VIN 注册（异常场景）"""
        payload = {
            "vin": "LSVAU2A38N2100001",  # 已存在的 VIN
            "plate_number": "测试车",
            "brand": "测试品牌"
        }
        resp = requests.post(f"{BASE_URL}/api/vehicles", json=payload)
        assert resp.status_code == 400
        assert resp.json()['code'] == 400
        print("  ✓ 重复 VIN 注册被正确拦截")

    def test_get_nonexistent_vehicle(self):
        """测试查询不存在的车辆（异常场景）"""
        resp = requests.get(f"{BASE_URL}/api/vehicles/INVALID_VIN_99999")
        assert resp.status_code == 404
        print("  ✓ 不存在的车辆返回 404")

# ======================== 远程控制测试 ========================

class TestRemoteControl:

    def test_control_cmd_send(self, test_vin):
        """测试下发远程控制指令"""
        payload = {"cmdType": "flash_light", "params": {"duration": 5}}
        resp = requests.post(f"{BASE_URL}/api/control/{test_vin}", json=payload)
        assert resp.status_code == 200
        assert resp.json()['data']['cmdId'] is not None
        print(f"  ✓ 远程控制指令下发成功, cmdId={resp.json()['data']['cmdId']}")

    def test_invalid_cmd_type(self, test_vin):
        """测试非法的指令类型（异常场景）"""
        payload = {"cmdType": "fly_to_moon"}  # 不存在的指令
        resp = requests.post(f"{BASE_URL}/api/control/{test_vin}", json=payload)
        assert resp.status_code == 400
        print("  ✓ 非法指令类型被正确拦截")

    def test_control_history(self, test_vin):
        """测试查询控制指令历史"""
        resp = requests.get(f"{BASE_URL}/api/control/{test_vin}/history")
        assert resp.status_code == 200
        print(f"  ✓ 控制指令历史查询成功, 共 {len(resp.json()['data'])} 条")

# ======================== 告警测试 ========================

class TestAlert:

    def test_get_alerts(self):
        """测试查询告警列表"""
        resp = requests.get(f"{BASE_URL}/api/alerts")
        assert resp.status_code == 200
        print(f"  ✓ 告警列表查询成功, 共 {len(resp.json()['data'])} 条")

    def test_filter_alerts_by_type(self):
        """测试按类型筛选告警"""
        for alert_type in ['overspeed', 'low_battery', 'high_temp']:
            resp = requests.get(f"{BASE_URL}/api/alerts?alertType={alert_type}")
            assert resp.status_code == 200
            for alert in resp.json()['data']:
                assert alert['alert_type'] == alert_type
        print("  ✓ 告警类型筛选通过")

    def test_resolve_alert(self):
        """测试手动解除告警"""
        # 先查一个未解除的告警
        resp = requests.get(f"{BASE_URL}/api/alerts?isResolved=0&pageSize=1")
        if resp.json()['data']:
            alert_id = resp.json()['data'][0]['id']
            resp2 = requests.put(f"{BASE_URL}/api/alerts/{alert_id}/resolve")
            assert resp2.status_code == 200
            print(f"  ✓ 告警 {alert_id} 解除成功")

# ======================== 轨迹测试 ========================

class TestTrajectory:

    def test_get_trajectory(self, test_vin):
        """测试查询轨迹"""
        resp = requests.get(f"{BASE_URL}/api/trajectory/{test_vin}")
        assert resp.status_code == 200
        data = resp.json()
        assert 'points' in data['data']
        print(f"  ✓ 轨迹查询成功, 共 {data['data']['pointCount']} 个点")

    def test_trajectory_with_time_range(self, test_vin):
        """测试按时间范围查询轨迹"""
        import datetime
        end = datetime.datetime.now().isoformat()
        start = (datetime.datetime.now() - datetime.timedelta(hours=1)).isoformat()

        resp = requests.get(
            f"{BASE_URL}/api/trajectory/{test_vin}",
            params={'startTime': start, 'endTime': end}
        )
        assert resp.status_code == 200
        print("  ✓ 按时间范围查询轨迹通过")

# ======================== 数据一致性测试 ========================

class TestDataConsistency:

    def test_vehicle_status_in_db(self, test_vin):
        """测试数据库中的车辆状态与 API 返回一致"""
        # API 获取
        api_resp = requests.get(f"{BASE_URL}/api/vehicles/{test_vin}")
        api_status = api_resp.json()['data']['status']

        # 数据库直接查
        conn = sqlite3.connect('tsp.db')
        cursor = conn.cursor()
        cursor.execute('SELECT status FROM vehicle_info WHERE vin = ?', (test_vin,))
        db_status = cursor.fetchone()[0]
        conn.close()

        assert api_status == db_status, f"API状态({api_status}) ≠ 数据库状态({db_status})"
        print(f"  ✓ 数据一致性验证通过: {api_status}")

    def test_control_cmd_recorded(self, test_vin):
        """测试远程控制指令是否正确入库"""
        # 下发一条指令
        payload = {"cmdType": "horn", "params": {}}
        resp = requests.post(f"{BASE_URL}/api/control/{test_vin}", json=payload)
        cmd_id = resp.json()['data']['cmdId']

        # 验证数据库中是否有记录
        conn = sqlite3.connect('tsp.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM control_cmd WHERE id = ?', (cmd_id,))
        record = cursor.fetchone()
        conn.close()

        assert record is not None
        assert record[2] == 'horn'  # cmd_type
        print(f"  ✓ 控制指令入库验证通过: cmdId={cmd_id}")

# ======================== 运行测试 ========================

if __name__ == '__main__':
    print("=" * 60)
    print("TSP 平台自动化测试开始")
    print("=" * 60)
    pytest.main([__file__, '-v', '-s'])
```

---

## 第五步：启动和联调（30 分钟）

### 启动顺序

```bash
# 终端 1：启动 TSP 平台
python tsp_server.py
# 输出：
# MQTT 已连接, 返回码: 0
# 已订阅: /vehicle/+/data
# TSP 平台 API 启动: http://localhost:5000

# 终端 2：启动 TBOX 模拟器
python tbox_sim.py
# 输出：
# [TBOX LSVAU2A38N2100001] 已连接到 MQTT Broker
# [TBOX LSVAU2A38N2100001] 开始上报数据...
# [TBOX LSVAU2A38N2100001] 上报数据: SOC=85.1%, 速度=68km/h, 位置=(121.5012, 31.2430)

# 终端 3：运行自动化测试
python test_api.py -v
```

### 用 Postman 手动测试

1. **GET** `http://localhost:5000/api/vehicles` — 查车辆列表
2. **GET** `http://localhost:5000/api/vehicles/LSVAU2A38N2100001` — 查车辆详情
3. **POST** `http://localhost:5000/api/control/LSVAU2A38N2100001`
   - Body: `{"cmdType": "flash_light", "params": {"duration": 5}}`
4. **GET** `http://localhost:5000/api/trajectory/LSVAU2A38N2100001` — 查轨迹
5. **GET** `http://localhost:5000/api/alerts` — 查告警
6. **GET** `http://localhost:5000/api/statistics/dashboard` — 运营看板

### 手动验证数据库

```bash
# 用 SQLite 命令行连接到数据库
sqlite3 tsp.db

# 查看表结构
.tables

# 查车辆状态
SELECT vin, soc, speed, report_time FROM vehicle_status ORDER BY report_time DESC LIMIT 10;

# 查告警历史
SELECT vin, alert_type, alert_content, create_time FROM alert_record;

# 查远程控制指令
SELECT vin, cmd_type, cmd_status, send_time FROM control_cmd;

# 查轨迹点数
SELECT vin, COUNT(*) as cnt FROM trajectory GROUP BY vin;

# 退出
.quit
```

---

## 第六步：进阶操作（加分项，有时间就做）

### 6.1 用 Charles 抓包

```
1. 打开 Charles
2. 设置 Proxy → Proxy Settings → HTTP Proxy Port: 8888
3. Python 请求加代理：
   proxies = {'http': 'http://localhost:8888', 'https': 'http://localhost:8888'}
   resp = requests.get('http://localhost:5000/api/vehicles', proxies=proxies)
4. 在 Charles 中查看请求/响应内容
```

### 6.2 编写 Postman Collection

Postman Collection 结构（面试时可以给面试官看）：

```
📁 TSP 平台测试集合
  📁 车辆管理
    ├── GET 查询车辆列表
    ├── GET 查询车辆详情
    ├── POST 注册车辆
    └── POST 批量导入车辆
  📁 远程控制
    ├── POST 远程解锁
    ├── POST 远程开空调
    ├── POST 闪灯鸣笛
    └── GET 查询控制历史
  📁 告警管理
    ├── GET 查询告警列表
    ├── GET 按类型筛选告警
    └── PUT 解除告警
  📁 轨迹回放
    ├── GET 查询轨迹
    └── GET 按时间范围查询轨迹
  📁 运营统计
    └── GET 运营看板数据
```

### 6.3 用 JMeter 做简单压测

```
1. 创建线程组：模拟 100 个并发用户
2. 添加 HTTP Request：GET /api/vehicles
3. 添加监听器：View Results Tree、Summary Report
4. 运行 → 看 TPS 和响应时间
```

### 6.4 扩展：模拟多辆车同时上报

```python
# multi_tbox.py — 同时启动 10 台模拟车
import threading
import tbox_sim

VINS = [
    'LSVAU2A38N2100001',
    'LSVAU2A38N2100002',
    'LSVAU2A38N2100003',
]

threads = []
for vin in VINS:
    t = threading.Thread(target=tbox_sim.run_with_vin, args=(vin,), daemon=True)
    t.start()
    threads.append(t)

for t in threads:
    t.join()
```

---

## 面试时你怎么描述这个项目

> **"我在面试前搭建了一个迷你的车联网 TSP 测试环境"**

然后展开说：

### 架构（边说边画）
> 我用 **Flask** 写了 TSP 平台的 API 服务，包括车辆管理、远程控制、告警判断、轨迹查询、运营统计等模块。用 **Mosquitto** 搭建了 MQTT Broker，编写了 Python 脚本来**模拟 TBOX** 终端，每 5 秒上报一次车辆数据到平台，同时能接收平台下发的远程控制指令。

### 测试做了什么
> 我编写了完整的**自动化测试脚本**，使用 pytest，覆盖了以下场景：
> - **功能测试**：每个 API 的正常流程验证
> - **异常测试**：重复注册、非法指令类型、查询不存在的车辆等
> - **数据一致性验证**：对比 API 返回数据和数据库存储数据是否一致
> - **边界值测试**：如告警阈值的边界验证（119 不触发、120 触发）
> - **端到端测试**：从 TBOX 上报 → 平台接收 → 数据库存储 → API 返回 → 数据核对

### 告警规则
> 我在平台中内置了 3 条告警规则：超速告警（> 120km/h）、低电量告警（SOC < 20%）、电池高温告警（> 60°C），每当 TBOX 上报的数据触发规则时，平台自动生成告警记录。

### 数据库
> 我设计了 6 张核心数据表：车辆信息表、实时状态表、轨迹数据表、告警记录表、控制指令表、OTA 任务表。用 SQLite 存储，能直接写 SQL 核对数据。

---

## 文件清单

完成后的项目文件结构：

```
tsp-test-project/
├── db_init.py          # 数据库初始化
├── tsp_server.py       # TSP 平台主服务
├── tbox_sim.py         # TBOX 模拟器
├── multi_tbox.py       # 多车并发模拟
├── test_api.py         # 自动化测试脚本
├── tsp.db              # SQLite 数据库（运行后自动生成）
├── TSP.postman_collection.json  # Postman 集合（手动导出）
└── README.md           # 项目说明
```

---

## 时间分配建议

| 时间段 | 任务 | 产出 |
|--------|------|------|
| 前 30 分钟 | 装环境、启动 Mosquitto | 环境就绪 |
| 30-90 分钟 | 写 db_init.py + tsp_server.py | 平台跑起来 |
| 90-120 分钟 | 写 tbox_sim.py、联调 | TBOX 能上报数据 |
| 120-150 分钟 | 写 test_api.py、运行测试 | 有测试结果 |
| 150-180 分钟 | Postman 手动验证、数据库查数 | 完整可演示 |
| 剩余时间 | 背面试文档、演练自我介绍 | 面试自信 |

---

> **面试核心目标**：让面试官觉得 "这个同学不只是背了理论，他真的动手做过车联网相关的测试" — 你就赢了。
