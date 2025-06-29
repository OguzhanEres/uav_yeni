# Test MAVLink connection
from mavlink_client import MAVLinkClient
import time

def test_mavlink_connection():
    client = MAVLinkClient()
    
    print("Testing MAVLink connection...")
    
    # Try to connect to default SITL address
    if client.connect("udp:127.0.0.1:14550"):
        print("Connection successful!")
        
        # Read some telemetry data
        for i in range(10):
            data = client.get_telemetry_data()
            print(f"Lat: {data['lat']:.6f}, Lon: {data['lon']:.6f}, Alt: {data['altitude']:.2f}m")
            time.sleep(1)
        
        client.disconnect()
    else:
        print("Connection failed!")

if __name__ == "__main__":
    test_mavlink_connection()