"""
共识节点启动脚本 — 读取 validators.json 启动所有共识节点
用法: python start_nodes.py [--config validators.json]
"""

import argparse
import json
import signal
import threading
import time
import sys
from ConsensusEngine import TBFTConsensusNode
from ConsensusNetwork import SeekNode


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)
    if "seed" not in config:
        raise ValueError("配置文件缺少 seed")
    if "validators" not in config or not config["validators"]:
        raise ValueError("配置文件缺少 validators")
    return config


def main():
    parser = argparse.ArgumentParser(description="TBFT 共识节点启动脚本")
    parser.add_argument("--config", default="validators.json", help="配置文件路径")
    args = parser.parse_args()

    config = load_config(args.config)
    seed_cfg = config["seed"]
    validator_list = config["validators"]

    # 提取验证者 id 列表（传给 TBFT 引擎）
    validator_ids = [v["id"] for v in validator_list]

    nodes: list[TBFTConsensusNode] = []
    seed: SeekNode | None = None
    shutdown = threading.Event()  # 关闭信号

    def stop_all():
        print("\n[*] 正在关闭所有节点...")
        shutdown.set()
        for node in nodes:
            node.stop()
        if seed:
            seed.stop()
        print("[*] 所有节点已关闭")

    def on_signal(signum, frame):
        stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, on_signal)   # Ctrl+C
    signal.signal(signal.SIGTERM, on_signal)  # kill

    # —————— 1. 启动种子节点 ——————
    seed = SeekNode(seed_cfg["host"], seed_cfg["port"])
    seed.start()
    print(f"[*] 种子节点启动: {seed.standard_name}")
    time.sleep(0.3)

    # —————— 2. 逐台启动共识节点 ——————
    for v in validator_list:
        node = TBFTConsensusNode(
            host=v["host"],
            port=v["port"],
            node_name=v["id"],
            validators=validator_ids,
        )
        node.start()
        node.connect_with_node(seed_cfg["host"], seed_cfg["port"])
        nodes.append(node)
        print(f"[*] 共识节点启动: {node.standard_name}")
        time.sleep(0.3)

    time.sleep(1)  # 等 P2P 拓扑建立

    # —————— 3. 交互循环 ——————
    print("\n共识节点就绪，等待客户端交易。输入 q 退出\n")

    while not shutdown.is_set():
        try:
            cmd = input("> ").strip().lower()
        except EOFError:
            break

        if cmd == "q":
            break
        elif cmd == "":
            continue
        else:
            print("未知命令，输入 q 退出")

    stop_all()


if __name__ == "__main__":
    main()
