from __future__ import print_function

import time

from dronekit import connect, VehicleMode, LocationGlobalRelative


vehicle = connect("tcp:127.0.0.1:5760", wait_ready=True, baud = 115200)
print(vehicle.armed)
print(vehicle.is_armable)
print(vehicle.mode)