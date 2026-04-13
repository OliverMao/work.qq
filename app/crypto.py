import base64
import hashlib
import socket
import struct
import time
from typing import Optional, Tuple

from Crypto.Cipher import AES


class WecomCrypto:
    def __init__(self, token: str, encoding_aes_key: str, corp_id: str):
        self.token = token
        self.encoding_aes_key = encoding_aes_key
        self.corp_id = corp_id
        self.aes_key = base64.b64decode(encoding_aes_key + "=")

    @staticmethod
    def _get_host_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = "127.0.0.1"
        finally:
            s.close()
        return ip

    def verify_signature(
        self, timestamp: str, nonce: str, echostr: str, msg_signature: str
    ) -> bool:
        sign_list = [self.token, timestamp, nonce, echostr]
        sign_list.sort()
        sign_str = "".join(sign_list)
        computed_signature = hashlib.sha1(sign_str.encode("utf-8")).hexdigest()
        return computed_signature == msg_signature

    def decrypt_echostr(self, echostr: str) -> str:
        cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_key[:16])
        decrypted = cipher.decrypt(base64.b64decode(echostr))
        content = self._unpad(decrypted)
        xml_len = struct.unpack(">I", content[16:20])[0]
        msg = content[20 : 20 + xml_len].decode("utf-8")
        return msg

    def verify_msg_signature(
        self, msg_signature: str, timestamp: str, nonce: str, encrypt_msg: str
    ) -> bool:
        sign_list = [self.token, timestamp, nonce, encrypt_msg]
        sign_list.sort()
        sign_str = "".join(sign_list)
        computed_signature = hashlib.sha1(sign_str.encode("utf-8")).hexdigest()
        return computed_signature == msg_signature

    def decrypt_message(self, encrypted_msg: str) -> Tuple[str, str, str, str]:
        cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_key[:16])
        decrypted = cipher.decrypt(base64.b64decode(encrypted_msg))
        content = self._unpad(decrypted)
        xml_len = struct.unpack(">I", content[16:20])[0]
        msg = content[20 : 20 + xml_len].decode("utf-8")
        receive_id = content[20 + xml_len :].decode("utf-8")
        return msg, receive_id, content[:16].hex(), str(xml_len)

    def encrypt_message(
        self,
        reply_msg: str,
        timestamp: Optional[str] = None,
        nonce: Optional[str] = None,
    ) -> str:
        timestamp = timestamp or str(int(time.time()))
        nonce = nonce or self._generate_random_string(16)
        msg_encrypt = self._encrypt_content(reply_msg)
        signature = self._generate_signature(self.token, timestamp, nonce, msg_encrypt)
        response_xml = (
            f"<xml>\n"
            f"   <Encrypt><![CDATA[{msg_encrypt}]]></Encrypt>\n"
            f"   <MsgSignature><![CDATA[{signature}]]></MsgSignature>\n"
            f"   <TimeStamp>{timestamp}</TimeStamp>\n"
            f"   <Nonce><![CDATA[{nonce}]]></Nonce>\n"
            f"</xml>"
        )
        return response_xml

    def _encrypt_content(self, msg: str) -> str:
        msg_bytes = msg.encode("utf-8")
        msg_len = struct.pack(">I", len(msg_bytes))
        random_bytes = self._generate_random_bytes(16)
        pad = self._pad(msg_bytes)
        content = (
            random_bytes + msg_len + msg_bytes + pad + self.corp_id.encode("utf-8")
        )
        cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_key[:16])
        encrypted = cipher.encrypt(content)
        return base64.b64encode(encrypted).decode("utf-8")

    def _generate_signature(
        self, token: str, timestamp: str, nonce: str, encrypt_msg: str
    ) -> str:
        sign_list = [token, timestamp, nonce, encrypt_msg]
        sign_list.sort()
        sign_str = "".join(sign_list)
        return hashlib.sha1(sign_str.encode("utf-8")).hexdigest()

    def _pad(self, data: bytes) -> bytes:
        block_size = 32
        padding_length = block_size - (len(data) % block_size)
        return bytes([padding_length] * padding_length)

    def _unpad(self, data: bytes) -> bytes:
        pad_len = data[-1]
        return data[:-pad_len]

    @staticmethod
    def _generate_random_string(length: int) -> str:
        import random
        import string

        return "".join(random.choices(string.ascii_letters + string.digits, k=length))

    @staticmethod
    def _generate_random_bytes(length: int) -> bytes:
        import os

        return os.urandom(length)
