import struct
import time
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

    class Version:
        def __init__(self, version_id):
            self.major = version_id >> 8
            self.minor = (version_id & 0xFF) >> 4
            self.patch = (version_id & 0x0F)

    def __init__(self, bus, addr, descriptor_reg):
        self._bus = bus
        self._addr = addr
        self._descriptor_reg = descriptor_reg
        read_msgs = self._prepare_register_read(self._descriptor_reg, 4)
        self._bus.i2c_rdwr(*read_msgs)
        descriptor_header = self.HidOverI2cDescriptorHeader.unpack(bytes(read_msgs[-1]))
        read_msgs = self._prepare_register_read(self._descriptor_reg, descriptor_header.wHIDDescLength)
        self._bus.i2c_rdwr(*read_msgs)
        self._descriptor = self.HidOverI2cDescriptor.unpack(bytes(read_msgs[-1]))

    def read(self, size: int, timeout_ms=None):
        return self._input_read(size, timeout_ms)
    
    def _read(self, size: int):
        """
        Perform an immediate, unsolicited read from HidOverI2c device

        """
        read = i2c_msg.read(self._addr, size)
        self._bus.i2c_rdwr(read)
        return bytes(read)

    def write(self, data):
        self._output_write(data)

    def get_report(self, report_type, report_id, size):
        if report_type == self.ReportType.Input:
            return self.get_input_report(report_id, size)
        elif report_type == self.ReportType.Feature:
            return self.get_feature_report(report_id, size)

    def set_report(self, report_type, **kwargs):
        if report_type == self.ReportType.Input:
            return self.set_input_report(**kwargs)
        elif report_type == self.ReportType.Feature:
            return self.set_feature_report(**kwargs)
    
    def get_input_report(self, report_id, size):
        return self._get_request(self.RequestOpcode.GET_REPORT, self.ReportType.Input, report_id, size=size)[2:]

    def set_output_report(self, report_id, data):
        self._set_request(self.RequestOpcode.SET_REPORT, self.ReportType.Output, report_id, data)

    def get_feature_report(self, report_id, size) -> bytes:
        return self._get_request(self.RequestOpcode.GET_REPORT, report_type=self.ReportType.Feature, report_id=report_id, size=size)

    def set_feature_report(self, report_id, data):
        self._set_request(self.RequestOpcode.SET_REPORT, self.ReportType.Feature, report_id=report_id, data=data)

    def get_report_descriptor(self, size = 4096):
        i2c_msgs = self._prepare_register_read(self._report_descriptor_register, size)
        self._bus.i2c_rdwr(*i2c_msgs)
        return bytes(i2c_msgs[-1])

    def get_idle(self, report_id=0):
        _bytes = self._get_request(self.RequestOpcode.GET_IDLE, size=2, report_id=report_id)
        return struct.unpack("<H", _bytes)[0]
    
    def set_idle(self, duration, report_id=0):
        _bytes = struct.pack("<H", duration)
        self._set_request(self.RequestOpcode.SET_IDLE, data=_bytes, report_id=report_id)

    def get_protocol(self):
        _bytes = self._get_request(self.RequestOpcode.GET_IDLE, size=2)
        return struct.unpack("<H", _bytes)[0]

    def set_protocol(self, protocol: int):
        assert 0 <= protocol <= 1
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
        """
        Packs an opcode+report_type+report_id into 2 or 3 bytes, as required for the command register.
        #7.1.1
        """
        assert 0 <= report_id <= 255
        if report_id < 15:
            _bytes = [report_id | (report_type.value << 4), opcode.value]
        else:
            _bytes = [15 | (report_type.value << 4), opcode.value, report_id]

        return bytes(_bytes)

    def _input_read(self, size, timeout_ms=0):
        # TODO: check if we're non blocking and whether we have IRQ signal
        start_time = time.time()
        while True:
            if timeout_ms > 0:
                elapsed = (time.time() - start_time)*1000 # ms
                remaining = timeout_ms - elapsed
                if remaining <= 0:
                    return None

            data = self._read(2+self._descriptor.wMaxInputLength)
            if len(data) <= 2:
                continue # device initiated reset?
            data_len = struct.unpack("<H", data[:2])[0]
            if data_len <= 2:
                continue # null report?

            report = data[2:data_len]
            return report

    def _output_write(self, data) -> bytes:
        i2c_msgs = self._prepare_register_write(self._output_register, data)
        self._bus.i2c_rdwr(*i2c_msgs)
        return bytes(i2c_msgs[-1]) # final read operation

    def _read_register(self, register, size) -> bytes:
        i2c_msgs = self._prepare_register_read(register, size)
        self._bus.i2c_rdwr(*i2c_msgs)
        return bytes(i2c_msgs[-1])
    
    def _write_register(self, register, data):
        i2c_msgs = self._prepare_register_write(register, data)
        self._bus.i2c_rdwr(*i2c_msgs)

    def _prepare_register_write(self, register, data) -> tuple[i2c_msg]:
        _data = self._register_bytes(register) + struct.pack("<H", len(data)) + data
        write = i2c_msg.write(self._addr, _data)
        return (write,)

    def _prepare_register_read(self, register, size) -> tuple[i2c_msg, i2c_msg]:
        """
        Prepares a Write (regnum)+Read (regdata) I2C messages for a single transaction.
        """
        write = i2c_msg.write(self._addr, self._register_bytes(register))
        read = i2c_msg.read(self._addr, size)
        return (write, read)

    @staticmethod
    def _register_bytes(register) -> bytes:
        """
        Returns the specified 16-bit value as bytes(2) as required for an i2c write register.
        """
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
        return self.Version(self._descriptor.bcdVersion)

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

class HIDAPI_HidOverI2c(HidOverI2c):

    def set_feature_report(self, report, report_id=None, **kwargs):
        report_id = report[0]
        return super().set_feature_report(report_id, report, **kwargs)

    def set_output_report(self, report, report_id=None, **kwargs):
        report_id = report[0]
        return super().set_output_report(report_id, report, **kwargs)

    send_feature_report = set_feature_report # provided for compatibility.
    send_output_report  = set_output_report  # provided for compatibility.
