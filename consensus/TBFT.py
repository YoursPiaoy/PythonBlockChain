"""
TBFT 五阶段状态机（含超时检测）
NewRound -> Proposal -> Prevote -> Precommit -> Commit
每个阶段有独立超时，超时自动推进到下一轮。
"""

import threading


class TBFTStateMachine:
    # 各阶段超时（秒），COMMIT 瞬时完成不需要超时
    TIMEOUTS: dict[str, float] = {
        "NEW_ROUND": 5.0,
        "PROPOSAL":  3.0,
        "PREVOTE":   5.0,
        "PRECOMMIT": 5.0,
    }

    def __init__(self,
                 node_id: str,        # 本节点名称
                 validators: list[str],    # 所有验证者节点名称列表
                 on_commit, on_broadcast, on_propose,
                 log_file: str | None = None):

        self.node_id: str = node_id
        self.validators: list[str] = validators
        self.on_commit = on_commit
        self.on_broadcast = on_broadcast
        self.on_propose = on_propose

        self.height: int = 1
        self.round: int = 0
        self.step: str = "NEW_ROUND"

        self.locked_block: dict | None = None   # 锁定的区块
        self.proposal: dict | None = None       # 当前提案
        self.prevotes: dict[str, str | None] = {}     # voter -> 区块数据或nil
        self.precommits: dict[str, str | None] = {}   # voter -> 区块数据或nil

        self._lock = threading.RLock()
        self._timer: threading.Timer | None = None
        self._timer_gen: int = 0               # 代际：防止旧定时器误触发
        self._stopped: bool = False

        # 日志：有文件则写文件，否则不输出
        if log_file:
            self._log_fp = open(log_file, "a", encoding="utf-8")
        else:
            self._log_fp = None

    def _log(self, msg: str) -> None:
        if self._log_fp:
            self._log_fp.write(msg + "\n")
            self._log_fp.flush()

    @property
    def proposer(self):
        """本轮 Leader"""
        return self.validators[(self.height + self.round) % len(self.validators)]

    @property
    def is_proposer(self):
        return self.node_id == self.proposer

    @property
    def threshold(self):
        """>2/3 阈值"""
        return int(len(self.validators) * 2 / 3) + 1

    # ==================== 入口 ====================

    def start(self):
        with self._lock:
            self.goto("NEW_ROUND")

    # ==================== 定时器 ====================

    def _start_timer(self) -> None:
        """为当前阶段启动超时定时器，代际+1 使旧定时器无效"""
        if self._stopped:
            return
        self._timer_gen += 1
        gen = self._timer_gen
        duration = self.TIMEOUTS.get(self.step)
        if duration is None:
            return
        self._timer = threading.Timer(duration, self._on_timeout, args=(gen,))
        self._timer.daemon = True
        self._timer.start()

    def _on_timeout(self, gen: int) -> None:
        """定时器回调，代际不匹配则忽略"""
        with self._lock:
            if self._stopped or gen != self._timer_gen:
                return
            self.timeout()

    def stop(self) -> None:
        """停止状态机，清理定时器与日志"""
        self._stopped = True
        if self._timer:
            self._timer.cancel()
            self._timer = None
        if self._log_fp:
            self._log_fp.close()
            self._log_fp = None

    # ==================== 状态转移 ====================

    def goto(self, step):
        with self._lock:
            if self._stopped:
                return
            self.step = step
            {
                "NEW_ROUND":   self.enter_new_round,
                "PROPOSAL":    self.enter_proposal,
                "PREVOTE":     self.enter_prevote,
                "PRECOMMIT":   self.enter_precommit,
                "COMMIT":      self.enter_commit,
            }[step]()
        self._start_timer()

    # ==================== 1. NEW_ROUND ====================

    def enter_new_round(self):
        self.proposal = None
        self.prevotes.clear()
        self.precommits.clear()
        self._log(f"[{self.node_id}] {self.height}:{self.round} NewRound  leader={self.proposer}")
        if self.is_proposer:
            self.goto("PROPOSAL")

    # ==================== 2. PROPOSAL ====================

    def enter_proposal(self):
        self._log(f"[{self.node_id}] {self.height}:{self.round} Proposal  (我是提议者)")
        data = self.on_propose(self.height, self.round)
        if data is not None:
            self.propose_block(data)

    def propose_block(self, data):
        """Leader 广播提案"""
        with self._lock:
            if self.step != "PROPOSAL" or not self.is_proposer:
                return None
            self.proposal = {"height": self.height, "round": self.round,
                             "data": data, "proposer": self.node_id}
            self.on_broadcast({"type": "PROPOSAL", **self.proposal})
            self._log(f"[{self.node_id}] 广播提案: {data}")
            self.goto("PREVOTE")

    def on_proposal(self, msg):
        """收到提案"""
        with self._lock:
            if self.step not in ("NEW_ROUND", "PROPOSAL"):
                return None
            if msg["proposer"] != self.proposer:
                return None
            self.proposal = msg
            self._log(f"[{self.node_id}] 收到提案: {msg['data']}")
            self.goto("PREVOTE")

    def on_prevote(self, msg):
        """收到 Prevote 投票"""
        with self._lock:
            self.add_prevote(msg["voter"], msg["vote"])

    def on_precommit(self, msg):
        """收到 Precommit 投票"""
        with self._lock:
            self.add_precommit(msg["voter"], msg["vote"])

    # ==================== 3. PREVOTE ====================

    def enter_prevote(self):
        """锁定规则: proposal > locked > nil"""
        proposal = self.proposal or self.locked_block
        vote = proposal["data"] if proposal else None
        self.on_broadcast({
            "type": "PREVOTE",
            "height": self.height, "round": self.round,
            "voter": self.node_id, "vote": vote,
        })
        self._log(f"[{self.node_id}] {self.height}:{self.round} Prevote  -> {vote or 'nil'}")

    def add_prevote(self, voter, vote):
        self.prevotes[voter] = vote
        if self._has_majority(self.prevotes):
            self._log(f"[{self.node_id}] Prevote 达成 >2/3")
            self.goto("PRECOMMIT")

    # ==================== 4. PRECOMMIT ====================

    def enter_precommit(self):
        if self.proposal:
            self.locked_block = self.proposal   # 锁定
        proposal = self.proposal or self.locked_block
        vote = proposal["data"] if proposal else None
        self.on_broadcast({
            "type": "PRECOMMIT",
            "height": self.height, "round": self.round,
            "voter": self.node_id, "vote": vote,
        })
        lock = " [锁定]" if self.locked_block else ""
        self._log(f"[{self.node_id}] {self.height}:{self.round} Precommit -> {vote or 'nil'}{lock}")

    def add_precommit(self, voter, vote):
        self.precommits[voter] = vote
        if self._has_majority(self.precommits):
            self._log(f"[{self.node_id}] Precommit 达成 >2/3")
            self.goto("COMMIT")

    # ==================== 5. COMMIT ====================

    def enter_commit(self):
        self._log(f"[{self.node_id}] {self.height}:{self.round} COMMIT 区块上链")
        self.on_commit(self.proposal)
        self.height += 1
        self.round = 0
        self.locked_block = None

    def next_round(self):
        """启动下一轮共识（外部调用）"""
        with self._lock:
            self.goto("NEW_ROUND")

    # ==================== 超时 ====================

    def timeout(self):
        with self._lock:
            if self._stopped:
                return
            self._log(f"[{self.node_id}] 超时! h{self.height} r{self.round} step={self.step} -> r{self.round + 1}")
            self.round += 1
            self.goto("NEW_ROUND")

    # ==================== 投票判定 ====================

    def _has_majority(self, votes):
        counts = {}
        for v in votes.values():
            counts[v] = counts.get(v, 0) + 1
        return max(counts.values()) >= self.threshold
