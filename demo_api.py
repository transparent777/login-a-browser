"""
面试演示脚本 - 一键调用所有 API，展示 TSP 平台功能
用法: python demo_api.py
"""
import requests
import json

BASE = "http://localhost:5000"

def hr(title):
    """打印分隔标题"""
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)

def call(method, path, desc, **kwargs):
    """统一调用 API 并打印结果"""
    url = BASE + path
    resp = requests.request(method, url, **kwargs)
    print(f"\n>>> {desc}")
    print(f"    {method} {path}")
    try:
        data = resp.json()
        # 如果 data 太长，截断
        text = json.dumps(data, ensure_ascii=False, indent=2)
        if len(text) > 1500:
            text = text[:1500] + "\n    ... (输出过长，已截断)"
        print(f"    响应: {text}")
    except:
        print(f"    响应: {resp.text[:500]}")
    return resp

# ==============================
# 第 1 组：运营看板（上来就亮结果）
# ==============================
hr("1. 运营看板 Dashboard")
call("GET", "/api/statistics/dashboard", "运营数据总览（总车数/在线率/活跃告警/今日轨迹点）")

# ==============================
# 第 2 组：车辆管理
# ==============================
hr("2. 车辆列表")
call("GET", "/api/vehicles", "查询全部车辆")

hr("3. 车辆详情")
call("GET", "/api/vehicles/LSVAU2A38N2100001", "查询比亚迪汉EV 详细数据 + 最新状态")

hr("4. 按状态筛选")
call("GET", "/api/vehicles?status=driving", "筛选行驶中的车辆")

# ==============================
# 第 3 组：告警管理
# ==============================
hr("5. 告警列表")
call("GET", "/api/alerts", "查询所有告警记录")

hr("6. 按类型筛选告警")
call("GET", "/api/alerts?alertType=overspeed", "只看超速告警")

# ==============================
# 第 4 组：轨迹查询
# ==============================
hr("7. 轨迹查询")
call("GET", "/api/trajectory/LSVAU2A38N2100001", "查看车辆轨迹数据")

# ==============================
# 第 5 组：远程控制
# ==============================
hr("8. 远程控制指令下发")
call("POST", "/api/control/LSVAU2A38N2100001", "下发闪灯指令",
     json={"cmdType": "flash_light", "params": {"duration": 5}})

hr("9. 非法指令拦截（异常测试）")
call("POST", "/api/control/LSVAU2A38N2100001", "发送不支持的指令类型，验证后端拦截",
     json={"cmdType": "start_engine", "params": {}})

hr("10. 控制历史")
call("GET", "/api/control/LSVAU2A38N2100001/history", "查看历史控制指令")

print()
print("=" * 60)
print("  演示完成！以上覆盖了 TSP 平台所有核心 API")
print("=" * 60)
