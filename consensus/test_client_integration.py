"""
集成测试 — 启动共识网络 + 客户端提交交易
"""
import threading
import time
import sys
import os

from ConsensusNetwork import SeekNode
from ConsensusEngine import TBFTConsensusNode
from p2pnetwork.node import Node


class TestClient(Node):
    """测试客户端，发送交易并等待响应"""

    def __init__(self, host, port, target_host, target_port):
        super().__init__(host, port, id=f"test_client_{port}")
        self.result = None
        self._done = threading.Event()
        self._target = (target_host, target_port)

    def node_message(self, node, data):
        if isinstance(data, dict) and data.get("type") == "TX_RESULT":
            self.result = data
            self._done.set()

    def send_tx(self, content):
        self.send_to_nodes({"type": "USERPOST", "CONTENT": content})

    def wait_result(self, timeout=10):
        if self._done.wait(timeout):
            return self.result
        return None


def main():
    VALIDATORS = ["consensus1", "consensus2", "consensus3"]

    print("=" * 60)
    print("TBFT 集成测试：客户端交易上链")
    print("=" * 60)

    # —————— 1. 启动种子节点 ——————
    print("\n[1/4] 启动种子节点...")
    seed = SeekNode("127.0.0.1", 8001)
    seed.start()
    time.sleep(0.3)

    # —————— 2. 启动共识节点 ——————
    print("[2/4] 启动共识节点...")
    nodes: list[TBFTConsensusNode] = []
    for i, port in enumerate([8002, 8003, 8004], start=1):
        name = f"consensus{i}"
        node = TBFTConsensusNode("127.0.0.1", port, node_name=name,
                                 validators=VALIDATORS)
        node.start()
        node.connect_with_node("127.0.0.1", 8001)
        nodes.append(node)
        print(f"      {node.standard_name}")
        time.sleep(0.3)

    time.sleep(1.5)  # 等 P2P 拓扑建立

    # —————— 3. 客户端提交交易 ——————
    print("[3/4] 客户端提交交易...")
    client = TestClient("127.0.0.1", 9001, "127.0.0.1", 8002)
    client.start()
    client.connect_with_node("127.0.0.1", 8002)
    time.sleep(0.5)

    tx_content = "测试交易: 张三向李四转账100元"
    print(f"      发送: {tx_content}")
    client.send_tx(tx_content)

    # 等待上链结果
    result = client.wait_result(timeout=10)
    if result:
        print(f"\n      [OK] 上链成功  height={result['height']}  data={result['data']}")
    else:
        print("\n      [FAIL] 超时：未收到上链结果")
        # 检查各节点状态
        for node in nodes:
            print(f"      {node.standard_name}  step={node.engine.step}  "
                  f"round={node.engine.round}  height={len(node.chain)}")
        client.stop()
        for node in nodes:
            node.stop()
        seed.stop()
        sys.exit(1)

    client.stop()

    time.sleep(1)  # 等所有节点完成落链

    # —————— 4. 验证 ——————
    print("[4/4] 验证区块链...")
    all_ok = True
    for node in nodes:
        h = len(node.chain)
        print(f"      {node.standard_name}  height={h}")
        if h < 2:  # 创世块(1) + 客户端交易(1) = 2
            all_ok = False
        # 检查最后一个区块的内容
        last_block = node.chain.blocks[-1]
        if tx_content not in str(last_block.transaction_content):
            all_ok = False

    # 关闭
    print()
    for node in nodes:
        node.stop()
    seed.stop()

    if all_ok:
        print("=" * 60)
        print("测试通过！客户端交易成功上链")
        print("=" * 60)
        sys.exit(0)
    else:
        print("=" * 60)
        print("测试失败！链高度不符合预期")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
