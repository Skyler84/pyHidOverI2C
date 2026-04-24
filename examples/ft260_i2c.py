import hid
import ft260
import hidoveri2c
import hid_parser

if __name__ == "__main__":
    # Create an instance of the FT260 class
    # h = hid.Device(0x0403, 0x6010)
    h = hid.device()
    h.open(0x3825, 0x0101)
    i2c = ft260.FT260_I2C(h)

    hi2c = hidoveri2c.HidOverI2c(i2c, 0x2C, 0x0020)

    report_descr = hi2c.get_report_descriptor(hi2c.report_descriptor_length)
    print(report_descr)
    rdesc = hid_parser.ReportDescriptor(report_descr)
    for rid in rdesc.input_report_ids:
        print(f"Input Report ID: {rid}")
        for item in rdesc.get_input_items(rid):
            print(item)


