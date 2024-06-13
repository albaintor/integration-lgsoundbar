import asyncio
import struct
import sys

from Crypto.Cipher import AES

iv = b'\'%^Ur7gy$~t+f)%@'
key = b'T^&*J%^7tr~4^%^&I(o%^!jIJ__+a0 k'

def decrypt_packet(data):
    cipher = AES.new(key, AES.MODE_CBC, iv)
    decrypt = cipher.decrypt(data)
    padding = decrypt[-1:]
    decrypt = decrypt[:-ord(padding)]
    return str(decrypt, 'utf-8')

def unpack_packet(data: bytes):
    if data[0] == 0x10:
        length = data[1:5]
        print(str(length))
        # data = self.socket.recv(4)
        length = struct.unpack(">I", length)[0]
        data = data[5:(6+length)]
        print("Length : " + str(int(length)))
        if len(data) % 16 != 0:
            print("Error")
            return
        response = decrypt_packet(data)
        if response is not None:
            print(response)

async def main():
    chain = sys.argv[1]
    # byte_chain = bytes.fromhex(chain[10:])
    # result = decrypt_packet(byte_chain)
    # print(result)

    byte_chain = bytes.fromhex(chain)
    unpack_packet(byte_chain)



if __name__ == "__main__":
    asyncio.run(main())