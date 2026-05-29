"""
TBFT 共识节点 — 打通 TBFTStateMachine 和 P2P 网络层
"""

import os
import time
from ConsensusNetwork import SeekNode, ConsensusNode
from TBFT import TBFTStateMachine
from ChainBuild import BlockChain, add_block, save


class TBFTConsensusNode(ConsensusNode):
    """携带 TBFT 共识引擎的共识节点"""

    def __init__(self, host: str, port: int, node_name: str,
                 validators: list[str], max_connections: int = 0):
        super().__init__(host, port, node_name, callback=None, max_connections=max_connections)
        self.validators: list[str] = validators
        self._tx_queue: list[str] = []          # 待上链交易队列
        self._client_nodes: list = []           # 客户端节点（用于回复）

        # 区块链持久化
        self.chain_path = os.path.join("Nodes", node_name, "chain.json")
        self.chain = self._init_chain()

        self.engine = TBFTStateMachine(
            node_id=node_name,
            validators=validators,
            on_commit=self._on_block_committed,
            on_broadcast=self._broadcast_consensus,
            on_propose=self._get_block_data,
            log_file=os.path.join("Nodes", node_name, "consensus.log"),
        )
        self.engine.height = len(self.chain)

    def _init_chain(self):
        """加载已有链，不存在则创建创世区块"""
        chain = BlockChain.load(self.chain_path)
        if chain is None:
            chain = BlockChain()
            save(chain, self.chain_path)
            print(f"[{self.standard_name}] 未找到链文件，已生成创世区块")
        else:
            print(f"[{self.standard_name}] 已加载链  height={len(chain)}")
        return chain

    def _broadcast_consensus(self, msg: dict) -> None:
        """TBFT 引擎 → P2P 网络广播（含自投票）"""
        self.send_to_nodes(msg)
        # 网络广播不包含自己，手动计入自投票
        if msg["type"] == "PREVOTE":
            self.engine.on_prevote(msg)
        elif msg["type"] == "PRECOMMIT":
            self.engine.on_precommit(msg)

    def _on_block_committed(self, proposal: dict) -> None:
        """区块达成共识，落链回调"""
        add_block(proposal["data"], self.chain)
        save(self.chain, self.chain_path)
        print(f"[{self.standard_name}] 区块落链  height={proposal['height']}  "
              f"data={proposal['data']}")
        # 回复连接本节点的客户端
        for client in self._client_nodes:
            try:
                self.send_to_node(client, {
                    "type": "TX_RESULT",
                    "status": "ok",
                    "height": proposal["height"],
                    "data": proposal["data"],
                })
            except Exception:
                pass
        self._client_nodes.clear()
        self._tx_queue.clear()

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
            self._tx_queue.append(data["CONTENT"])
            if node not in self._client_nodes:
                self._client_nodes.append(node)
            self.send_to_nodes({"type": "CONSENSUS_TRIGGER",
                                "CONTENT": data["CONTENT"]})
            self.next_round()
            return

        # 其他节点转发来的交易触发
        if msg_type == "CONSENSUS_TRIGGER":
            self._tx_queue.append(data["CONTENT"])
            self.next_round()
            return

        # 共识消息 → TBFT 引擎
        if msg_type == "PROPOSAL":
            self.engine.on_proposal(data)
        elif msg_type == "PREVOTE":
            self.engine.on_prevote(data)
        elif msg_type == "PRECOMMIT":
            self.engine.on_precommit(data)

    def next_round(self):
        self.engine.next_round()


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
