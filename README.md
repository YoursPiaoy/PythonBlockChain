# 基于 Python 的区块链系统

基于中国国家密码标准（SM2/SM3）构建的区块链演示系统，包含区块管理、链完整性校验、持久化存储及交互式命令行工具。内置国际贸易报关单数据模型，可作为交易内容上链。

## 项目结构

| 文件 | 说明 |
| --- | --- |
| [ShangMi.py](ShangMi.py) | 国密算法封装（SM3 哈希、SM2 密钥生成/加解密/签名验签） |
| [BlockBuild.py](BlockBuild.py) | 区块数据结构定义（`Block` 类） |
| [ChainBuild.py](ChainBuild.py) | 区块链核心逻辑：独立函数（`add_block` / `validate` / `save`）+ `BlockChain` 类（创建、加载、索引、切片、迭代、成员判断） |
| [CustomsDeclaration.py](CustomsDeclaration.py) | 报关单数据模型（dataclass），格式化为标准报关单字符串，可直接作为交易内容上链 |
| [run.py](run.py) | 交互式 CLI 主程序，含 `AutoBlockChain`（自动保存/重载） |

## 功能特性

- **SM3 哈希** — 区块指纹生成，确保数据不可篡改
- **SM2 国密算法** — 非对称加密、数字签名与验签
- **区块链核心** — 创世区块、区块追加、链式哈希校验
- **序列协议支持** — 索引/切片访问、`len()`、`for` 迭代、反向迭代、`in` 成员判断、`append`/`pop`/`del`
- **数据持久化** — 整条链存储为 JSON 文件，支持加载与重载
- **篡改检测** — 修改已有区块内容后校验失败
- **交互式菜单** — 查看链、新增交易、校验完整性、自动保存
- **AutoBlockChain** — 自动保存；校验前自动从磁盘重载
- **报关单模型** — 标准化的国际贸易报关数据结构，可直接作为交易内容上链

## 快速开始

```bash
# 安装依赖
pip install gmssl

# 运行交互式 CLI
python run.py

# 或直接使用 API
python -c "from ChainBuild import *; chain = BlockChain(); print(chain)"
```

## 依赖

- Python 3.10+
- `gmssl` — 国密算法库

## API 使用示例

### 创建区块链与添加区块

```python
from ChainBuild import BlockChain, add_block, validate, save

# 创建区块链（自动包含创世区块）
chain = BlockChain()

# 添加交易区块
add_block("小明向小红转账 100 元", chain)
add_block("小红向小刚转账 50 元", chain)

# 校验链完整性
validate(chain)   # 输出: [校验通过]

# 保存到文件
save(chain)

# 从文件加载
loaded = BlockChain.load()
```

### 查看区块信息

```python
chain = BlockChain()

print(len(chain))       # 区块总数（含创世区块）
print(chain[0])         # 按索引访问区块
print(chain[1:3])       # 切片访问
print(chain)            # 打印整条链

# 迭代、成员判断等序列协议支持
for block in chain:
    print(block)

for block in reversed(chain):
    print(block)

chain.append(new_block)  # 追加区块
chain.pop()              # 弹出末尾区块
del chain[0]             # 删除指定区块
print(block in chain)    # 成员判断
```

### 使用 AutoBlockChain（自动保存）

```python
from run import AutoBlockChain

chain = AutoBlockChain()
chain.add_block("一笔交易")   # 自动保存到 JSON 文件
chain.validate()              # 自动从磁盘重载后校验
```

### 报关单作为交易内容

```python
from CustomsDeclaration import CustomsDeclaration
from ChainBuild import BlockChain, add_block

dec = CustomsDeclaration(
    seller_name_address="ABC Corp, Shanghai, China",
    buyer_name_address="XYZ Ltd, New York, USA",
    goods_description="LED Lighting Fixtures",
    hs_code="940542",
    quantity=500,
    unit="pieces",
    unit_price=12.50,
    total_amount=6250.00,
    currency="USD",
    incoterms="CIF",
)

# 将报关单格式化为字符串上链
chain = BlockChain()
add_block(dec.to_str(), chain)

# 直接打印报关单查看
print(dec)
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

## CLI 交互菜单

运行 `python run.py` 后进入交互式菜单：

```text
============================================================
              基于Python的区块链系统
============================================================

主菜单
  1. 查看整条链
  2. 新增区块（输入交易内容上链）
  3. 校验完整性（自动从数据库重载后校验）
  0. 退出（自动保存）
```

启动时会自动尝试加载已有数据库文件（`./BlockChainDatabase/chain.json`），未找到时引导创建新区块链或从指定路径加载。
