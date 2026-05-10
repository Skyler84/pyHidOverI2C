from typing import Protocol, runtime_checkable, Iterator

@runtime_checkable
class I2CMessageClass(Protocol):
    """
    Using flexible signatures to match both smbus2 and alternatives
    """
    addr: int
    flags: int
    len: int
    def __bytes__(self) -> bytes: ...

    def __iter__(self) -> Iterator[int]: ...

    def __len__(self) -> int: ...

    @staticmethod
    def read(address: int, length: int) -> 'I2CMessageClass': ...
    
    @staticmethod
    def write(address: int, buf: bytes|str|list[int]) -> 'I2CMessageClass': ...
