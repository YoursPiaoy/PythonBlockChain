"""
TBFT — Tendermint 风格的拜占庭容错共识引擎。

长安链核心共识协议，5 阶段状态机：
  NewRound -> Proposal -> Prevote -> Precommit -> Commit

特性：
  - >2/3 投票阈值
  - Leader 轮换制 (height + round) % validator_count
  - 锁定机制确保安全性
  - 超时自动进入下一轮
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from ShangMi import sm3_hash_string


# —————————————————————————————— 常量 ——————————————————————————————

PROPOSE_TIMEOUT_BASE = 0.3       # 提案超时基数（秒）
PROPOSE_TIMEOUT_DELTA = 0.2      # 每轮递增
PREVOTE_TIMEOUT_BASE = 0.3
PREVOTE_TIMEOUT_DELTA = 0.2
PRECOMMIT_TIMEOUT_BASE = 0.3
PRECOMMIT_TIMEOUT_DELTA = 0.2
THRESHOLD_RATIO = 2 / 3          # 拜占庭容错阈值


# —————————————————————————————— 阶段枚举 ——————————————————————————————

class Step(Enum):
    NEW_ROUND = "NEW_ROUND"
    PROPOSAL = "PROPOSAL"
    PREVOTE = "PREVOTE"
    PRECOMMIT = "PRECOMMIT"
    COMMIT = "COMMIT"


# —————————————————————————————— 数据结构 ——————————————————————————————

@dataclass
class Proposal:
    """区块提议"""
    height: int
    round: int
    block_data: str
    block_hash: str
    proposer: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class Vote:
    """投票"""
    height: int
    round: int
    block_hash: str | None        # None = nil vote
    voter: str
    vote_type: str                # "PREVOTE" | "PRECOMMIT"


# —————————————————————————————— TBFT 引擎 ——————————————————————————————

class TBFTEngine:
    """
    可插拔 TBFT 共识引擎，通过回调与网络层解耦。

    使用方式:
        engine = TBFTEngine(
            node_id="node1",
            validators=["node1","node2","node3","node4"],
            on_broadcast=lambda msg: ...,
            on_send=lambda target, msg: ...,
            on_commit=lambda proposal: ...,
            on_propose=lambda height, round: "交易数据",
        )
        engine.start()
        # 收到网络消息时
        engine.receive(msg_dict, sender_id)
    """

    def __init__(self, node_id: str,
                 validators: list[str],
                 on_broadcast: Callable[[dict], None],
                 on_send: Callable[[str, dict], None],
                 on_commit: Callable[[Proposal], None],
                 on_propose: Callable[[int, int], str | None]):
        self.node_id = node_id              # 本节点标识，对应验证者名称
        self.validators = validators        # 验证者名称列表，用于选 leader、算阈值
        self.on_broadcast = on_broadcast    # 广播共识消息的回调
        self.on_send = on_send              # 点对点发送消息的回调
        self.on_commit = on_commit          # 区块达成共识后的回调（通知上层落链）
        self.on_propose = on_propose        # 轮到本节点提议时的回调（获取待打包数据）

        # 共识进度
        self.height = 1
        self.round = 0
        self.step = Step.NEW_ROUND

        # 锁定机制（Tendermint 安全核心）
        self.locked_block: Proposal | None = None
        self.locked_round: int = -1
        self.valid_block: Proposal | None = None
        self.valid_round: int = -1

        # 当前轮临时状态
        self._proposal: Proposal | None = None
        self._prevotes: dict[str, Vote] = {}
        self._precommits: dict[str, Vote] = {}

        # 定时器 & 线程安全
        self._timer: threading.Timer | None = None
        self._lock = threading.RLock()
        self._running = False

    # —————————————————— 属性 ——————————————————

    @property
    def proposer(self) -> str:
        """本轮提议者"""
        return self.validators[(self.height + self.round) % len(self.validators)]

    @property
    def is_proposer(self) -> bool:
        return self.node_id == self.proposer

    @property
    def threshold(self) -> int:
        """需要 >2/3 的票数"""
        return int(len(self.validators) * THRESHOLD_RATIO) + 1

    @property
    def state(self) -> dict:
        """返回当前状态快照（调试用）"""
        return {
            "node": self.node_id, "height": self.height, "round": self.round,
            "step": self.step.value, "proposer": self.proposer,
            "is_proposer": self.is_proposer,
            "prevotes": len(self._prevotes), "precommits": len(self._precommits),
        }

    # —————————————————— 启动 / 停止 ——————————————————

    def start(self):
        self._running = True
        self._transition_to(Step.NEW_ROUND)

    def stop(self):
        self._running = False
        self._cancel_timer()

    # —————————————————— 消息入口 ——————————————————

    def receive(self, msg: dict, sender_id: str):
        """网络层收到共识消息时调用"""
        if not self._running:
            return
        t = msg.get("type")
        with self._lock:
            if t == "PROPOSAL":
                self._handle_proposal(msg, sender_id)
            elif t == "PREVOTE":
                self._handle_vote(msg, sender_id, "PREVOTE")
            elif t == "PRECOMMIT":
                self._handle_vote(msg, sender_id, "PRECOMMIT")

    # —————————————————— 提议入口 ——————————————————

    def propose_block(self, block_data: str):
        """提议者调用，将区块广播给全网"""
        with self._lock:
            if self.step != Step.PROPOSAL or not self.is_proposer:
                return
            block_hash = sm3_hash_string(block_data)
            self._proposal = Proposal(
                height=self.height, round=self.round,
                block_data=block_data, block_hash=block_hash,
                proposer=self.node_id,
            )
            self._broadcast({
                "type": "PROPOSAL",
                "height": self.height, "round": self.round,
                "block_data": block_data, "block_hash": block_hash,
                "proposer": self.node_id,
            })
            self._transition_to(Step.PREVOTE)

    # —————————————————— 状态转移 ——————————————————

    def _transition_to(self, target: Step):
        self._cancel_timer()
        self.step = target

        {
            Step.NEW_ROUND:  self._enter_new_round,
            Step.PROPOSAL:   self._enter_proposal,
            Step.PREVOTE:    self._enter_prevote,
            Step.PRECOMMIT:  self._enter_precommit,
            Step.COMMIT:     self._enter_commit,
        }[target]()

    # —————————————————— NEW_ROUND ——————————————————

    def _enter_new_round(self):
        self._proposal = None
        self._prevotes.clear()
        self._precommits.clear()

        t = PROPOSE_TIMEOUT_BASE + self.round * PROPOSE_TIMEOUT_DELTA
        self._set_timer(t, self._on_propose_timeout)

        print(f"[{self.node_id}] > NewRound    h={self.height} r={self.round}  "
              f"proposer={self.proposer}")

        if self.is_proposer:
            self._transition_to(Step.PROPOSAL)

    # —————————————————— PROPOSAL ——————————————————

    def _enter_proposal(self):
        t = PROPOSE_TIMEOUT_BASE + self.round * PROPOSE_TIMEOUT_DELTA
        self._set_timer(t, self._on_propose_timeout)

        print(f"[{self.node_id}] | Proposal    h={self.height} r={self.round}  "
              f"(我是提议者)")

        block_data = self.on_propose(self.height, self.round)
        if block_data is not None:
            self.propose_block(block_data)

    def _handle_proposal(self, msg: dict, sender: str):
        if self.step not in (Step.NEW_ROUND, Step.PROPOSAL):
            return
        h, r = msg["height"], msg["round"]
        if (h, r) != (self.height, self.round):
            return
        if sender != self.proposer:
            print(f"[{self.node_id}] [!] 非提议者 {sender} 发送提议，忽略")
            return

        expected = sm3_hash_string(msg["block_data"])
        if expected != msg["block_hash"]:
            print(f"[{self.node_id}] [!] 提议哈希校验失败")
            return

        self._proposal = Proposal(
            height=h, round=r, block_data=msg["block_data"],
            block_hash=msg["block_hash"], proposer=sender,
        )
        print(f"[{self.node_id}] o 收到提议    h={h} r={r}  "
              f"hash={msg['block_hash'][:8]}...  from={sender}")
        self._transition_to(Step.PREVOTE)

    def _on_propose_timeout(self):
        with self._lock:
            if self.step in (Step.NEW_ROUND, Step.PROPOSAL):
                print(f"[{self.node_id}] [T/O] 提案超时   h={self.height} r={self.round}  "
                      f"-> r={self.round + 1}")
                self.round += 1
                self._transition_to(Step.NEW_ROUND)

    # —————————————————— PREVOTE ——————————————————

    def _enter_prevote(self):
        t = PREVOTE_TIMEOUT_BASE + self.round * PREVOTE_TIMEOUT_DELTA
        self._set_timer(t, self._on_prevote_timeout)

        block_hash = self._decide_prevote()
        self._broadcast({
            "type": "PREVOTE",
            "height": self.height, "round": self.round,
            "block_hash": block_hash, "voter": self.node_id,
        })
        label = block_hash[:8] + "..." if block_hash else "nil"
        print(f"[{self.node_id}] >> Prevote     h={self.height} r={self.round}  "
              f"{label}")

    def _decide_prevote(self) -> str | None:
        """Tendermint 锁定规则：优先投 locked_block"""
        if self._proposal is None:
            # 未收到提议，如果有 locked_block 则投它，否则投 nil
            return self.locked_block.block_hash if self.locked_block else None
        # 收到提议：如果 locked 且和提议不同，投 nil（不打破锁定）
        if (self.locked_block is not None and
                self.locked_round < self.round and
                self._proposal.block_hash != self.locked_block.block_hash):
            return None
        return self._proposal.block_hash

    def _on_prevote_timeout(self):
        with self._lock:
            if self.step == Step.PREVOTE:
                print(f"[{self.node_id}] [T/O] Prevote超时 h={self.height} r={self.round}  "
                      f"-> r={self.round + 1}")
                self.round += 1
                self._transition_to(Step.NEW_ROUND)

    # —————————————————— PRECOMMIT ——————————————————

    def _enter_precommit(self):
        t = PRECOMMIT_TIMEOUT_BASE + self.round * PRECOMMIT_TIMEOUT_DELTA
        self._set_timer(t, self._on_precommit_timeout)

        block_hash = self._decide_precommit()
        if block_hash is not None and self._proposal is not None:
            self.locked_block = self._proposal
            self.locked_round = self.round

        self._broadcast({
            "type": "PRECOMMIT",
            "height": self.height, "round": self.round,
            "block_hash": block_hash, "voter": self.node_id,
        })
        label = block_hash[:8] + "..." if block_hash else "nil"
        print(f"[{self.node_id}] >> Precommit   h={self.height} r={self.round}  "
              f"{label}  {'[锁定]' if block_hash else ''}")

    def _decide_precommit(self) -> str | None:
        if self._proposal is not None:
            return self._proposal.block_hash
        if self.locked_block is not None:
            return self.locked_block.block_hash
        return None

    def _on_precommit_timeout(self):
        with self._lock:
            if self.step == Step.PRECOMMIT:
                print(f"[{self.node_id}] [T/O] Precommit超时 h={self.height} r={self.round}"
                      f"  -> r={self.round + 1}")
                self.round += 1
                self._transition_to(Step.NEW_ROUND)

    # —————————————————— COMMIT ——————————————————

    def _enter_commit(self):
        proposal = self._proposal
        if proposal is None:
            self.round += 1
            self._transition_to(Step.NEW_ROUND)
            return

        print(f"[{self.node_id}] [OK] 已提交区块  h={proposal.height}  "
              f"hash={proposal.block_hash[:8]}...  "
              f"content=\"{proposal.block_data}\"")
        self.on_commit(proposal)

        self.height += 1
        self.round = 0
        self.locked_block = None
        self.locked_round = -1
        self.valid_block = None
        self.valid_round = -1
        self._transition_to(Step.NEW_ROUND)

    # —————————————————— 投票汇总 ——————————————————

    def _handle_vote(self, msg: dict, sender: str, vote_type: str):
        h, r = msg["height"], msg["round"]
        if (h, r) != (self.height, self.round):
            return

        vote = Vote(
            height=h, round=r, block_hash=msg["block_hash"],
            voter=sender, vote_type=vote_type,
        )

        if vote_type == "PREVOTE":
            self._prevotes[sender] = vote
            self._check_prevote_majority()
        else:
            self._precommits[sender] = vote
            self._check_precommit_majority()

    def _check_prevote_majority(self):
        if self.step != Step.PREVOTE:
            return

        counts: dict[str, int] = {}
        nil_count = 0
        for v in self._prevotes.values():
            if v.block_hash is None:
                nil_count += 1
            else:
                counts[v.block_hash] = counts.get(v.block_hash, 0) + 1

        t = self.threshold
        # 需要 >2/3 非 nil 投票才能进入 Precommit
        best_hash = max(counts, key=counts.get) if counts else None
        best_count = counts.get(best_hash, 0) if best_hash else 0

        if best_count >= t:
            if self._proposal and self._proposal.block_hash == best_hash:
                self.valid_block = self._proposal
                self.valid_round = self.round
            print(f"[{self.node_id}] o Prevote达成  {best_count}/{len(self._prevotes)}  "
                  f"hash={best_hash[:8]}...")
            self._transition_to(Step.PRECOMMIT)

    def _check_precommit_majority(self):
        if self.step != Step.PRECOMMIT:
            return

        counts: dict[str, int] = {}
        for v in self._precommits.values():
            if v.block_hash is not None:
                counts[v.block_hash] = counts.get(v.block_hash, 0) + 1

        t = self.threshold
        for bh, cnt in counts.items():
            if cnt >= t:
                print(f"[{self.node_id}] o Precommit达成 {cnt}/{len(self._precommits)} "
                      f"hash={bh[:8]}...")
                self._transition_to(Step.COMMIT)
                return

    # —————————————————— 网络通信 ——————————————————

    def _broadcast(self, msg: dict):
        self.on_broadcast(msg)
        # 模拟 self-receive（确保自己也计入投票）
        self.receive(msg, self.node_id)

    # —————————————————— 定时器 ——————————————————

    def _set_timer(self, timeout: float, callback):
        self._cancel_timer()
        self._timer = threading.Timer(timeout, callback)
        self._timer.daemon = True
        self._timer.start()

    def _cancel_timer(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
