import os
from datetime import datetime
from p2pnetwork.node import Node
import time


SEEK_LOG_DIR = os.path.join(os.path.dirname(__file__), "Nodes", "seed")


class SeekNode(Node):
    """种子节点：负责节点发现和网络拓扑组织"""
    def __init__(self, host, port, id='SEEDNODE', callback=None, max_connections=0):
        super().__init__(host, port, id, callback, max_connections)
        self.standard_name = f"{self.id} @ {self.host}:{self.port}"
        os.makedirs(SEEK_LOG_DIR, exist_ok=True)
        self._log_fp = open(os.path.join(SEEK_LOG_DIR, "seed.log"), "a", encoding="utf-8")

    def _write_log(self, msg: str) -> None:
        if not self._log_fp:
            return
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._log_fp.write(f"[{ts}] [{self.id}] {msg}\n")
        self._log_fp.flush()

    def _peer_desc(self, node) -> str:
        return f"{node.host}:{node.port} (id={node.id})"

    def inbound_node_connected(self, node):
        super().inbound_node_connected(node)
        self._write_log(f"节点接入: {self._peer_desc(node)}")
        print(f"[{self.standard_name}] 节点接入: {self._peer_desc(node)}")

        # 把已有节点的地址信息发给新节点，让它去连接
        peers_info = [
            {"host": n.host, "port": int(n.port), "id": n.id}
            for n in self.nodes_inbound if n != node
        ]
        if peers_info:
            time.sleep(0.05)
            self.send_to_node(node, {
                "type": "PEER_LIST",
                "peers": peers_info
            })

        # 把新节点信息广播给所有已连接的旧节点（通过 exclude 排除新节点自身）
        time.sleep(0.05)
        self.send_to_nodes({
            "type": "NEW_PEER",
            "peer": {"host": node.host, "port": int(node.port), "id": node.id}
        }, exclude=[node])

    def outbound_node_connected(self, node):
        super().outbound_node_connected(node)
        self._write_log(f"连接节点: {self._peer_desc(node)}")
        print(f"[{self.standard_name}] 连接节点: {self._peer_desc(node)}")

    def node_disconnected(self, node):
        super().node_disconnected(node)
        self._write_log(f"节点断开: {self._peer_desc(node)}")
        print(f"[{self.standard_name}] 节点断开: {self._peer_desc(node)}")

    def stop(self):
        super().stop()
        if self._log_fp:
            self._log_fp.close()
            self._log_fp = None

    def __del__(self):
        if hasattr(self, '_log_fp') and self._log_fp:
            self._log_fp.close()
            self._log_fp = None


class ConsensusNode(Node):
    """共识节点：参与区块链共识的普通节点"""
    def __init__(self, host, port, node_name="consensus", callback=None, max_connections=0):
        super().__init__(host, port, node_name, callback, max_connections)
        self.standard_name = f"{self.id} @ {self.host}:{self.port}"

    def node_message(self, node, data):
        if not isinstance(data, dict) or "type" not in data:
            return

        msg_type = data["type"]

        if msg_type == "PEER_LIST":
            for peer in data["peers"]:
                self.connect_with_node(peer["host"], peer["port"])
            return
        if msg_type == "NEW_PEER":
            self.connect_with_node(data["peer"]["host"], data["peer"]["port"])
            return
        if msg_type == "SHUTDOWN":
            self.stop()
            return

        self._handle_message(node, data)

    def _handle_message(self, node, data):
        """子类重写以处理自定义消息类型"""


if __name__ == "__main__":
    # 启动种子节点
    seed = SeekNode("127.0.0.1", 8001)
    seed.start()
    print(f"[*] 种子节点已启动: {seed.standard_name}")
    time.sleep(0.3)

    # 启动三个共识节点
    for i, port in enumerate([8002, 8003, 8004], start=1):
        node = ConsensusNode("127.0.0.1", port, node_name=f"consensus{i}")
        node.start()
        node.connect_with_node("127.0.0.1", 8001)
        time.sleep(0.3)

    time.sleep(1)
