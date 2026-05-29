"""
共识节点启动脚本 — 支持单机和多机部署

用法:
  python start_nodes.py [--with-seed] [--config PATH]

参数:
  --config PATH   共识节点配置文件路径 (JSON)
                  默认值: 脚本同目录下的 validators.json
                  文件格式见下方示例

  --with-seed     在本机同时启动种子节点 (SeedNode)
                  不加此参数时，认为种子已在远端运行，只连接到配置中的 seed 地址
                  适用场景: 多机部署中只有一台机器加此参数，其余机器不加

配置文件 (validators.json) 中的关键字段:
  seed.host/port        种子节点地址（本机或远端）
  validators[].id       共识节点唯一标识
  validators[].host     节点绑定的 IP 地址
  validators[].port     节点绑定的端口
  validators[].local    是否在本机启动此节点 (true=本机, false=远端)
                        不设置此字段时，默认所有节点都在本机启动（向后兼容）

多机部署步骤:
  1. 在一台机器上生成密钥:  python generate_keys.py
  2. 将 validators.json 复制到每台机器（内容一致）
  3. 在每台机器上编辑 validators.json，将自己运行的节点标记 "local": true
  4. 种子机启动:  python start_nodes.py --with-seed
  5. 其他机器启动: python start_nodes.py
"""
import argparse
import json
import os
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
    parser.add_argument("--config",
                        default=os.path.join(os.path.dirname(__file__), "validators.json"),
                        help="共识节点配置文件路径 (JSON)")
    parser.add_argument("--with-seed", action="store_true",
                        help="在本机启动种子节点（多机部署时只有一台机器需要此参数）")
    args = parser.parse_args()

    config = load_config(args.config)
    seed_cfg = config["seed"]
    validator_list = config["validators"]

    # 提取验证者 id 列表（传给 TBFT 引擎，全量）
    validator_ids = [v["id"] for v in validator_list]

    # —————— 区分本机节点和远端节点 ——————
    local_validators = [v for v in validator_list if v.get("local", False)]
    remote_validators = [v for v in validator_list if not v.get("local", False)]

    # 向后兼容：如果没有任何节点标记 local，则全部视为本机
    if not local_validators:
        local_validators = validator_list
        remote_validators = []

    if not local_validators:
        print("[!] 配置文件中未找到任何共识节点")
        return

    print(f"[*] 本机节点 ({len(local_validators)}): "
          f"{', '.join(v['id'] for v in local_validators)}")
    if remote_validators:
        print(f"[*] 远端节点 ({len(remote_validators)}): "
              f"{', '.join(v['id'] for v in remote_validators)}")
    else:
        print(f"[*] 未检测到远端节点，运行单机模式")

    nodes: list[TBFTConsensusNode] = []
    seed: SeekNode | None = None
    shutdown = threading.Event()

    def stop_all():
        print("\n[*] 正在关闭所有节点...")
        shutdown.set()
        for node in nodes:
            node.stop()
        if seed:
            seed.stop()

    def on_signal(signum, frame):
        stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    # —————— 1. 种子节点 ——————
    if args.with_seed:
        seed = SeekNode(seed_cfg["host"], seed_cfg["port"])
        seed.start()
        print(f"[*] 种子节点启动: {seed.standard_name}")
        time.sleep(0.3)
    else:
        print(f"[*] 种子节点在远端 {seed_cfg['host']}:{seed_cfg['port']}，跳过本地启动")

    # —————— 2. 启动本机共识节点 ——————
    for v in local_validators:
        node = TBFTConsensusNode(
            host=v["host"],
            port=v["port"],
            node_name=v["id"],
            validators=validator_ids,
        )
        node.start()
        nodes.append(node)
        print(f"[*] 本机共识节点启动: {node.standard_name}")
        time.sleep(0.3)

    # —————— 3. 连接种子节点 ——————
    seed_host, seed_port = seed_cfg["host"], seed_cfg["port"]
    for node in nodes:
        node.connect_with_node(seed_host, seed_port)
        time.sleep(0.1)
    seed_label = "本机" if seed else "远端"
    print(f"[*] 所有本机节点已连接{seed_label}种子 {seed_host}:{seed_port}")

    # —————— 4. 连接远端共识节点（直连冗余）——————
    for rv in remote_validators:
        for node in nodes:
            node.connect_with_node(rv["host"], rv["port"])
            time.sleep(0.1)
        print(f"[*] 已连接远端共识节点: {rv['id']} ({rv['host']}:{rv['port']})")

    time.sleep(1)  # 等 P2P 拓扑建立

    # —————— 5. 交互循环 ——————
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
