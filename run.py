from ChainBuild import BlockChain, Block, add_block, validate, save
from BlockBuild import create_genesis_block
import os


class AutoBlockChain(BlockChain):
    """自动保存的区块链：
    - add_block() 后自动保存到数据库
    - validate() 前自动从数据库重载
    """

    def __init__(self, blocks=None, db_path="./BlockChainDatabase/chain.json"):
        if blocks is None:
            blocks = [create_genesis_block()]
        super().__init__(blocks)
        self.db_path = db_path

    def add_block(self, transaction_content: str) -> Block:
        block = add_block(transaction_content, self.blocks)
        save(self.blocks, self.db_path)
        print("  >> 已自动保存到数据库")
        return block

    def validate(self) -> bool:
        loaded = BlockChain.load(self.db_path)
        if loaded is not None:
            self.blocks = loaded.blocks
            print("  >> 已从数据库重新加载，基于磁盘数据进行校验")
        return validate(self.blocks)


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def pause():
    input("按 Enter 返回...")
    clear()


def banner():
    print("=" * 60)
    print("              基于Python的区块链系统")
    print("=" * 60)


def main():
    clear()
    banner()

    db_path = "./BlockChainDatabase/chain.json"
    chain = None

    # 启动时尝试加载已有数据库
    loaded = BlockChain.load(db_path)
    if loaded is None:
        print("\n未找到区块链数据文件。")
        while True:
            gen_choice = input("\n是否生成新的区块链文件？(y/n): ").strip().lower()
            if gen_choice == "y":
                path_input = input("请输入保存路径（直接回车使用默认路径./BlockChainDatabase/chain.json）: ").strip()
                if path_input:
                    db_path = path_input
                print(f"\n正在创建新区块链（含创世区块），保存至: {db_path}")
                chain = AutoBlockChain(db_path=db_path)
                save(chain.blocks, chain.db_path)
                break
            elif gen_choice == "n":
                while True:
                    load_choice = input("\n是否从其他地址加载区块链文件？(y/n): ").strip().lower()
                    if load_choice == "y":
                        load_path = input("请输入文件路径: ").strip()
                        if not load_path:
                            print("路径不能为空。")
                            continue
                        loaded = BlockChain.load(load_path)
                        if loaded is not None:
                            db_path = load_path
                            chain = AutoBlockChain(blocks=loaded.blocks, db_path=db_path)
                            break
                        else:
                            print("文件不存在或格式错误，请重新输入。")
                    elif load_choice == "n":
                        print("退出程序。")
                        return
                    else:
                        print("无效输入，请输入 y 或 n。")
                break  # 选择加载后退出外层循环
            else:
                print("无效输入，请输入 y 或 n。")
    else:
        chain = AutoBlockChain(blocks=loaded.blocks, db_path=db_path)
        print(f"\n已加载数据库，当前共 {len(chain)} 个区块")

    while True:
        print("\n" + "─" * 60)
        print("主菜单")
        print("  1. 查看整条链")
        print("  2. 新增区块（输入交易内容上链）")
        print("  3. 校验完整性（自动从数据库重载后校验）")
        print("  0. 退出（自动保存）")
        print("─" * 60)

        choice = input("请选择: ").strip()

        if choice == "1":
            clear()
            banner()
            print(f"\n当前链长: {len(chain)} 个区块\n")
            for i, block in enumerate(chain.blocks):
                print(f"--- 区块 {i} ---")
                print(block)
            pause()

        elif choice == "2":
            clear()
            banner()
            tx_content = input("\n请输入交易内容: ").strip()
            if not tx_content:
                print("交易内容不能为空！")
                pause()
                continue

            block = chain.add_block(tx_content)
            print(f"\n上链成功！区块索引: {block.index}")
            pause()

        elif choice == "3":
            clear()
            banner()
            print("\n正在从数据库重载并校验...\n")
            valid = chain.validate()
            print()
            if valid:
                print("校验通过 —— 区块链完整，未被篡改")
            else:
                print("校验失败 —— 数据已被篡改或链不完整")
            pause()

        elif choice == "0":
            save(chain.blocks, chain.db_path)
            print("数据已保存！")
            break


if __name__ == "__main__":
    main()
