"""
SM2 密钥预生成脚本 — 为每个共识节点生成密钥对并分发公钥
用法: python generate_keys.py [--config validators.json]
"""
import argparse
import json
import os
import sys

# 确保能找到同目录下的 ShangMi
sys.path.insert(0, os.path.dirname(__file__))
from ShangMi import sm2_generate_keypair


def main():
    parser = argparse.ArgumentParser(description="SM2 密钥生成工具")
    parser.add_argument("--config", default=os.path.join(os.path.dirname(__file__), "validators.json"),
                        help="共识节点配置文件")
    args = parser.parse_args()

    consensus_config_path = args.config
    client_config_path = os.path.join(os.path.dirname(__file__), "..", "client", "validators.json")
    nodes_dir = os.path.join(os.path.dirname(__file__), "Nodes")

    # 加载共识配置
    with open(consensus_config_path, "r", encoding="utf-8") as f:
        consensus_config = json.load(f)

    validators = consensus_config.get("validators", [])
    if not validators:
        print("[!] 配置文件中无 validators")
        return

    print(f"[*] 为 {len(validators)} 个共识节点生成 SM2 密钥对...\n")

    for v in validators:
        node_id = v["id"]
        pri_key, pub_key = sm2_generate_keypair()

        # 私钥写入 Nodes/<node_id>/sm2_key.json
        node_dir = os.path.join(nodes_dir, node_id)
        os.makedirs(node_dir, exist_ok=True)
        key_path = os.path.join(node_dir, "sm2_key.json")
        with open(key_path, "w", encoding="utf-8") as f:
            json.dump({"private_key": pri_key, "public_key": pub_key}, f, indent=2)
        print(f"  [{node_id}] 私钥 → {key_path}")

        # 公钥写入 consensus/validators.json
        v["public_key"] = pub_key
        print(f"  [{node_id}] 公钥: {pub_key[:32]}...")

    # 写回共识配置文件
    with open(consensus_config_path, "w", encoding="utf-8") as f:
        json.dump(consensus_config, f, indent=2, ensure_ascii=False)
    print(f"\n[*] 公钥已写入 {consensus_config_path}")

    # 同步公钥到 client/validators.json
    if os.path.isfile(client_config_path):
        with open(client_config_path, "r", encoding="utf-8") as f:
            client_config = json.load(f)
    else:
        client_config = {"validators": []}

    # 按 id 匹配更新（客户端配置可能字段不同，只更新 public_key）
    client_nodes = client_config.get("validators") or client_config.get("nodes") or client_config.get("peers") or []
    for v in validators:
        for cn in client_nodes:
            if cn.get("id") == v["id"]:
                cn["public_key"] = v["public_key"]
                break

    if "validators" in client_config:
        client_config["validators"] = client_nodes
    elif "nodes" in client_config:
        client_config["nodes"] = client_nodes
    elif "peers" in client_config:
        client_config["peers"] = client_nodes

    with open(client_config_path, "w", encoding="utf-8") as f:
        json.dump(client_config, f, indent=2, ensure_ascii=False)
    print(f"[*] 公钥已同步到 {client_config_path}")

    print("\n[*] 密钥生成完成。")


if __name__ == "__main__":
    main()
