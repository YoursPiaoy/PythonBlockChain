#SM3 哈希算法工具函数使用 gmssl 库计算 SM3 哈希值
from gmssl.sm3 import sm3_hash

def sm3_hash_string(input_str: str) -> str:
    """
    计算输入字符串的 SM3 哈希值
    input_str: 待计算哈希的输入字符串
    """
    # 将字符串编码为 UTF-8 字节序列，再转为整数列表
    data_list = list(input_str.encode("utf-8"))

    # 调用 gmssl 库计算 SM3 哈希值（返回十六进制字符串）
    hash_value = sm3_hash(data_list)

    return hash_value

# 使用示例
if __name__ == "__main__":
    text = '1'
    result = sm3_hash_string(text)
    print(f"输入: {text}")
    print(f"SM3: {result}")
    print(f"长度: {len(result)} 位十六进制字符")
