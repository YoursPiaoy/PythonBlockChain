"""
客户端脚本 — 连接共识节点，提交交易数据
用法: python client.py [--host 127.0.0.1] [--port 9000] [--target 8002]
"""

import argparse
from p2pnetwork.node import Node


class ClientNode(Node):
    """客户端 P2P 节点，连接共识节点并提交交易"""

    def __init__(self, host: str, port: int, target_host: str, target_port: int):
        super().__init__(host, port, id=f"client_{port}")
        self.target_host = target_host
        self.target_port = target_port

    def node_message(self, node, data):
        if not isinstance(data, dict):
            return

        msg_type = data.get("type")
        if msg_type == "TX_RESULT":
            status = "成功" if data.get("status") == "ok" else "失败"
            print(f"\n[上链{status}] height={data.get('height')}  "
                  f"data={data.get('data')}")
        elif msg_type == "PEER_LIST":
            for peer in data.get("peers", []):
                self.connect_with_node(peer["host"], peer["port"])
        elif msg_type == "NEW_PEER":
            peer = data["peer"]
            self.connect_with_node(peer["host"], peer["port"])

    def send_tx(self, content: str):
        msg = {"type": "USERPOST", "CONTENT": content}
        self.send_to_nodes(msg)


def main():
    parser = argparse.ArgumentParser(description="TBFT 客户端")
    parser.add_argument("--host", default="127.0.0.1", help="本机地址")
    parser.add_argument("--port", type=int, default=9000, help="本机端口")
    parser.add_argument("--target", type=int, default=8002,
                        help="目标共识节点端口 (8002=consensus1, 8003=consensus2, 8004=consensus3)")
    args = parser.parse_args()

    target_host = "127.0.0.1"

    print(f"[*] 客户端启动: {args.host}:{args.port}")
    print(f"[*] 目标共识节点: {target_host}:{args.target}")

    client = ClientNode(args.host, args.port, target_host, args.target)
    client.start()
    client.connect_with_node(target_host, args.target)

    print("\n输入交易内容后回车发送，输入 q 退出\n")

    try:
        while True:
            cmd = input("> ").strip()
            if cmd.lower() == "q":
                break
            if cmd:
                client.send_tx(cmd)
                print(f"[*] 已发送交易: {cmd}")
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        client.stop()
        print("[*] 客户端已关闭")


if __name__ == "__main__":
    main()
