"""
车联网 TSP 平台 — 数据库初始化脚本
创建 6 张核心表 + 插入测试车辆数据
"""

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
