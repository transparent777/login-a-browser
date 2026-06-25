"""
车联网 TSP 平台 — API 自动化测试
使用 pytest 框架，覆盖：功能测试、异常测试、数据一致性测试
"""

import requests
import pytest
import json
import sqlite3
import datetime

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
