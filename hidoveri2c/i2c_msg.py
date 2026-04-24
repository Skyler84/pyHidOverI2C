
class i2c_msg:
    READ = 0x01
    WRITE = 0x00
    buf: list[int]
    len: int
    addr: int
    flags: int

    def __init__(self, addr, buf, len, flags):
        self.addr = addr
        self.buf = buf
        self.len = len
        self.flags = flags

    @staticmethod
    def read(addr, size):
        return i2c_msg(addr, [0]*size, size, i2c_msg.READ)
    
    @staticmethod
    def write(addr, data):
        return i2c_msg(addr, data, len(data), i2c_msg.WRITE)

    def __iter__(self):
        """ Iterator / Generator

        :return: iterates over :py:attr:`buf`
        :rtype: :py:class:`generator` which returns int values
        """
        idx = 0
        while idx < self.len:
            yield self.buf[idx]
            idx += 1

    def __len__(self):
        return self.len

    def __bytes__(self):
        return bytes(self.buf[:self.len])

    def __repr__(self):
        return 'i2c_msg(%d,%d,%r)' % (self.addr, self.flags, self.__bytes__())

    def __str__(self):
        s = self.__bytes__()
        # Throw away non-decodable bytes
        s = s.decode(errors="ignore")
        return s
