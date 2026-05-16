import json
import time
from pathlib import Path
from datetime import datetime
from BlockBuild import Block

def add_block(transaction_content: str, blocks_chain:list[Block]) -> Block: 
    """ 添加新区快
        transaction_content: 新区快的交易内容"""
    previous_block = blocks_chain[-1]
    new_block = Block(
        index=str(len(blocks_chain)),
        previous_block_hash=previous_block.self_hash,
        transaction_content=transaction_content,
        timestamp=time.time(),
    )
    blocks_chain.append(new_block)
    return new_block


def validate(blocks_chain:list[Block]) -> bool:
    """遍历整条链，校验每个区块的哈希链是否完整。"""
    try:
        for i, block in enumerate(blocks_chain):
            if block.self_hash != block.get_self_hash():
                print(f"[校验失败] 区块 {i} 自身哈希不匹配")
                return False
            if i > 0 and block.previous_block_hash != blocks_chain[i - 1].self_hash:
                print(f"[校验失败] 区块 {i} 的 previous_hash 不指向区块 {i - 1}")
                return False
        print("[校验通过] 整条链完整")
        return True
    except Exception as e:
        print(f"[校验异常] {e}")
        return False
    
def save(blocks_chain : list[Block], path: str | Path = "./BlockChainDatabase/chain.json") -> None:
    """将整条链保存为 JSON 文件。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [
        {
            "index": block.index,
            "previous_block_hash": block.previous_block_hash,
            "transaction_content": block.transaction_content,
            "timestamp": block.timestamp,
            "timestamp_readable": datetime.fromtimestamp(block.timestamp).strftime("%Y-%m-%d %H:%M:%S"),
            "self_hash": block.self_hash,
        }
        for block in blocks_chain
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[保存] 共 {len(blocks_chain)} 个区块 -> {path}")

class BlockChain:
    def __init__(self, blocks: list[Block] | None = None):
        self.blocks = blocks if blocks is not None else [Block.create_genesis_block()]
        
    @classmethod
    def load(cls, path: str | Path = "./BlockChainDatabase/chain.json") -> "BlockChain | None":
        """从 JSON 文件加载整条链。"""
        try:
            with open(path, "r", encoding="utf-8") as datafile:
                data = json.load(datafile)
        except FileNotFoundError:
            print("文件不存在，请确认数据库路径或是否存在数据库文件")
            return None
        blocks = []
        for item in data:
            block = Block(
                index=item["index"],
                previous_block_hash=item["previous_block_hash"],
                transaction_content=item["transaction_content"],
                timestamp=item["timestamp"],
            )
            block.self_hash = item["self_hash"]
            blocks.append(block)
        print(f"[加载] 从 {path} 读取 {len(blocks)} 个区块")
        return cls(blocks)

    def __getitem__(self, index: int) -> Block:
        return self.blocks[index]

    def __len__(self) -> int:
        return len(self.blocks)

    def __str__(self) -> str:
        return "\n".join(str(b) for b in self.blocks)


if __name__ == "__main__":
    # ========== 冒烟测试 ==========
    print("=" * 60)
    print("冒烟测试：ChainBuild.py")
    print("=" * 60)

    # 1. 创建区块链（含创世区块）
    chain = BlockChain()
    print(f"\n[1] 创建区块链，长度 = {len(chain)}")
    assert len(chain) == 1, "创世区块未正确创建"
    assert chain[0].index == "0", "创世区块索引应为 0"
    print("    [OK] 创世区块创建成功")

    # 2. 用 add_block() 添加区块
    b1 = add_block("第一笔交易：小明 -> 小红 10 BTC", chain.blocks)
    b2 = add_block("第二笔交易：小红 -> 小刚 5 BTC", chain.blocks)
    print(f"[2] 添加 2 个区块后，长度 = {len(chain)}")
    assert len(chain) == 3, "应包含创世区块 + 2 个新区块"
    assert b1.previous_block_hash == chain[0].self_hash, "区块 1 应指向创世区块"
    assert b2.previous_block_hash == chain[1].self_hash, "区块 2 应指向区块 1"
    print("    [OK] 区块添加成功，哈希链完整")

    # 3. 校验
    print(f"[3] 校验整条链 …… ", end="")
    assert validate(chain.blocks) is True
    print("    [OK] 校验通过")

    # 4. 篡改检测
    print(f"[4] 篡改检测 …… ", end="")
    chain.blocks[1].transaction_content = "篡改内容"
    assert validate(chain.blocks) is False
    print("    [OK] 篡改后被正确检测")

    # 5. 保存 & 加载
    test_path = "./BlockChainDatabase/test_chain.json"
    save(chain.blocks, test_path)
    loaded = BlockChain.load(test_path)
    assert loaded is not None, "加载失败"
    assert len(loaded) == len(chain)
    print(f"[5] 保存 & 加载：{len(loaded)} 个区块，哈希完整")

    # 6. 加载后的链再次校验
    assert validate(loaded.blocks) is False, "篡改后的链加载后仍应校验失败"
    print("    [OK] 保存 / 加载功能正常")

    # 7. __str__
    print(f"[6] __str__ 输出：")
    for b in chain:
        print(f"  --- 区块 {b.index} ---")
        for line in str(b).split("\n"):
            print(f"  {line}")

    # 清理测试文件
    import os
    if os.path.exists(test_path):
        os.remove(test_path)

    print("\n" + "=" * 60)
    print("所有冒烟测试通过！")
    print("=" * 60)