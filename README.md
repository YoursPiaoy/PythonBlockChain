# Python 区块链 — TBFT 共识网络

基于国密算法（SM2/SM3）的多节点区块链系统，实现 TBFT（可信拜占庭容错）五阶段共识协议、P2P 网络通信、SM2 端到端加密和链同步机制。

## 项目结构

```text
├── requirements.txt
├── consensus/                     # 共识层
│   ├── ShangMi.py                 # SM3 哈希、SM2 密钥/加解密/签名验签
│   ├── BlockBuild.py              # 区块数据结构
│   ├── ChainBuild.py              # 区块链核心：增删、校验、持久化
│   ├── CustomsDeclaration.py      # 报关单交易数据模型
│   ├── ConsensusNetwork.py        # P2P 网络层：种子节点 + 共识节点基类
│   ├── TBFT.py                    # TBFT 五阶段状态机（含超时、POL、双投票检测）
│   ├── ConsensusEngine.py         # 共识引擎：桥接网络、状态机、链存储、加密
│   ├── generate_keys.py           # SM2 密钥对预生成工具
│   ├── start_nodes.py             # 生产节点启动脚本（单机/多机部署）
│   ├── test_client_integration.py # 集成测试
│   └── validators.json            # 验证者节点配置
├── client/                        # 客户端
│   ├── client.py                  # 交互式 CLI 客户端（SM2 加密通信）
│   └── validators.json            # 客户端节点配置
└── README.md
```

## 架构概览

```text
客户端 (client.py) ──SM2加密──▶ 共识节点 (ConsensusEngine)
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              TBFT 状态机     P2P 网络层      区块链存储
              (五阶段共识)   (SeekNode)      (ChainBuild)
```

- **3 个共识节点**运行 TBFT 协议，>2/3 投票达成共识后区块上链
- **种子节点**负责节点发现和 P2P 拓扑组织
- **客户端**通过 SM2 加密提交交易，验证签名回复

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 生成 SM2 密钥对（写入 validators.json 和各节点 key 文件）
python consensus/generate_keys.py

# 3. 启动共识网络
python consensus/start_nodes.py --with-seed

# 4. 新终端，启动客户端提交交易
python client/client.py
```

## TBFT 共识协议

五阶段状态机：`NEW_ROUND → PROPOSAL → PREVOTE → PRECOMMIT → COMMIT`

| 特性 | 说明 |
| --- | --- |
| 提议者轮换 | `(height + round) % len(validators)` |
| 投票阈值 | >2/3 多数（排除 nil 投票） |
| Proof-of-Lock | 仅当 >2/3 prevote 对同一非 nil 区块时才锁定 |
| 双投票检测 | 同高度/轮次发送冲突投票时记录告警 |
| 超时推进 | 每阶段独立超时，自动进入下一轮 |
| 消息认证 | 共识消息附加 SM2 签名，接收端验签 |

## 安全特性

- **SM2 端到端加密**：客户端用节点公钥加密交易内容，节点用客户端公钥加密回复
- **SM2 签名**：客户端签名交易，节点签名回复，接收端验证签名者身份
- **P2P 消息认证**：PREVOTE/PRECOMMIT/PROPOSAL 消息附带 SM2 签名
- **链完整性校验**：启动时自动验证本地链，校验失败则备份损坏文件并从创世块重建
- **同步区块校验**：同步过程中逐块验证哈希和链接，异常时回滚
- **分叉检测**：同步时比较同高度区块哈希，不一致则告警

## 链同步

节点启动后自动通过 P2P 网络同步区块：

1. 连接建立时发送 `SYNC_HELLO`（高度 + 末块哈希）
2. 发现对端高度更高时发起 `SYNC_REQUEST`
3. 对端回复 `SYNC_RESPONSE` 包含缺失区块
4. 逐块验哈希和链接，整链校验通过后落盘
5. 校验失败则回滚到同步前状态

## 多机部署

```bash
# 种子机（含种子节点 + 本机共识节点）
python consensus/start_nodes.py --with-seed

# 其他机器（只启动本机共识节点，连接远端种子）
python consensus/start_nodes.py
```

配置在 `consensus/validators.json` 中，每台机器将本地节点标记 `"local": true`。

## 集成测试

```bash
python consensus/test_client_integration.py
```

启动种子 + 3 个共识节点 + 测试客户端，提交交易并验证所有节点链高度一致。

## API 示例

```python
from consensus.ChainBuild import BlockChain, add_block, validate, save
from consensus.BlockBuild import create_genesis_block

chain = BlockChain()
add_block("交易内容", chain)
validate(chain)         # → True
save(chain, "chain.json")
loaded = BlockChain.load("chain.json")
```

## 依赖

- Python 3.10+
- [gmssl](https://github.com/duanhongyi/gmssl) — SM2/SM3 国密算法
- [p2pnetwork](https://github.com/macsnoeren/python-p2p-network) — P2P 网络库
