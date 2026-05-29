from ShangMi import *
import time
from datetime import datetime
from CustomsDeclaration import CustomsDeclaration

def create_genesis_block():
    """生成创世区块"""
    return Block('0','0'*64, "This is the genesis block")


class Block:
    def __init__(self, index: str, 
                 previous_block_hash: str, 
                 transaction_content: str, 
                 timestamp: float = time.time()
                 ): # 初始化参数
        
        self.index = index
        self.previous_block_hash = previous_block_hash
        self.transaction_content = transaction_content
        self.timestamp = timestamp
        self.self_hash = self.get_self_hash()
    
    def get_self_hash(self): 
        """生成当前对象哈希"""
        pending_string = (self.previous_block_hash + #前区块哈希
                          self.index +  #区块序号
                          self.transaction_content + #交易内容
                          str(self.timestamp) # 时间戳
                          )
        
        return sm3_hash_string(pending_string)
    
    def __str__(self):
        readable_time = datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        return (f"index = \t{self.index},\n"
                f"prev_hash = \t{self.previous_block_hash},\n"
                f"content = \t{self.transaction_content},\n"
                f"self_hash = \t{self.self_hash},\n"
                f"timestamp = \t{readable_time}\n")
    
if __name__ == '__main__':
    print(create_genesis_block())