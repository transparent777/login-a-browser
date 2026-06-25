"""
车联网 TSP 平台 — 主服务
- MQTT 订阅接收 TBOX 上报数据
- Flask REST API 提供车辆管理、远程控制、轨迹查询、告警管理、运营统计
"""

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


# ===================== 启动入口 =====================

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
