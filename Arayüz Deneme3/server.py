import socket

HOST = "127.0.0.1"
PORT = 65432

# Create a socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))
server_socket.listen(1)  # Accept only one client at a time

print(f"Server started on {HOST}:{PORT}")

conn, addr = server_socket.accept()  # Accept a connection
print(f"Connected by {addr}")

while True:
    try:
        # Receive data
        data = conn.recv(1024).decode()
        if not data:
            break  # If data is empty, client disconnected
        print(f"Client: {data}")

        # Stop communication if client sends 'exit'
        if data.lower() == "exit":
            print("Client disconnected.")
            conn.sendall("Goodbye!".encode())
            break

        # Send a response
        response = input("Server: ")  # Get user input for response
        conn.sendall(response.encode())
    
    except ConnectionResetError:
        print("Connection lost.")
        break

# Close connection
conn.close()
server_socket.close()
