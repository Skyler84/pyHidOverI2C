# Python HID Over I2C Library
While both Windows and Linux both support HID Over I2C natively, this is mostly limited to devices enumerated at boot-up using ACPI tables or Device Trees.
This library aims to allow HID Over I2C devices to be tested without the OS being involved - simply using an I2C bus (such as SMBus) to communicate with the device.
It provides a drop in replacement compatible with pyhidapi interfaces, allowing ease of use with existing programs.