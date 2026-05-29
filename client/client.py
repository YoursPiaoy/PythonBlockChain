"""
客户端脚本 — 连接共识节点，提交交易数据
用法: python client.py [--host 127.0.0.1] [--port 9000] [--timeout 10] --config validators.json
"""


import argparse
import json
import os
import threading
from p2pnetwork.node import Node

from consensus.ShangMi import (sm2_encrypt, sm2_decrypt, sm2_verify_hash, sm2_sign_hash,
                                sm2_generate_keypair, sm3_hash_string)

CLIENT_KEY_FILE = os.path.join(os.path.dirname(__file__), "sm2_key.json")


class ClientNode(Node):
    """客户端 P2P 节点，连接共识节点并提交交易"""

    def __init__(self, host: str, port: int, timeout: float = 10.0):
        super().__init__(host, port, id=f"client_{port}")
        self.timeout = timeout
        self._result: threading.Event = threading.Event()
        self._result_ok: bool = False
        self._result_data: dict | None = None
        self._validator_pubkeys: dict[str, str] = {}  # node_id → public_key
        # 客户端自身的 SM2 密钥对
        self._client_pri, self._client_pub = self._load_or_generate_keypair()

    def _load_or_generate_keypair(self) -> tuple[str, str]:
        """加载客户端 SM2 密钥对，不存在则自动生成并持久化"""
        if os.path.isfile(CLIENT_KEY_FILE):
            with open(CLIENT_KEY_FILE, "r", encoding="utf-8") as f:
                key = json.load(f)
            pri, pub = key["private_key"], key["public_key"]
            print(f"[*] 已加载客户端 SM2 密钥对 ({CLIENT_KEY_FILE})")
            return pri, pub
        # 首次运行，生成新密钥对
        pri, pub = sm2_generate_keypair()
        os.makedirs(os.path.dirname(CLIENT_KEY_FILE), exist_ok=True)
        with open(CLIENT_KEY_FILE, "w", encoding="utf-8") as f:
            json.dump({"private_key": pri, "public_key": pub}, f, indent=2)
        print(f"[*] 已生成客户端 SM2 密钥对 → {CLIENT_KEY_FILE}")
        return pri, pub

    def load_pubkeys(self, nodes: list[dict]) -> None:
        """从节点配置中提取 SM2 公钥"""
        for n in nodes:
            pub_key = n.get("public_key")
            if pub_key:
                node_id = n.get("id", f"{n.get('host')}:{n.get('port')}")
                self._validator_pubkeys[node_id] = pub_key
        if self._validator_pubkeys:
            print(f"[*] 已加载 {len(self._validator_pubkeys)} 个共识节点公钥")

    def node_message(self, node, data):
        if not isinstance(data, dict):
            return

        msg_type = data.get("type")
        if msg_type == "TX_RECEIVED":
            # 阶段一：共识节点已接收，即将投票
            print(f"\n[接收] 节点 {data.get('node')} 已收到: {data.get('content')}")
        elif msg_type == "TX_RESULT":
            result_data = data

            # SM2 解密回复数据（共识节点用客户端公钥加密）
            if data.get("encrypted"):
                encrypted_payload = data.get("data")
                try:
                    decrypted = sm2_decrypt(self._client_pri, self._client_pub, encrypted_payload)
                    result_data = dict(data)
                    result_data["data"] = decrypted
                except Exception:
                    print("[!] TX_RESULT 解密失败")
                    return

            # SM2 签名验证（共识节点私钥签名）
            sig = data.get("signature")
            sign_data = data.get("sign_data")
            signer_id = data.get("signer_id")
            if sig and sign_data and signer_id and self._validator_pubkeys:
                pub_key = self._validator_pubkeys.get(signer_id)
                if pub_key is None:
                    print(f"[!] 未找到节点 {signer_id} 的公钥，无法验证签名")
                    return
                hash_val = sm3_hash_string(sign_data)
                if sm2_verify_hash(pub_key, hash_val, sig):
                    print("[*] 签名验证通过")
                else:
                    print("[!] 签名验证失败，结果不可信!")
                    return

            self._result_ok = result_data.get("status") == "ok"
            self._result_data = result_data
            self._result.set()
        elif msg_type == "PEER_LIST":
            for peer in data.get("peers", []):
                self.connect_with_node(peer["host"], peer["port"])
        elif msg_type == "NEW_PEER":
            peer = data["peer"]
            self.connect_with_node(peer["host"], peer["port"])

    def send_tx(self, content: str) -> bool:
        if not self.all_nodes:
            print("[!] 未连接到任何共识节点，发送失败")
            return False

        self._result.clear()
        self._result_ok = False
        self._result_data = None

        # SM2 加密交易内容 + 客户端签名（使用已连接节点的公钥）
        payload = {"type": "USERPOST", "CONTENT": content}
        if self._validator_pubkeys and self.all_nodes:
            target_id = self.all_nodes[0].id
            pub_key = self._validator_pubkeys.get(target_id)
            if pub_key:
                encrypted = sm2_encrypt(pub_key, content)
                content_hash = sm3_hash_string(content)
                client_sig = sm2_sign_hash(self._client_pri, content_hash)
                payload = {
                    "type": "USERPOST",
                    "CONTENT": encrypted,
                    "encrypted": True,
                    "client_public_key": self._client_pub,
                    "client_signature": client_sig,
                }
                print(f"[*] 已加密交易内容 (SM2) + 客户端签名")

        self.send_to_nodes(payload)
        print(f"[*] 已提交交易: {content}  (等待共识结果...)")

        if self._result.wait(timeout=self.timeout):
            data = self._result_data
            status = "成功" if self._result_ok else "失败"
            print(f"\n[上链{status}] height={data.get('height')}  "
                  f"data={data.get('data')}")
            return self._result_ok
        else:
            print(f"[!] 超时 ({self.timeout}s): 未收到共识结果，发送可能失败")
            return False


def load_nodes(path: str) -> list[dict]:
    """从 JSON 文件加载共识节点列表，支持 validators / nodes / peers 三种字段名"""
    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)
    for key in ("validators", "nodes", "peers"):
        if key in config:
            return config[key]
    return []


def try_connect_nodes(client: "ClientNode", nodes: list[dict]) -> bool:
    """逐个尝试连接节点列表，直到有一个连接成功，返回是否成功"""
    for node in nodes:
        host = node.get("host", "127.0.0.1")
        port = node.get("port")
        node_id = node.get("id", f"{host}:{port}")
        if not port:
            continue
        print(f"[*] 尝试连接 {node_id} ({host}:{port})...")
        if client.connect_with_node(host, port):
            print(f"[*] 成功连接 {node_id}")
            return True
        print(f"[*] 连接 {node_id} 失败，尝试下一个...")
    return False


def main():
    parser = argparse.ArgumentParser(description="TBFT 客户端")
    parser.add_argument("--host", default="127.0.0.1", help="本机地址")
    parser.add_argument("--port", type=int, default=9000, help="本机端口")
    parser.add_argument("--config",
                        default=os.path.join(os.path.dirname(__file__), "validators.json"),
                        help="共识节点配置文件路径 (JSON)")
    parser.add_argument("--timeout", type=float, default=10.0, help="交易超时(秒)")
    args = parser.parse_args()

    # 解析配置文件路径
    config_path = args.config
    if not os.path.isabs(config_path):
        candidates = [config_path, os.path.join(os.path.dirname(__file__), config_path)]
    else:
        candidates = [config_path]

    resolved = None
    for p in candidates:
        if os.path.isfile(p):
            resolved = p
            break

    if resolved is None:
        print(f"[!] 配置文件不存在: {args.config}")
        return

    print(f"[*] 客户端启动: {args.host}:{args.port}")
    print(f"[*] 加载节点配置: {resolved}")
    nodes = load_nodes(resolved)
    if not nodes:
        print("[!] 配置文件中未找到任何共识节点")
        return

    client = ClientNode(args.host, args.port, timeout=args.timeout)
    client.load_pubkeys(nodes)
    client.start()

    if not try_connect_nodes(client, nodes):
        print("[!] 未能连接到任何共识节点，退出")
        client.stop()
        return

    print("\n输入交易内容后回车发送，输入 q 退出\n")

    try:
        while True:
            cmd = input("> ").strip()
            if cmd.lower() == "q":
                break
            if cmd:
                client.send_tx(cmd)
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        client.stop()
        print("[*] 客户端已关闭")


if __name__ == "__main__":
    main()
