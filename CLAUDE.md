# CLAUDE.md

## 项目概述
这是一个车联网 TSP（Telematics Service Platform）平台测试学习项目，面向车联网测试岗位的面试准备。
**项目已完整搭建并验证通过，所有功能可运行。**

## 项目状态
- ✅ 数据库初始化（6 张表 + 3 辆测试车）
- ✅ TSP 平台 API（Flask + MQTT 订阅）
- ✅ TBOX 模拟器（定时上报 + 接收远程指令）
- ✅ 自动化测试（18 个用例全部通过）
- ✅ 告警规则引擎（超速 / 低电量 / 电池高温）
- ✅ 端到端数据链路验证

## 项目文件

### 核心代码
- `db_init.py` — 数据库初始化，创建 6 张表 + 插入 3 辆测试车
- `tsp_server.py` — TSP 平台主服务（Flask API + paho-mqtt 订阅 + 告警规则）
- `tbox_sim.py` — TBOX 模拟器（每 5 秒上报数据，接收远程指令）
- `multi_tbox.py` — 多车并发模拟（3 台车同时上报）
- `test_api.py` — pytest 自动化测试脚本（18 个用例）

### 文档
- `README.md` — 完整的 GitHub 项目文档（架构图 + 演示教程 + API 文档 + 面试话术）
- `面试背诵文档-车联网TSP测试.md` — 车联网核心概念、测试要点、面试问答
- `面试背诵文档-车联网TSP测试.docx` — 同上 docx 版本
- `项目实战指南-车联网TSP测试.md` — 搭建模拟 TSP 平台的完整步骤指南
- `CLAUDE.md` — 项目 AI 记忆文件（本文件）

### 生成文件
- `tsp.db` — SQLite 数据库（运行 db_init.py 后自动生成）

## 启动命令

```bash
# 终端 1：启动 TSP 平台（API :5000 + MQTT 订阅）
python tsp_server.py

# 终端 2：启动 TBOX 模拟器
python tbox_sim.py

# 终端 3：运行测试
python -m pytest test_api.py -v
```

## 技术栈
- Python 3.6 + Flask 0.12（TSP 平台 API）
- Mosquitto 2.1（MQTT Broker，端口 1883）
- paho-mqtt 1.6（Python MQTT 客户端）
- SQLite 3（数据存储，在 tsp.db 中）
- pytest 3.2（自动化测试框架，18 个用例）
- requests 2.18（HTTP 客户端，测试用）

## 测试工具（可选）
- Postman（手动 API 测试，可导出 Collection）
- JMeter（压力测试）
- Charles（HTTP/MQTT 抓包）

## 核心业务概念
- **TSP**：Telematics Service Platform，车联网远程服务平台
- **TBOX**：车载智能终端，通过 4G + MQTT 与平台通信
- **MQTT**：发布/订阅模式的轻量级物联网协议（QoS 0/1/2，默认端口 1883）
- **GB/T 32960**：新能源车数据上报国家强制标准
- **OTA**：远程固件升级（Over The Air）
- **VIN**：17 位车辆识别码（Vehicle Identification Number）
- **SOC**：电池电量百分比（State of Charge）
- **ICCID**：SIM 卡唯一标识（20 位数字）
- **遗嘱消息（Will Message）**：MQTT 客户端断连时 Broker 自动发布的预设消息

## 数据流向
```
TBOX → MQTT (publish /vehicle/{VIN}/data)
       ↓
    Mosquitto Broker (localhost:1883)
       ↓
TSP 平台 (paho-mqtt subscribe /vehicle/+/data)
       ↓
  ┌─→ SQLite (vehicle_status, trajectory)
  └─→ 告警引擎 (check_alerts) → alert_record
       ↓
Flask REST API (:5000) → APP/小程序/运营后台
       ↓
MQTT (publish /vehicle/{VIN}/control) → TBOX 接收并执行
```

## API 接口概览
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/vehicles | 车辆列表（支持 status/page/pageSize） |
| GET | /api/vehicles/<vin> | 车辆详情 + 最新状态 |
| POST | /api/vehicles | 注册车辆 |
| POST | /api/control/<vin> | 下发远程控制指令 |
| GET | /api/control/<vin>/history | 控制历史 |
| GET | /api/trajectory/<vin> | 轨迹查询（支持 startTime/endTime） |
| GET | /api/alerts | 告警列表（支持 vin/alertType/isResolved） |
| PUT | /api/alerts/<id>/resolve | 解除告警 |
| GET | /api/statistics/dashboard | 运营看板 |

## 数据库表结构
6 张核心表：vehicle_info, vehicle_status, trajectory, alert_record, control_cmd, ota_task

## 告警规则
1. 超速告警：speed > 120 km/h → critical
2. 低电量告警：SOC < 20% → warning
3. 电池高温告警：battery_temp > 60°C → critical

## 测试覆盖（18 个用例）
- 车辆管理：列表查询、详情查询、状态筛选(4种)、重复注册拦截、404处理
- 远程控制：指令下发、非法指令拦截、控制历史
- 告警管理：告警列表、类型筛选、告警解除
- 轨迹查询：轨迹查询、时间范围筛选
- 数据一致性：API vs DB 状态对比、控制指令入库验证

## 测试数据
3 辆测试车：
- LSVAU2A38N2100001 — 沪A12345 — 比亚迪 汉EV — 张三
- LSVAU2A38N2100002 — 京B67890 — 特斯拉 Model 3 — 李四
- LSVAU2A38N2100003 — 粤C11111 — 蔚来 ET5 — 王五

## 已知注意事项
- Mosquitto 在 Windows 需要手动安装，安装路径 `C:\Program Files\Mosquitto`
- Mosquitto 命令行工具需要添加到系统 PATH
- Python 3.6 版本较老，f-string 可用但部分新特性不可用
- `tsp_server.py` 中的 MQTT 订阅在 daemon 线程中运行，主进程退出时自动结束
- 远程控制 API 依赖 MQTT 下发，车辆离线时会返回 400
