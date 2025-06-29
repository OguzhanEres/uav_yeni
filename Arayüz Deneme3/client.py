import socket
import pickle
import time
import threading

# Soket oluştur ama bağlantı kurmadan bekle
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
response = None

# Bağlantı kurma işlemini fonksiyon içine al
def connect_to_server(host="127.0.0.1", port=65433):
    try:
        client_socket.connect((host, port))
        print(f"Sunucuya bağlandı: {host}:{port}")
        return True
    except ConnectionRefusedError:
        print(f"Bağlantı reddedildi: {host}:{port} adresinde sunucu bulunamadı")
        return False
    except Exception as e:
        print(f"Bağlantı hatası: {str(e)}")
        return False

requests = {0:"TAKEOFF",
            1:"LANDING",
            2:"LOITER",
            3:"RTL",
            4:"GUIDED"}

def take_telemetry():
    global client_socket, response
    while True:
        response = client_socket.recv(8192)
        response = pickle.loads(response)
        print(f"Server: {response}")
def send_command():
    global client_socket
    while True:
        message = input("0:TAKEOFF,\n1:LANDING,\n2:LOITER,\n3:RTL,\n4:GUIDED\nWhich one:")
        if message.lower() == "exit":
            print("Closing connection.")
            break
        try:
            message = int(message)
            if not message in requests:
                print("Invalid command.")
                continue
        except:
            print("You should type realated numbers only.")
            continue
        message = pickle.dumps(requests[message])
        client_socket.sendall(message)

try:
    connect_to_server()
    telemetry_thread = threading.Thread(target=take_telemetry)
    telemetry_thread.start()
    """command_thread = threading.Thread(target=send_command)
    command_thread.start()"""
except KeyboardInterrupt:
    print("Çıkılıyor...")
    client_socket.close()

