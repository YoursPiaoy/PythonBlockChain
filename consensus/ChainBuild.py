from __future__ import annotations

import json
import time
from pathlib import Path
from datetime import datetime
from BlockBuild import Block, create_genesis_block

def add_block(transaction_content: str, blocks_chain: list[Block] | BlockChain,
              timestamp: float | None = None) -> Block:
    """添加新区块
       transaction_content: 新区块的交易内容
       timestamp: 可选时间戳，None 则使用当前时间"""
    previous_block = blocks_chain[-1]
    new_block = Block(
        index=str(len(blocks_chain)),
        previous_block_hash=previous_block.self_hash,
        transaction_content=transaction_content,
        timestamp=timestamp if timestamp is not None else time.time(),
    )
    blocks_chain.append(new_block)
    return new_block


def validate(blocks_chain: BlockChain) -> bool:
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
    

def save(blocks_chain: BlockChain, path: str | Path = "./BlockChainDatabase/chain.json") -> None:
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
        self.blocks = blocks if blocks is not None else [create_genesis_block()]
        
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
    
    #让对象支持索引操作（含切片）
    def __getitem__(self, index: int | slice) -> Block | list[Block]:
        return self.blocks[index]

    #支持返回链中区块的总数
    def __len__(self) -> int:
        return len(self.blocks)

    #显式迭代支持
    def __iter__(self):
        return iter(self.blocks)

    #反向迭代
    def __reversed__(self):
        return reversed(self.blocks)

    #in 操作符
    def __contains__(self, block: object) -> bool:
        return block in self.blocks

    #追加区块
    def append(self, block: Block) -> None:
        self.blocks.append(block)

    #弹出区块
    def pop(self, index: int = -1) -> Block:
        return self.blocks.pop(index)

    #del 语句支持
    def __delitem__(self, index: int | slice) -> None:
        del self.blocks[index]

    #支持规范输出
    def __str__(self) -> str:
        return "\n".join(str(b) for b in self.blocks)
