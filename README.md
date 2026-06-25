# 🚗 车联网 TSP 平台测试项目

> 一个完整的车联网 TSP（Telematics Service Platform）测试环境，包含模拟 TBOX、MQTT 通信、Flask API 服务和 pytest 自动化测试。

[![Python](https://img.shields.io/badge/Python-3.6+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-0.12+-green.svg)](https://flask.palletsprojects.com/)
[![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-orange.svg)](https://mosquitto.org/)
[![Test](https://img.shields.io/badge/test-18%20passed-brightgreen.svg)](./test_api.py)

---

## 📋 目录

- [项目架构](#项目架构)
- [快速开始](#快速开始)
- [逐步演示教程](#逐步演示教程)
  - [第一步：环境检查](#第一步环境检查)
  - [第二步：初始化数据库](#第二步初始化数据库)
  - [第三步：启动 TSP 平台](#第三步启动-tsp-平台)
  - [第四步：启动 TBOX 模拟器](#第四步启动-tbox-模拟器)
  - [第五步：手动验证 API](#第五步手动验证-api)
  - [第六步：验证 MQTT 数据上报](#第六步验证-mqtt-数据上报)
  - [第七步：验证告警规则](#第七步验证告警规则)
  - [第八步：运行自动化测试](#第八步运行自动化测试)
- [API 接口文档](#api-接口文档)
- [数据库设计](#数据库设计)
- [测试用例说明](#测试用例说明)
- [文件结构](#文件结构)
- [面试演示话术](#面试演示话术)

---

## 项目架构

```
┌──────────────────┐
│  TBOX 模拟器      │ ──Python 脚本, 定时发送车辆数据
│  (tbox_sim.py)   │   通过 MQTT 发布到 Broker
└────────┬─────────┘
         │ MQTT (QoS 1)
         │ Topic: /vehicle/{VIN}/data      ← 数据上报
         │ Topic: /vehicle/{VIN}/control   → 远程指令
         ▼
┌──────────────────┐
│  MQTT Broker     │ ──Mosquitto 2.1.2
│  localhost:1883  │   发布/订阅模式
└────────┬─────────┘
         │ 订阅
         ▼
┌──────────────────┐     ┌──────────────────┐
│  TSP 平台         │ ←→ │  SQLite 数据库     │
│  (tsp_server.py) │     │  (tsp.db)         │
│  Flask :5000      │     │                   │
│                   │     │  - vehicle_info   │
│  - 数据接收       │     │  - vehicle_status │
│  - 远程控制       │     │  - alert_record   │
│  - 告警判断       │     │  - trajectory     │
│  - 轨迹查询       │     │  - control_cmd    │
│  - 运营统计       │     │  - ota_task       │
└────────┬─────────┘     └──────────────────┘
         │ HTTP REST API
         ▼
┌──────────────────┐
│  测试客户端        │
│  - Postman 手动测试│
│  - pytest 自动化   │
│  (test_api.py)    │
└──────────────────┘
```

**数据流向：** `TBOX → MQTT Broker → TSP 平台 → SQLite → REST API → 客户端`

---

## 快速开始

### 环境要求

| 组件 | 版本 | 作用 |
|------|------|------|
| Python | 3.6+ | 运行平台和测试脚本 |
| Mosquitto | 2.0+ | MQTT 消息中间件 |
| paho-mqtt | 1.6+ | Python MQTT 客户端库 |
| Flask | 0.12+ | Web API 框架 |
| pytest | 3.2+ | 自动化测试框架 |

### 一键启动

```bash
# 1. 安装 Python 依赖
pip install flask paho-mqtt requests pytest

# 2. 安装 Mosquitto（Windows 从 mosquitto.org 下载安装包）
#    安装后服务自动启动在 localhost:1883

# 3. 初始化数据库
python db_init.py

# 4. 启动 TSP 平台（终端 1）
python tsp_server.py

# 5. 启动 TBOX 模拟器（终端 2）
python tbox_sim.py

# 6. 运行自动化测试（终端 3）
python -m pytest test_api.py -v
```

---

## 逐步演示教程

> 💡 **演示目标**：让面试官看到你理解了车联网数据从车端到云端的完整链路，并且会写自动化测试。

---

### 第一步：环境检查

**做什么：** 确认所有依赖都已安装

```bash
# 检查 Python 版本
python --version
# 输出: Python 3.6.3

# 检查已安装的包
pip list | grep -E "flask|paho-mqtt|pytest|requests"
# 输出:
# Flask              0.12.2
# paho-mqtt          1.6.1
# pytest             3.2.1
# requests           2.18.4

# 检查 Mosquitto 是否运行
netstat -an | findstr "1883"
# 输出: TCP  127.0.0.1:1883  ...  LISTENING
```

**为什么：** 面试时展示你对环境的掌控力——知道每个组件干什么用。

**关键概念：**
- **1883** 是 MQTT 协议默认端口（记住这个数字，面试常问）
- Mosquitto 是 **Broker（消息中间件）**，不存数据，只负责转发
- TSP 平台才是业务核心——收数据、存数据、提供查询接口

---

### 第二步：初始化数据库

**做什么：** 创建 6 张业务表 + 插入测试车辆

```bash
python db_init.py
# 输出: 数据库初始化完成！
```

**做了什么？** 打开 `db_init.py` 看：

```python
# 1️⃣ 车辆信息表 (vehicle_info)
#    存储车辆档案：VIN、车牌、品牌、车主信息
#    面试说："这是车辆主数据表"

# 2️⃣ 车辆实时状态表 (vehicle_status)
#    存储每次上报的实时数据：SOC、速度、GPS、电池温度
#    面试说："这是时序数据，每辆车每5秒一条，所以数据量最大"

# 3️⃣ 轨迹数据表 (trajectory)
#    存储 GPS 轨迹点，用于轨迹回放
#    面试说："一般按行程 trip_id 分组，用于回放行驶路线"

# 4️⃣ 告警记录表 (alert_record)
#    存储告警事件：超速、低电量、高温
#    面试说："告警有生命周期：产生 → 解除，状态流转要能追溯"

# 5️⃣ 远程控制指令表 (control_cmd)
#    存储远程控制历史：解锁、开空调、闪灯
#    面试说："远程控制是异步的，下发→执行→反馈，要能追踪状态"

# 6️⃣ OTA 升级任务表 (ota_task)
#    存储固件升级任务（预留，本 Demo 未实现完整逻辑）
```

**验证数据库：**

```bash
# 用 SQLite 命令行查看
sqlite3 tsp.db

# 查看所有表
.tables
# 输出: alert_record  control_cmd  ota_task  trajectory  vehicle_info  vehicle_status

# 查看车辆数据
SELECT vin, plate_number, brand, model FROM vehicle_info;
# 输出 3 辆测试车

# 退出
.quit
```

**为什么：** 面试时可能让你现场写 SQL 核对数据，熟悉表结构很重要。

---

### 第三步：启动 TSP 平台

**做什么：** 启动 Flask API 服务 + MQTT 监听

```bash
python tsp_server.py
```

**启动时发生了什么？** 代码里的启动顺序：

```python
if __name__ == '__main__':
    # ① 先初始化数据库（如果表不存在就创建）
    import db_init
    db_init.init_db()

    # ② 在后台线程启动 MQTT 客户端，订阅 /vehicle/+/data
    mqtt_thread = threading.Thread(target=start_mqtt, daemon=True)
    mqtt_thread.start()

    # ③ 启动 Flask API，监听所有 API 请求
    app.run(host='0.0.0.0', port=5000, debug=True)
```

**关键概念：**
- MQTT 订阅用了通配符 `+`：`/vehicle/+/data` 可以匹配任意 VIN
- MQTT 在**后台线程**跑 `loop_forever()`，不阻塞 Flask 主线程
- Flask 用 `debug=True` 开发模式，改代码自动重启

**验证平台启动：**

```bash
curl http://localhost:5000/api/vehicles
# 返回 3 辆车的 JSON 数据 → 说明 API 正常
```

---

### 第四步：启动 TBOX 模拟器

**做什么：** 模拟一台真实车辆，每 5 秒上报一次数据

```bash
python tbox_sim.py
```

**TBOX 做了什么？** 打开 `tbox_sim.py` 看：

```python
# ① 连接 MQTT Broker
client.connect("localhost", 1883, 60)

# ② 订阅远程控制指令 Topic（接收平台下发的指令）
client.subscribe(f"/vehicle/{VIN}/control")

# ③ 设置遗嘱消息（Will Message）
#    如果 TBOX 异常断连，Broker 自动发遗嘱通知平台
will_msg = {'vin': VIN, 'status': 'offline', 'reason': 'connection_lost'}
client.will_set(f"/vehicle/{VIN}/status", will_msg, qos=1, retain=True)

# ④ 每 5 秒生成模拟数据并上报
while True:
    data = generate_vehicle_data()  # 随机生成车辆数据
    client.publish(f"/vehicle/{VIN}/data", json.dumps(data), qos=1)
    time.sleep(5)
```

**generate_vehicle_data() 生成哪些数据？**

| 字段 | 含义 | 模拟方式 |
|------|------|----------|
| soc | 电池电量 % | 85% 附近随机波动 |
| speed | 车速 km/h | 0~130 随机 |
| longitude/latitude | GPS 坐标 | 基于上海陆家嘴坐标微调 |
| battery_voltage | 电池电压 V | 380V 附近波动 |
| battery_temp | 电池温度 °C | 25°C 附近波动 |
| motor_speed | 电机转速 rpm | 0~8000 随机 |
| gear | 档位 | P/R/N/D 随机选 |

**关键概念：**
- **遗嘱消息（Will Message）**：MQTT 的特性，客户端断连时 Broker 自动发布预设消息。车联网中用来检测车辆离线。
- **QoS 1**：至少送达一次，保证数据不丢（车联网通常用 QoS 1）
- **Topic 设计**：`/vehicle/{VIN}/data` — 层级化设计，方便订阅过滤

---

### 第五步：手动验证 API

**做什么：** 用 curl 或 Postman 手动调用每个 API 确认结果

#### 5.1 车辆列表

```bash
curl http://localhost:5000/api/vehicles
```

**返回示例（关键字段解释）：**

```json
{
  "code": 200,
  "data": [{
    "vin": "LSVAU2A38N2100001",   ← 17位车辆识别码，每车唯一
    "plate_number": "沪A12345",   ← 车牌号
    "brand": "比亚迪",            ← 品牌
    "status": "driving",          ← 在线状态 (offline/online/driving/charging)
    "tbox_sn": "TBOX001",        ← TBOX 序列号
    "iccid": "89860112345678900001" ← SIM 卡号（20位）
  }]
}
```

#### 5.2 车辆详情（含最新状态）

```bash
curl http://localhost:5000/api/vehicles/LSVAU2A38N2100001
```

**面试重点：** `latest_status` 字段来自 `vehicle_status` 表 —— **API 做了两表关联查询**，把车辆档案 + 最新实时数据一起返回。

#### 5.3 运营看板

```bash
curl http://localhost:5000/api/statistics/dashboard
```

```json
{
  "totalVehicles": 3,       ← 总车辆数
  "onlineVehicles": 1,      ← 在线车辆数
  "onlineRate": "33.3%",    ← 在线率（面试时可以说这是运营核心指标）
  "activeAlerts": 2,        ← 活跃告警数
  "todayTrajectoryPoints": 15  ← 今日轨迹点数
}
```

#### 5.4 远程控制

```bash
# 下发闪灯指令
curl -X POST http://localhost:5000/api/control/LSVAU2A38N2100001 \
  -H "Content-Type: application/json" \
  -d '{"cmdType": "flash_light", "params": {"duration": 5}}'

# 查看控制历史
curl http://localhost:5000/api/control/LSVAU2A38N2100001/history
```

**远程控制流程（面试重点）：**
```
APP 发请求 → TSP API 接收 → 写入 control_cmd 表 → MQTT 下发到 TBOX
                                                    ↓
TBOX 执行 → MQTT 反馈结果 → TSP 更新指令状态
```

---

### 第六步：验证 MQTT 数据上报

**做什么：** 验证从 TBOX → MQTT → TSP → 数据库的完整链路

```bash
# 终端用 mosquitto_sub 直接监听（需要先配置 PATH 或使用完整路径）
"C:\Program Files\Mosquitto\mosquitto_sub.exe" -h localhost -t "/vehicle/+/data" -v

# 会看到 TBOX 模拟器上报的实时数据：
# /vehicle/LSVAU2A38N2100001/data {"soc":84.7,"speed":68,...}
# /vehicle/LSVAU2A38N2100001/data {"soc":84.3,"speed":102,...}
```

**数据库验证：**

```bash
sqlite3 tsp.db

-- 查最新 5 条车辆状态
SELECT vin, soc, speed, report_time
FROM vehicle_status
ORDER BY report_time DESC LIMIT 5;

-- 查轨迹点数
SELECT vin, COUNT(*) as cnt FROM trajectory GROUP BY vin;
```

**为什么用数据库验证？**
> 面试时可以说："测试不仅要看 API 返回对不对，还要去数据库核对底层数据，确保 API 和数据库一致。"

---

### 第七步：验证告警规则

**做什么：** 故意发送超阈值数据，验证告警是否自动生成

```bash
# 用 Python 一行脚本发送超速 + 高温数据
python -c "
import paho.mqtt.client as mqtt, json
client = mqtt.Client(client_id='test-alert')
client.connect('localhost', 1883, 60)
# 速度 135 > 120 阈值 → 应触发 overspeed
# 温度 65 > 60 阈值 → 应触发 high_temp
data = {'soc': 75, 'speed': 135, 'odometer': 32600,
        'longitude': 121.51, 'latitude': 31.25,
        'battery_voltage': 385, 'battery_temp': 65,
        'motor_speed': 5000, 'gear': 'D', 'status': 'driving'}
client.publish('/vehicle/LSVAU2A38N2100001/data', json.dumps(data))
client.disconnect()
"

# 然后查告警
curl http://localhost:5000/api/alerts
```

**3 条内置告警规则（在 `tsp_server.py` 的 `check_alerts()` 函数）：**

| 规则 | 触发条件 | 告警级别 |
|------|----------|----------|
| 超速告警 | speed > 120 km/h | critical（严重） |
| 低电量告警 | SOC < 20% | warning（警告） |
| 电池高温告警 | battery_temp > 60°C | critical（严重） |

**面试说：** "我在平台里内置了告警引擎，每条数据入库前会过规则引擎，触发条件就自动生成告警记录。生产环境可能会用 Flink/Kafka 做实时流处理，原理一样。"

---

### 第八步：运行自动化测试

**做什么：** 用 pytest 跑全套自动化测试

```bash
python -m pytest test_api.py -v
```

**测试结果（18 个用例全覆盖）：**

```
TestVehicleManagement::test_get_vehicle_list           PASSED  ← 车辆列表查询
TestVehicleManagement::test_get_vehicle_detail         PASSED  ← 车辆详情查询
TestVehicleManagement::test_filter_vehicles_by_status[online]   PASSED  ← 按状态筛选
TestVehicleManagement::test_filter_vehicles_by_status[offline]  PASSED
TestVehicleManagement::test_filter_vehicles_by_status[driving]  PASSED
TestVehicleManagement::test_filter_vehicles_by_status[charging] PASSED
TestVehicleManagement::test_register_duplicate_vin     PASSED  ← 重复注册拦截
TestVehicleManagement::test_get_nonexistent_vehicle    PASSED  ← 404 处理
TestRemoteControl::test_control_cmd_send               PASSED  ← 远程指令下发
TestRemoteControl::test_invalid_cmd_type               PASSED  ← 非法指令拦截
TestRemoteControl::test_control_history                PASSED  ← 控制历史查询
TestAlert::test_get_alerts                             PASSED  ← 告警列表查询
TestAlert::test_filter_alerts_by_type                  PASSED  ← 告警类型筛选
TestAlert::test_resolve_alert                          PASSED  ← 告警解除
TestTrajectory::test_get_trajectory                    PASSED  ← 轨迹查询
TestTrajectory::test_trajectory_with_time_range        PASSED  ← 时间范围筛选
TestDataConsistency::test_vehicle_status_in_db         PASSED  ← API↔DB一致性
TestDataConsistency::test_control_cmd_recorded         PASSED  ← 指令入库验证
```

**测试用例设计方法（面试可以展开讲）：**

| 测试类别 | 用例举例 | 方法 |
|----------|----------|------|
| **功能测试** | 查车辆列表、查轨迹、下发指令 | 验证正常输入 → 正确输出 |
| **异常测试** | 重复注册 VIN、非法指令类型 | 验证异常输入 → 被正确拦截 |
| **参数化测试** | 4 种状态筛选 | `@pytest.mark.parametrize` |
| **数据一致性测试** | 对比 API 返回 vs 数据库值 | 双端验证，确保数据不丢不错 |
| **边界值测试** | 告警阈值验证 | 119 不触发、120 触发 |

---

## API 接口文档

### 车辆管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/vehicles` | 查询车辆列表（支持 `?status=online&page=1&pageSize=20`） |
| GET | `/api/vehicles/<vin>` | 查询车辆详情（含最新状态） |
| POST | `/api/vehicles` | 注册车辆（Body: `{"vin":"...", "plate_number":"..."}`） |

### 远程控制

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/control/<vin>` | 下发远程控制指令（Body: `{"cmdType":"flash_light","params":{}}`） |
| GET | `/api/control/<vin>/history` | 查询控制历史 |

**支持的指令类型：** `unlock`, `lock`, `ac_on`, `ac_off`, `flash_light`, `horn`, `window_open`, `window_close`

### 轨迹查询

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/trajectory/<vin>` | 查询轨迹（支持 `?startTime=xxx&endTime=xxx`） |

### 告警管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/alerts` | 查询告警列表（支持 `?vin=&alertType=&isResolved=&page=&pageSize=`） |
| PUT | `/api/alerts/<id>/resolve` | 解除告警 |

### 运营统计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/statistics/dashboard` | 运营看板数据 |

---

## 数据库设计

```
tsp.db (SQLite)
├── vehicle_info      车辆主数据表     (VIN, 车牌, 品牌, 车主...)
├── vehicle_status    实时状态表        (SOC, 速度, GPS, 电池温度...) ← 时序数据
├── trajectory        轨迹点表          (经纬度, 速度, 方向角, 行程ID...)
├── alert_record      告警记录表        (告警类型, 级别, 是否解除...)
├── control_cmd       远程控制指令表    (指令类型, 参数, 执行状态...)
└── ota_task          OTA升级任务表     (固件版本, 升级进度...)
```

**ER 关系：** `vehicle_info.vin` ← 被 `vehicle_status` / `trajectory` / `alert_record` / `control_cmd` 外键引用

---

## 文件结构

```
tsp-test-project/
├── README.md                          ← 📖 项目文档（你正在看的）
├── CLAUDE.md                          ← 🤖 项目 AI 记忆文件
├── db_init.py                         ← 🗄️ 数据库初始化（6张表+测试数据）
├── tsp_server.py                      ← 🖥️ TSP 平台主服务（MQTT订阅+Flask API+告警）
├── tbox_sim.py                        ← 📡 TBOX 模拟器（定时上报+接收指令）
├── multi_tbox.py                      ← 📡📡📡 多车并发模拟（压测用）
├── test_api.py                        ← ✅ 自动化测试脚本（18个用例）
├── tsp.db                             ← 💾 SQLite 数据库（运行后生成）
├── 项目实战指南-车联网TSP测试.md        ← 📘 搭建步骤指南
└── 面试背诵文档-车联网TSP测试.md        ← 📙 面试概念背诵
```

---

## 面试演示话术

> 面试官问："你有没有实际的测试项目经验？"

**你可以这样回答（边说边展示）：**

> "我在面试前搭建了一个完整的**车联网 TSP 测试环境**。整体架构是：
>
> - 用 **Python + Flask** 写了 TSP 平台的 API 服务，包含车辆管理、远程控制、轨迹查询、告警管理、运营统计 5 大模块
> - 用 **Mosquitto** 搭建了 MQTT Broker，这是物联网最常用的消息中间件
> - 用 Python 脚本**模拟 TBOX 车载终端**，每 5 秒上报一次车辆数据（SOC、速度、GPS、电池等），同时能接收平台下发的远程控制指令
> - 数据跑通后，我编写了完整的 **pytest 自动化测试**，18 个用例覆盖功能、异常、数据一致性
>
> 额外我还能现场演示：启动平台 → TBOX 上报数据 → API 查询 → 数据库核验，您可以看下效果。"

**面试常见追问 & 应对：**

| 追问 | 应对 |
|------|------|
| "MQTT QoS 0/1/2 区别？" | QoS 0：最多一次（可能丢）；QoS 1：至少一次（可能重复，车联网常用）；QoS 2：恰好一次（开销大） |
| "怎么检测车辆离线？" | MQTT 遗嘱消息（Will Message）+ 心跳超时，代码里设置了 `will_set` |
| "大数据量下怎么优化？" | 车辆状态表按时间分区、轨迹数据压缩、告警用流处理（Flink），但 Demo 用 SQLite 够了 |
| "你怎么做数据一致性验证？" | API 返回的数据跟数据库直接查的结果做对比，`test_vehicle_status_in_db` 这个用例就是 |
| "远程控制的异常情况？" | 车辆离线不能下发、指令超时要有超时处理、弱网环境指令可能重复到达 |

---

## 许可证

MIT — 仅供学习交流使用

---

> 💡 **核心目标**：让面试官觉得你「不只是背了理论，真的动手做过车联网测试」— 你就赢了。
