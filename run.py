from ChainBuild import BlockChain,add_block,validate,save
from pathlib import Path

data_path: Path = Path("BlockChainDatabase/chain.json")
loading_chain: BlockChain | None = None

def help():
    print(f"""> help\t\t\t\t显示帮助
> load \t\t\t\t加载区块链数据库
> save \t\t\t\t保存区块链到数据库
> add  <交易内容>\t\t创建区块并上链
> create \t\t\t创建新区块链
> list\t\t\t\t打印当前加载区块链
> validate\t\t\t\t检验当前加载区块链的完整性
> pwd\t\t\t\t打印当前区块链文件所在路径
> setpath <文件路径>\t\t加载区块链文件所在路径\n\t\t\t\t默认为{data_path}
> exit\t\t\t\t退出程序""")

def setpath(path: str | Path = data_path):
    global data_path
    data_path = Path(path)
    print(f"已设置文件路径为{data_path}")

def load():
    global loading_chain
    loading_chain = BlockChain.load(data_path)

def sv():
    if loading_chain is None:
        print("请先加载或创建区块链")
        return
    save(loading_chain, data_path)

def add(content):
    if not content:
        print("交易内容不能为空")
        return
    if loading_chain is None:
        print("请先加载或创建区块链")
        return
    add_block(content, loading_chain)
    print("区块已添加")

def create():
    global loading_chain
    loading_chain = BlockChain()

def ls():
    if loading_chain is None:
        print("请先加载或创建区块链")
        return
    print(loading_chain)

def vld():
    if loading_chain is None:
        print("请先加载或创建区块链")
        return
    validate(loading_chain)

def pwd():
    print(data_path)

def main():
    cmd = input(f"{data_path}>").strip().lower().split()
    if not cmd:
        return
    order = cmd[0]
    argv = cmd[1:]
    order_dict: dict = {
        "setpath": setpath,
        "load": load,
        "save": sv,
        "add": add,
        "create": create,
        "list": ls,
        "validate": vld,
        "pwd": pwd,
        "exit": exit,
        "help": help,
    }
    try:
        order_dict[order](*argv)
    except KeyError:
        print(f"没有 {order} 命令，请重新输入。")
    except TypeError:
        print(f"{order} 命令参数错误，请检查参数数量。")

        
if __name__ == "__main__":
    help()
    while True:
        main()
