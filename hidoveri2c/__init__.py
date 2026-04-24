import struct
from dataclasses import dataclass
from enum import Enum, Flag


try:
    from smbus2 import i2c_msg
except ImportError:
    from .i2c_msg import i2c_msg

class HidOverI2c:
    @dataclass
    class HidOverI2cDescriptorHeader:
        wHIDDescLength: int
        bcdVersion: int

        STRUCT = struct.Struct("<HH")

        @classmethod
        def unpack(cls, data: bytes):
            values = cls.STRUCT.unpack(data)
            return cls(*values)

    @dataclass
    class HidOverI2cDescriptor:
        wHIDDescLength: int
        bcdVersion: int
        wReportDescLength: int
        wReportDescRegister: int
        wInputRegister: int
        wMaxInputLength: int
        wOutputRegister: int
        wMaxOutputLength: int
        wCommandRegister: int
        wDataRegister: int
        wVendorID: int
        wProductID: int
        wVersionID: int
        RESERVED: int

        STRUCT = struct.Struct("<HHHHHHHHHHHHHI")

        @classmethod
        def unpack(cls, data: bytes):
            values = cls.STRUCT.unpack(data)
            return cls(*values)
        
        def pack(self) -> bytes:
            return self.STRUCT.pack(
                self.wHIDDescLength,
                self.bcdVersion,
                self.wReportDescLength,
                self.wReportDescRegister,
                self.wInputRegister,
                self.wMaxInputLength,
                self.wOutputRegister,
                self.wMaxOutputLength,
                self.wCommandRegister,
                self.wDataRegister,
                self.wVendorID,
                self.wProductID,
                self.wVersionID,
                self.RESERVED
            )
        
    class RequestOpcode(Enum):
        RESERVED_0 = 0b0000
        RESET = 0b0001
        GET_REPORT   = 0b0010
        SET_REPORT   = 0b0011
        GET_IDLE     = 0b0100
        SET_IDLE     = 0b0101
        GET_PROTOCOL = 0b0110
        SET_PROTOCOL = 0b0111
        SET_POWER    = 0b1000
        RESERVED_9  = 0b1001
        RESERVED_A  = 0b1010
        RESERVED_B  = 0b1011
        RESERVED_C  = 0b1100
        RESERVED_D  = 0b1101
        VENDOR       = 0b1110
        RESERVED_F  = 0b1111

    class Flags(Flag):
        ALLOW_INVALID = 0

    class ReportType(Enum):
        RESERVED = 0b00
        Input    = 0b01
        Output   = 0b10
        Feature  = 0b11

    def __init__(self, bus, addr, descriptor_reg):
        self._bus = bus
        self._addr = addr
        self._descriptor_reg = descriptor_reg
        read_msgs = self._register_read(self._descriptor_reg, 4)
        self._bus.i2c_rdwr(*read_msgs)
        descriptor_header = self.HidOverI2cDescriptorHeader.unpack(bytes(read_msgs[-1]))
        read_msgs = self._register_read(self._descriptor_reg, descriptor_header.wHIDDescLength)
        self._bus.i2c_rdwr(*read_msgs)
        self._descriptor = self.HidOverI2cDescriptor.unpack(bytes(read_msgs[-1]))

    def read(self, size, timeout=None):
        return self._input_read(size, timeout)

    def write(self, data):
        self._output_write(data)
    
    def get_input_report(self, report_id, size):
        return self._get_request(self.RequestOpcode.GET_REPORT, self.ReportType.Input, report_id, size=size)[2:]

    def set_output_report(self, report_id, data):
        self._set_request(self.RequestOpcode.SET_REPORT, self.ReportType.Output, report_id, data)

    def get_feature_report(self, report_id, size):
        return self._get_request(self.RequestOpcode.GET_REPORT, report_type=self.ReportType.Feature, report_id=report_id, size=size)

    def set_feature_report(self, report_id, data):
        self._set_request(self.RequestOpcode.SET_REPORT, self.ReportType.Feature, report_id=report_id, data=data)

    def get_report_descriptor(self, size = 4096):
        i2c_msgs = self._register_read(self._report_descriptor_register, size)
        self._bus.i2c_rdwr(*i2c_msgs)
        return bytes(i2c_msgs[-1])

    def get_idle(self):
        _bytes = self._get_request(self.RequestOpcode.GET_IDLE, size=2)
        return struct.unpack("<H", _bytes)
    
    def set_idle(self, duration):
        _bytes = struct.pack("<H", duration)
        self._set_request(self.RequestOpcode.SET_IDLE, data=_bytes)

    def get_protocol(self):
        _bytes = self._get_request(self.RequestOpcode.GET_IDLE, size=2)
        return struct.unpack("<H", _bytes)

    def set_protocol(self, protocol):
        _bytes = struct.pack("<H", protocol)
        self._set_request(self.RequestOpcode.SET_PROTOCOL, data=_bytes)

    def reset(self):
        self._set_request(self.RequestOpcode.RESET)

    def set_power(self, power) -> None:
        assert 0 <= power <= 1
        self._set_request(self.RequestOpcode.SET_POWER, report_id=power)

    def _get_request(self, opcode: RequestOpcode, *, report_type = ReportType.RESERVED, report_id = 0, size) -> bytes:
        _command_bytes = self._register_bytes(self._command_register) + self._pack_request(opcode, report_type, report_id)
        _data_bytes = self._register_bytes(self._data_register)
        write = i2c_msg.write(self._addr, _command_bytes + _data_bytes)
        read = i2c_msg.read(self._addr, size+2) # +2 for length prefix
        self._bus.i2c_rdwr(write, read)
        return bytes(read)[2:]

    def _set_request(self, opcode: RequestOpcode, report_type = ReportType.RESERVED, report_id = 0, data: bytes|None = None) -> None:
        _command_bytes = self._register_bytes(self._command_register) + self._pack_request(opcode, report_type, report_id)
        if data is not None:
            _data_bytes = self._register_bytes(self._data_register) + struct.pack("<H", len(data)+2) + data
            write = i2c_msg.write(self._addr, _command_bytes + _data_bytes)
        else:
            write = i2c_msg.write(self._addr, _command_bytes)
        self._bus.i2c_rdwr(write)

    @staticmethod
    def _pack_request(opcode: RequestOpcode, report_type: ReportType, report_id) -> bytes:
        assert 0 <= report_id <= 255
        if report_id < 15:
            _bytes = [report_id | (report_type.value << 4), opcode.value]
        else:
            _bytes = [15 | (report_type.value << 4), opcode.value, report_id]

        return bytes(_bytes)

    def _input_read(self, size, timeout=None):
        # check if we're non blocking and whether we have IRQ signal
        pass

    def _output_write(self, data) -> bytes:
        i2c_msgs = self._register_write(self._output_register, data)
        self._bus.i2c_rdwr(*i2c_msgs)
        return bytes(i2c_msgs[-1]) # final read operation

    def _register_write(self, register, data) -> tuple[i2c_msg]:
        _data = self._register_bytes(register) + struct.pack("<H", len(data)) + data
        write = i2c_msg.write(self._addr, _data)
        return (write)

    def _register_read(self, register, size) -> tuple[i2c_msg, i2c_msg]:
        write = i2c_msg.write(self._addr, self._register_bytes(register))
        read = i2c_msg.read(self._addr, size)
        return (write, read)

    @staticmethod
    def _register_bytes(register) -> bytes:
        return struct.pack("<H", register)

    @property
    def manufacturer(self):
        return "Microsoft"

    @property
    def product(self):
        return "HID I2C Devic"

    @property
    def serial(self):
        return None

    @property
    def vid(self):
        return self._descriptor.wVendorID

    @property
    def pid(self):
        return self._descriptor.wProductID

    @property
    def version(self):
        return self._descriptor.wVersionID

    @property
    def _output_register(self):
        return self._descriptor.wOutputRegister
    
    @property
    def _input_register(self):
        return self._descriptor.wInputRegister
    
    @property
    def _report_descriptor_register(self):
        return self._descriptor.wReportDescRegister
    
    @property
    def _command_register(self):
        return self._descriptor.wCommandRegister
    
    @property
    def _data_register(self):
        return self._descriptor.wDataRegister
    
    @property
    def report_descriptor_length(self):
        return self._descriptor.wReportDescLength