# Program to control passerelle between Android application
# and micro-controller through USB tty
import time
import argparse
import signal
import sys
import socket
import socketserver
import serial
import threading
import json 


HOST           = "192.168.1.110"  # The server's hostname or IP address²
UDP_PORT       = 10000
MICRO_COMMANDS = ["TL" , "LT"]
FILENAME        = "values.json"
LAST_VALUE      = ""

DATA_MEASUREMENT = {}

ORDER_DISPLAY = {} # ID:TLHP


class ThreadedUDPRequestHandler(socketserver.BaseRequestHandler):
    
    def _is_change_order_action(self, data):
        must_containe_each = [":", "T", "L", "H", "P"]
        for item in must_containe_each:
            if item not in data:
                return False
        return True and len(data) == 16+5 # 5 characters for command and 16 for the id

    def handle(self):
        data = self.request[0].strip().decode()
        socket = self.request[1]
        current_thread = threading.current_thread()
        print("{}: client: {}, wrote: {}".format(current_thread.name, self.client_address, data))
        if data != "":
                        if self._is_change_order_action(data): # Send message through UART
                                ORDER_DISPLAY[data[:16]] = data[17:] # save order in display
                        elif data == "ping":
                                socket.sendto("pong".encode(), self.client_address) 
                        elif data == "getValues()": 
                                socket.sendto(json.dumps(DATA_MEASUREMENT, indent=4).encode(), self.client_address) 
                        else:
                                print("Unknown message: ",data)

class ThreadedUDPServer(socketserver.ThreadingMixIn, socketserver.UDPServer):
    pass


# send serial message 
SERIALPORT = "/dev/ttyACM0"
BAUDRATE = 115200
ser = serial.Serial()

def initUART():        
        # ser = serial.Serial(SERIALPORT, BAUDRATE)
        ser.port=SERIALPORT
        ser.baudrate=BAUDRATE
        ser.bytesize = serial.EIGHTBITS #number of bits per bytes
        ser.parity = serial.PARITY_NONE #set parity check: no parity
        ser.stopbits = serial.STOPBITS_ONE #number of stop bits
        ser.timeout = None          #block read

        # ser.timeout = 0             #non-block read
        # ser.timeout = 2              #timeout block read
        ser.xonxoff = False     #disable software flow control
        ser.rtscts = False     #disable hardware (RTS/CTS) flow control
        ser.dsrdtr = False       #disable hardware (DSR/DTR) flow control
        #ser.writeTimeout = 0     #timeout for write
        print('Starting Up Serial Monitor')
        try:
                ser.open()
        except serial.SerialException:
                print("Serial {} port not available".format(SERIALPORT))
                exit()



def sendUARTMessage(msg):
    ser.write((msg+"\n").encode())
    print("Message <" + msg + "> sent to micro-controller." )

def send_back_to_microbit_ordrer(id):
        if id in ORDER_DISPLAY.keys():
                sendUARTMessage(ORDER_DISPLAY[id])
        else:
               sendUARTMessage("")

def writeToFile():
        f= open(FILENAME,"w")
        f.write(json.dumps(DATA_MEASUREMENT, indent=4))
        f.close()
def loadFromFile():
        f= open(FILENAME,"r")
        try:
                DATA_MEASUREMENT = json.loads(f.read())
        except:
                print("File not found or empty, creating new file")
                DATA_MEASUREMENT = {}
        f.close()
        return DATA_MEASUREMENT

# Main program logic follows:
if __name__ == '__main__':
        initUART()
        loadFromFile()
        print ('Press Ctrl-C to quit.')

        server = ThreadedUDPServer((HOST, UDP_PORT), ThreadedUDPRequestHandler)

        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True

        try:
                server_thread.start()
                print("Server started at {} port {}".format(HOST, UDP_PORT))
                while ser.isOpen() : 
                        # time.sleep(100)
                        if (ser.inWaiting() > 0): # if incoming bytes are waiting 
                                data_bytes = ser.read(ser.inWaiting())
                                data_str = data_bytes.decode()
                                LAST_VALUE += str(data_str)

                                if '\n' in LAST_VALUE:
                                        
                                        splited = LAST_VALUE.split("=")
                                        LAST_VALUE = ""
                                        if len(splited) != 2:
                                                print("Invalid data received", splited)
                                                continue

                                        DATA_MEASUREMENT[splited[0]] = json.loads(splited[1])
                                        writeToFile()
                                        send_back_to_microbit_ordrer(splited[0])
                                        # sendUARTMessage("test")
        except (KeyboardInterrupt, SystemExit):
                server.shutdown()
                server.server_close()
                ser.close()
                exit()
