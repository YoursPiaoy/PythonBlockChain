import base64
from gmssl.sm3 import sm3_hash
from gmssl.sm2 import CryptSM2, default_ecc_table
from gmssl import func


def sm3_hash_string(input_str: str) -> str: 
    """输入字符串转化为哈希值"""
    data_list = list(input_str.encode("utf-8"))
    return sm3_hash(data_list)


def sm2_generate_keypair() -> tuple:
    """
    生成 SM2 密钥对
    :return: (私钥 hex, 公钥 hex)  公钥为 x+y 拼接，不含 04 前缀，共 128 hex 字符
    """
    para_len = len(default_ecc_table['n'])
    private_key = func.random_hex(para_len)
    # gmssl 未提供公开的公钥派生 API，通过私钥×基点 G 计算公钥
    sm2 = CryptSM2(private_key=private_key, public_key="")
    try:
        public_key = sm2._kg(int(private_key, 16), default_ecc_table['g'])
    except AttributeError:
        raise RuntimeError("gmssl 版本不兼容，请联系维护者") from None
    return private_key, public_key


def sm2_encrypt(public_key: str, plaintext: str) -> str:
    """
    SM2 加密
    :param public_key: 公钥 hex 字符串（x+y，不含 04 前缀，共 128 hex 字符）
    :param plaintext:  明文字符串
    :return:          base64 编码的密文
    """
    sm2 = CryptSM2(private_key="", public_key=public_key)
    cipher_bytes = sm2.encrypt(plaintext.encode("utf-8"))
    return base64.b64encode(cipher_bytes).decode("utf-8")


def sm2_decrypt(private_key: str, public_key: str, ciphertext: str) -> str:
    """
    SM2 解密
    :param private_key: 私钥 hex 字符串
    :param public_key:  公钥 hex 字符串（x+y，不含 04 前缀）
    :param ciphertext:  base64 编码的密文
    :return:           明文字符串
    """
    sm2 = CryptSM2(private_key=private_key, public_key=public_key)
    plain_bytes = sm2.decrypt(base64.b64decode(ciphertext))
    return plain_bytes.decode("utf-8")


def sm2_sign_hash(private_key: str, hash_hex: str) -> str:
    """
    SM2 使用私钥对哈希值签名（直接对哈希值签名，不经过 SM3 摘要）
    :param private_key: 私钥 hex 字符串
    :param hash_hex:    待签名的哈希值 hex 字符串
    :return:            签名 hex 字符串（r||s 拼接）
    """
    sm2 = CryptSM2(private_key=private_key, public_key="")
    random_hex = func.random_hex(len(private_key))
    return sm2.sign(bytes.fromhex(hash_hex), random_hex)


def sm2_verify_hash(public_key: str, hash_hex: str, signature: str) -> bool:
    """
    SM2 使用公钥验证哈希值的签名
    :param public_key: 公钥 hex 字符串（x+y，不含 04 前缀）
    :param hash_hex:   被签名的哈希值 hex 字符串
    :param signature:  签名 hex 字符串（r||s 拼接）
    :return:           True 验证通过，False 验证失败
    """
    sm2 = CryptSM2(private_key="", public_key=public_key)
    try:
        return sm2.verify(signature, bytes.fromhex(hash_hex))
    except (ValueError, TypeError) as e:
        print(f"[SM2] 签名验证异常: {e}")
        return False


if __name__ == "__main__":
    # SM3 示例
    print(f"SM3('a') = {sm3_hash_string('a')}")

    # SM2 加解密示例
    pri, pub = sm2_generate_keypair()
    print(f"私钥: {pri}")
    print(f"公钥: {pub}")

    msg = "Hello, SM2!"
    enc = sm2_encrypt(pub, msg)
    print(f"加密: {enc}")

    dec = sm2_decrypt(pri, pub, enc)
    print(f"解密: {dec}")

    # SM2 哈希签名示例
    hash_val = sm3_hash_string("Hello, SM2 Signature!")
    print(f"\n哈希值: {hash_val}")
    sig = sm2_sign_hash(pri, hash_val)
    print(f"签名:   {sig}")
    ok = sm2_verify_hash(pub, hash_val, sig)
    print(f"验证:   {'通过' if ok else '失败'}")
