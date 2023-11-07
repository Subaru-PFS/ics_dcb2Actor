#!/usr/bin/env python3

import signal
import socket
import subprocess
import sys
from functools import partial


def execute_script(script_name):
    process = subprocess.Popen(f"{script_name}", shell=True, stdout=subprocess.PIPE, text=True)
    for line in process.stdout:
        yield line


def signal_handler(sig, frame, server_socket):
    print("Shutting down the server...")
    if server_socket:
        server_socket.close()
    sys.exit(0)


def main():
    host = 'filterheel-dcb'
    port = 9000

    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((host, port))
        server_socket.listen(1)

        print(f"Server is listening on {host}:{port}")

        signal.signal(signal.SIGINT, partial(signal_handler, server_socket=server_socket))

        while True:
            conn, addr = server_socket.accept()
            print(f"Connection established with {addr}")

            while True:
                recv = conn.recv(1024).decode()
                if not recv:
                    break

                print(recv)

                script_name, _ = recv.split('\r\n')
                print(f"Received request to execute script: {script_name}")

                for output_line in execute_script(script_name):
                    conn.send(f"{output_line}".encode())

            print('closing connection')
            conn.close()

    except Exception as e:
        if server_socket:
            server_socket.close()
        raise


if __name__ == "__main__":
    main()
