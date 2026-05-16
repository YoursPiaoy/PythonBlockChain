# 基于 Python 的区块链系统

基于中国国家密码标准（SM2/SM3）构建的区块链演示系统，包含区块管理、链完整性校验、持久化存储及交互式命令行工具。

## 项目结构

| 文件 | 说明 |
| --- | --- |
| [ShangMi.py](ShangMi.py) | 国密算法封装（SM3 哈希、SM2 密钥生成/加解密/签名验签） |
| [BlockBuild.py](BlockBuild.py) | 区块数据结构定义 |
| [ChainBuild.py](ChainBuild.py) | 区块链核心逻辑（添加区块、完整性校验、JSON 持久化） |
| [CustomsDeclaration.py](CustomsDeclaration.py) | 报关单数据模型，可用于区块链交易内容 |
| [run.py](run.py) | 交互式 CLI 主程序 |

## 功能特性

- **SM3 哈希** — 区块指纹生成，确保数据不可篡改
- **SM2 国密算法** — 非对称加密、数字签名与验签
- **区块链核心** — 创世区块、区块追加、链式哈希校验
- **数据持久化** — 将整条链存储为 JSON 文件，支持加载与重载
- **篡改检测** — 修改已有区块内容后校验失败
- **交互式菜单** — 查看链、新增交易、校验完整性
- **报关单模型** — 标准化的国际贸易报关数据结构，可直接作为交易内容上链

## 快速开始

```bash
# 运行交互式 CLI
python run.py

# 运行区块链演示
python ChainBuild.py
```

## 依赖

- Python 3.10+
- `gmssl` — 国密算法库

```bash
pip install gmssl
```

## 使用示例

```python
from ChainBuild import BlockChain

# 创建区块链（自动包含创世区块）
chain = BlockChain()

# 添加交易区块
chain.add_block("小明向小红转账 100 元")
chain.add_block("小红向小刚转账 50 元")

# 校验链完整性
chain.validate()               # 输出: [校验通过]

# 保存到文件
chain.save_chain()

# 从文件加载
loaded = BlockChain.load()
```

## 国密算法使用

```python
from ShangMi import *

# SM3 哈希
hash_val = sm3_hash_string("Hello")

# SM2 密钥对生成
pri, pub = sm2_generate_keypair()

# SM2 加解密
enc = sm2_encrypt(pub, "Hello")
dec = sm2_decrypt(pri, pub, enc)

# SM2 签名验签
sig = sm2_sign_hash(pri, hash_val)
ok = sm2_verify_hash(pub, hash_val, sig)
```
