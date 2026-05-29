"""
TBFT 共识节点 — 打通 TBFTStateMachine 和 P2P 网络层
"""

import json
import os
import time
from datetime import datetime

from BlockBuild import Block
from ChainBuild import BlockChain, add_block, save, validate
from ConsensusNetwork import SeekNode, ConsensusNode
from ShangMi import (sm2_decrypt, sm2_encrypt, sm2_sign_hash,
                     sm2_verify_hash, sm3_hash_string)
from TBFT import TBFTStateMachine


class TBFTConsensusNode(ConsensusNode):
    """携带 TBFT 共识引擎的共识节点"""

    _DATA_DIR = os.path.join(os.path.dirname(__file__), "Nodes")

    def __init__(self, host: str, port: int, node_name: str,
                 validators: list[str], max_connections: int = 0,
                 validator_pubkeys: dict[str, str] | None = None):
        super().__init__(host, port, node_name, callback=None, max_connections=max_connections)
        self.validators: list[str] = validators
        self._tx_queue: list[str] = []          # 待上链交易队列
        self._seen_txs: set[str] = set()       # 已见交易哈希，防重复
        self._clients: dict = {}               # 客户端 node → public_key
        self._validator_pubkeys: dict[str, str] = validator_pubkeys or {}

        # SM2 密钥对
        self._private_key, self._public_key = self._load_keypair(node_name)

        if not self._validator_pubkeys:
            print(f"[WARNING] 未加载任何共识节点公钥，共识消息签名验证已禁用！")

        # 区块链持久化
        self.chain_path = os.path.join(self._DATA_DIR, node_name, "chain.json")
        self.chain = self._init_chain()

        self.engine = TBFTStateMachine(
            node_id=node_name,
            validators=validators,
            on_commit=self._on_block_committed,
            on_broadcast=self._broadcast_consensus,
            on_propose=self._get_block_data,
            log_file=os.path.join(self._DATA_DIR, node_name, "consensus.log"),
        )
        self.engine.height = len(self.chain)

    def _init_chain(self):
        """加载已有链，不存在则创建创世区块。校验失败则回退到创世块并备份损坏文件。"""
        chain = BlockChain.load(self.chain_path)
        if chain is None:
            chain = BlockChain()
            save(chain, self.chain_path)
            print(f"[{self.standard_name}] 未找到链文件，已生成创世区块")
        else:
            print(f"[{self.standard_name}] 已加载链  height={len(chain)}")
            if not validate(chain):
                print(f"[{self.standard_name}] 链校验失败，备份损坏文件并重建创世区块")
                # 备份损坏的链文件
                backup_path = self.chain_path + ".corrupted"
                try:
                    os.rename(self.chain_path, backup_path)
                    print(f"[{self.standard_name}] 已备份损坏链 -> {backup_path}")
                except OSError:
                    pass
                chain = BlockChain()
                save(chain, self.chain_path)
                print(f"[{self.standard_name}] 已从创世区块重建链")
        return chain

    def _load_keypair(self, node_name: str) -> tuple[str | None, str | None]:
        """从 Nodes/<node_name>/sm2_key.json 加载 SM2 密钥对"""
        key_path = os.path.join(self._DATA_DIR, node_name, "sm2_key.json")
        if not os.path.isfile(key_path):
            print(f"[{node_name}] 未找到 SM2 密钥文件 {key_path}，将使用明文模式")
            return None, None
        with open(key_path, "r", encoding="utf-8") as f:
            key_data = json.load(f)
        pri = key_data.get("private_key")
        pub = key_data.get("public_key")
        print(f"[{node_name}] 已加载 SM2 密钥对")
        return pri, pub

    def _broadcast_consensus(self, msg: dict) -> None:
        """TBFT 引擎 → P2P 网络广播（含自投票 + SM2 签名）"""
        # 对共识消息签名
        if self._private_key:
            sign_str = self._build_sign_string(msg)
            hash_val = sm3_hash_string(sign_str)
            msg["_sig"] = sm2_sign_hash(self._private_key, hash_val)
            msg["_signer"] = self.id
        # 先计入自投票，再广播到网络
        if msg["type"] == "PREVOTE":
            self.engine.on_prevote(msg)
        elif msg["type"] == "PRECOMMIT":
            self.engine.on_precommit(msg)
        self.send_to_nodes(msg)

    def _build_sign_string(self, msg: dict) -> str:
        """构建签名用的规范字符串"""
        t = msg["type"]
        if t == "PROPOSAL":
            return f"{msg['height']}|{msg['round']}|{msg['data']}|{msg['proposer']}|{msg.get('timestamp', '')}"
        elif t in ("PREVOTE", "PRECOMMIT"):
            return f"{msg['height']}|{msg['round']}|{msg['voter']}|{msg['vote'] or 'nil'}"
        return str(msg)

    def _verify_msg(self, msg: dict) -> bool:
        """验证共识消息的 SM2 签名"""
        sig = msg.get("_sig")
        signer = msg.get("_signer")
        if not sig or not signer:
            return False
        pub_key = self._validator_pubkeys.get(signer)
        if not pub_key:
            print(f"[{self.standard_name}] 未找到节点 {signer} 的公钥")
            return False
        sign_str = self._build_sign_string(msg)
        hash_val = sm3_hash_string(sign_str)
        return sm2_verify_hash(pub_key, hash_val, sig)

    def _on_block_committed(self, proposal: dict) -> None:
        """区块达成共识，落链回调"""
        add_block(proposal["data"], self.chain, proposal.get("timestamp"))
        save(self.chain, self.chain_path)
        print(f"[{self.standard_name}] 区块落链  height={proposal['height']}  "
              f"data={proposal['data']}")
        original_data = proposal["data"]

        # 回复连接本节点的客户端
        for client, client_pub in self._clients.items():
            reply = {
                "type": "TX_RESULT",
                "status": "ok",
                "height": proposal["height"],
                "data": original_data,
                "signer_id": self.id,
            }

            # 用客户端公钥加密回复数据
            if client_pub and self._private_key and self._public_key:
                encrypted_data = sm2_encrypt(client_pub, original_data)
                reply["data"] = encrypted_data
                reply["encrypted"] = True

                # SM2 签名（签名对象为 height|encrypted_data，不泄露明文）
                sign_data = f"{proposal['height']}|{encrypted_data}"
                hash_val = sm3_hash_string(sign_data)
                sig = sm2_sign_hash(self._private_key, hash_val)
                reply["signature"] = sig
                reply["sign_data"] = sign_data

            try:
                self.send_to_node(client, reply)
            except Exception:
                pass
        self._clients.clear()

    def _get_block_data(self, height: int, round: int) -> str | None:
        """提议者从队列取交易数据，队列空则跳过本轮"""
        if self._tx_queue:
            return self._tx_queue.pop(0)
        return None

    def _handle_message(self, node, data):
        """处理自定义消息：交易触发 + 共识路由"""
        msg_type = data["type"]

        # 客户端交易 → 入队 + 广播触发共识
        if msg_type == "USERPOST":
            raw_content = data["CONTENT"]

            # SM2 解密（如果客户端加密了）
            if data.get("encrypted") and self._private_key and self._public_key:
                try:
                    raw_content = sm2_decrypt(self._private_key, self._public_key, raw_content)
                except Exception:
                    print(f"[{self.standard_name}] SM2 解密失败，丢弃消息")
                    return

            # 验证客户端签名（如果提供了）
            client_pub = data.get("client_public_key")
            client_sig = data.get("client_signature")
            if client_pub and client_sig:
                content_hash = sm3_hash_string(raw_content)
                if sm2_verify_hash(client_pub, content_hash, client_sig):
                    print(f"[{self.standard_name}] 客户端签名验证通过")
                    self._clients[node] = client_pub
                else:
                    print(f"[{self.standard_name}] 客户端签名验证失败，丢弃消息")
                    return

            # 防重复：用交易内容哈希判断是否已处理过
            tx_hash = sm3_hash_string(raw_content)
            if tx_hash in self._seen_txs:
                return
            self._seen_txs.add(tx_hash)
            self._tx_queue.append(raw_content)
            self._clients.setdefault(node, None)
            # 立即回复客户端确认收到
            self.send_to_node(node, {
                "type": "TX_RECEIVED",
                "node": self.standard_name,
                "content": raw_content,
            })
            # 转发给其他共识节点，确保提议者能收到（防重复已在对方节点处理）
            self.send_to_nodes({
                "type": "USERPOST",
                "CONTENT": raw_content,
            }, exclude=[node])
            # 仅在空闲时触发新一轮
            if self.engine.step == "NEW_ROUND":
                self.next_round()
            return

        # 共识消息 → TBFT 引擎（含签名验证）
        if msg_type in ("PROPOSAL", "PREVOTE", "PRECOMMIT"):
            if self._validator_pubkeys and not self._verify_msg(data):
                print(f"[{self.standard_name}] 签名验证失败，丢弃 {msg_type} 消息")
                return
            if msg_type == "PROPOSAL":
                self.engine.on_proposal(data)
            elif msg_type == "PREVOTE":
                self.engine.on_prevote(data)
            elif msg_type == "PRECOMMIT":
                self.engine.on_precommit(data)

        # 链同步消息
        if msg_type == "SYNC_HELLO":
            peer_height = data["height"]
            peer_hash = data["last_hash"]
            local_height = len(self.chain)
            local_hash = self.chain[-1].self_hash
            if peer_height > local_height:
                self._request_sync(node, local_height)
            elif peer_height == local_height and peer_hash != local_hash:
                print(f"[{self.standard_name}] 警告: 分叉检测! "
                      f"相同高度 {local_height} 但哈希不同, "
                      f"本地={local_hash[:16]}... 远端={peer_hash[:16]}...")
                # 以远端链为准，回退最后一区块后重新同步
                if len(self.chain) > 1:
                    print(f"[{self.standard_name}] 回退最后一个区块并请求同步")
                    self.chain.pop()
                    self._request_sync(node, len(self.chain))
            return

        if msg_type == "SYNC_REQUEST":
            from_height = data["from_height"]
            blocks = []
            for i in range(from_height, len(self.chain)):
                b = self.chain[i]
                blocks.append({
                    "index": b.index,
                    "previous_block_hash": b.previous_block_hash,
                    "transaction_content": b.transaction_content,
                    "timestamp": b.timestamp,
                    "self_hash": b.self_hash,
                })
            self.send_to_node(node, {
                "type": "SYNC_RESPONSE",
                "blocks": blocks,
            })
            return

        if msg_type == "SYNC_RESPONSE":
            blocks_data = data["blocks"]
            if not blocks_data:
                return
            pre_sync_height = len(self.chain)
            for bd in blocks_data:
                block = Block(
                    index=bd["index"],
                    previous_block_hash=bd["previous_block_hash"],
                    transaction_content=bd["transaction_content"],
                    timestamp=bd["timestamp"],
                )
                block.self_hash = bd["self_hash"]
                if block.self_hash != block.get_self_hash():
                    print(f"[{self.standard_name}] 同步区块 {bd['index']} 哈希校验失败，回滚")
                    del self.chain.blocks[pre_sync_height:]
                    return
                if len(self.chain) > 0 and block.previous_block_hash != self.chain[-1].self_hash:
                    print(f"[{self.standard_name}] 同步区块 {bd['index']} 链接校验失败，回滚")
                    del self.chain.blocks[pre_sync_height:]
                    return
                self.chain.append(block)
            # 整链校验
            if not validate(self.chain):
                print(f"[{self.standard_name}] 同步后整链校验失败，回滚")
                del self.chain.blocks[pre_sync_height:]
                return
            save(self.chain, self.chain_path)
            self.engine.height = len(self.chain)
            print(f"[{self.standard_name}] 链同步完成, 新高度={len(self.chain)}")
            # 同步完成后，如果空闲则启动新轮
            if self.engine.step == "NEW_ROUND":
                self.next_round()
            return

    def next_round(self):
        self.engine.next_round()

    # —————— P2P 连接事件日志 ——————

    def _peer_desc(self, node) -> str:
        return f"{node.host}:{node.port} (id={node.id})"

    def _log_peer(self, msg: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.engine._log(f"[{ts}] {msg}")

    def inbound_node_connected(self, node):
        super().inbound_node_connected(node)
        self._log_peer(f"节点接入: {self._peer_desc(node)}")

    def outbound_node_connected(self, node):
        super().outbound_node_connected(node)
        self._log_peer(f"连接节点: {self._peer_desc(node)}")
        # 连接建立后发起链同步
        self._send_sync_hello(node)

    def _send_sync_hello(self, node) -> None:
        """向对等节点发送链摘要信息"""
        last_block = self.chain[-1]
        self.send_to_node(node, {
            "type": "SYNC_HELLO",
            "height": len(self.chain),
            "last_hash": last_block.self_hash,
        })

    def _request_sync(self, node, from_height: int) -> None:
        """请求对等节点发送从 from_height 开始的区块"""
        self.send_to_node(node, {
            "type": "SYNC_REQUEST",
            "from_height": from_height,
        })

    def node_disconnected(self, node):
        super().node_disconnected(node)
        self._log_peer(f"节点断开: {self._peer_desc(node)}")

    def stop(self):
        super().stop()
        self.engine.stop()


# ==================== 测试入口 ====================

if __name__ == "__main__":
    VALIDATORS = ["consensus1", "consensus2", "consensus3"]

    # 1. 启动种子节点
    seed = SeekNode("127.0.0.1", 8001)
    seed.start()
    print(f"[*] 种子节点启动: {seed.standard_name}")
    time.sleep(0.3)

    # 2. 启动 3 个 TBFT 共识节点，连到种子节点
    nodes = []
    for i, port in enumerate([8002, 8003, 8004], start=1):
        name = f"consensus{i}"
        node = TBFTConsensusNode("127.0.0.1", port, node_name=name,
                                 validators=VALIDATORS)
        node.start()
        node.connect_with_node("127.0.0.1", 8001)
        nodes.append(node)
        print(f"[*] 共识节点启动: {node.standard_name}")
        time.sleep(0.3)

    time.sleep(1)  # 等 P2P 拓扑建立完成

    print("\n共识节点就绪，等待客户端交易。使用 client.py 发送交易\n")

    # 3. 等待后关闭
    time.sleep(60)
    for node in nodes:
        node.stop()
    seed.stop()
