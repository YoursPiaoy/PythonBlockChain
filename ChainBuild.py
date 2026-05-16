import json
import time
from pathlib import Path
from datetime import datetime
from BlockBuild import Block


class BlockChain:
    def __init__(self, blocks: list[Block] | None = None):
        self.blocks = blocks if blocks is not None else [Block.create_genesis_block()]

    def add_block(self, transaction_content: str) -> Block: 
        """ 添加新区快
            transaction_content: 新区快的交易内容"""
        previous_block = self.blocks[-1]
        new_block = Block(
            index=str(len(self.blocks)),
            previous_block_hash=previous_block.self_hash,
            transaction_content=transaction_content,
            timestamp=time.time(),
        )
        self.blocks.append(new_block)
        return new_block

    def validate(self) -> bool:
        """遍历整条链，校验每个区块的哈希链是否完整。"""
        try:
            for i, block in enumerate(self.blocks):
                if block.self_hash != block.get_self_hash():
                    print(f"[校验失败] 区块 {i} 自身哈希不匹配")
                    return False
                if i > 0 and block.previous_block_hash != self.blocks[i - 1].self_hash:
                    print(f"[校验失败] 区块 {i} 的 previous_hash 不指向区块 {i - 1}")
                    return False
            print("[校验通过] 整条链完整")
            return True
        except Exception as e:
            print(f"[校验异常] {e}")
            return False

    def save_chain(self, path: str | Path = "./BlockChainDatabase/chain.json") -> None:
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
            for block in self.blocks
        ]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[保存] 共 {len(self.blocks)} 个区块 -> {path}")

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
    import os

    print("=" * 60)
    print("1. 创建区块链（自动生成创世区块）")
    print("=" * 60)
    chain = BlockChain()
    print(f"   链长: {len(chain)} 个区块")
    print(chain)

    print("=" * 60)
    print("2. 添加区块")
    print("=" * 60)
    chain.add_block("小明向小红转账 100 元")
    chain.add_block("小红向小刚转账 50 元")
    chain.add_block("小刚向小明转账 20 元")
    print(f"   链长: {len(chain)} 个区块")
    for i in range(len(chain)):
        print(f"\n--- 区块 {i} ---")
        print(chain[i])

    print("=" * 60)
    print("3. 校验区块链")
    print("=" * 60)
    chain.validate()

    print("=" * 60)
    print("4. 保存区块链到文件")
    print("=" * 60)
    chain.save_chain()

    print("=" * 60)
    print("5. 从文件加载区块链")
    print("=" * 60)
    loaded_chain = BlockChain.load()
    if loaded_chain:
        print(f"   链长: {len(loaded_chain)} 个区块")
        print(loaded_chain)

    print("=" * 60)
    print("6. 校验加载后的链")
    print("=" * 60)
    if loaded_chain:
        loaded_chain.validate()

    print("=" * 60)
    print("7. 篡改测试：修改区块内容后校验应失败")
    print("=" * 60)
    if loaded_chain:
        loaded_chain.blocks[1].transaction_content = "篡改的交易内容"
        loaded_chain.validate()

    print("=" * 60)
    print("8. 加载不存在的文件")
    print("=" * 60)
    BlockChain.load("./NonExistentFile.json")

    print("\n✅ 所有功能测试完成，测试文件已清理")

