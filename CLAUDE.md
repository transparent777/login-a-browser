# CLAUDE.md

## 项目概述
这是一个车联网 TSP（Telematics Service Platform）平台测试学习项目，面向车联网测试岗位的面试准备。

## 项目文件
- `面试背诵文档-车联网TSP测试.md` — 车联网核心概念、测试要点、面试问答
- `项目实战指南-车联网TSP测试.md` — 搭建模拟 TSP 平台的完整步骤指南

## 技术栈
- Python 3 + Flask（TSP 平台 API）
- Mosquitto（MQTT Broker）
- SQLite（数据存储）
- pytest（自动化测试）
- Postman、JMeter、Charles（测试工具）

## 核心业务概念
- **TSP**：车联网远程服务平台
- **TBOX**：车载智能终端，通过 4G + MQTT 与平台通信
- **MQTT**：发布/订阅模式的轻量级物联网协议（QoS 0/1/2）
- **GB/T 32960**：新能源车数据上报国家强制标准
- **OTA**：远程固件升级
- **VIN**：17 位车辆识别码

## 数据流向
```
TBOX → MQTT → TSP 平台 → REST API → APP/小程序/运营后台
                      ↘ → 国家监管平台 (GB/T 32960)
```
