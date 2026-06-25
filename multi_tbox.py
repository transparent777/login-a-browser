"""
车联网 TSP 平台 — 多车并发模拟器
同时启动多台模拟 TBOX，用于压力测试和场景验证
"""

import threading
import time
import tbox_sim

# 模拟的车辆 VIN 列表
VINS = [
    'LSVAU2A38N2100001',
    'LSVAU2A38N2100002',
    'LSVAU2A38N2100003',
]

# 如果想添加更多模拟车辆，在这里追加 VIN
# 注意：需要先在 vehicle_info 表中注册该 VIN


def main():
    print("=" * 60)
    print("多车并发 TBOX 模拟器")
    print(f"将同时启动 {len(VINS)} 台车辆: {VINS}")
    print("=" * 60)

    threads = []
    for vin in VINS:
        t = threading.Thread(target=tbox_sim.run_with_vin, args=(vin,), daemon=True)
        t.start()
        threads.append(t)
        time.sleep(0.5)  # 错开启动，避免同时连接
        print(f"  [{vin}] 已启动")

    print(f"\n全部 {len(VINS)} 台 TBOX 已启动, 按 Ctrl+C 停止\n")

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        print("\n所有 TBOX 模拟器已停止")


if __name__ == '__main__':
    main()
