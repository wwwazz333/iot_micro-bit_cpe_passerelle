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
FILENAME_MEASUREMENT        = "values.json"
FILENAME_ORDER        = "orders.json"
LAST_VALUE      = ""

DATA_MEASUREMENT = {}

ORDER_DISPLAY = {} # ID:TLHP



def logger(*msg: object):
    the_log = "[{}] {}".format(time.strftime("%d-%m-%Y %H:%M:%S"), " ".join(str(m) for m in msg))
    print(the_log)
    with open("log.txt", "a+") as log_file:
           log_file.write(the_log + "\n")

def save(data, filename):
       f= open(filename,"w")
       f.write(json.dumps(data, indent=4))
       f.close()
def loadFromFile(filename):
        loaded_values = {}
        try:
                with open(filename, "r") as f:
                        loaded_values = json.loads(f.read())
        except FileNotFoundError:
                logger("File not found, creating new file : ", filename)
                with open(filename, "w") as f:
                        f.write(json.dumps({}))
                loaded_values = {}
        except Exception:
                logger("File empty or invalid, resetting file : ", filename)
                with open(filename, "w") as f:
                        f.write(json.dumps({}))
                loaded_values = {}
        return loaded_values
def writeToFileOrder():
        save(ORDER_DISPLAY, FILENAME_ORDER)
def loadFromFileOrder():
        global ORDER_DISPLAY
        ORDER_DISPLAY = loadFromFile(FILENAME_ORDER)
        return ORDER_DISPLAY

def writeToFileMeasurement():
        save(DATA_MEASUREMENT, FILENAME_MEASUREMENT)
def loadFromFileMeasurement():
        global DATA_MEASUREMENT
        DATA_MEASUREMENT = loadFromFile(FILENAME_MEASUREMENT)
        return DATA_MEASUREMENT


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
        logger("{}: client: {}, wrote: {}".format(current_thread.name, self.client_address, data))
        if data != "":
                        if self._is_change_order_action(data): # Send message through UART
                                ORDER_DISPLAY[data[:16]] = data[17:] # save order in display
                                writeToFileOrder()
                        elif data == "ping":
                                socket.sendto("pong".encode(), self.client_address) 
                        elif data == "getValues()": 
                                socket.sendto(json.dumps(DATA_MEASUREMENT, indent=4).encode(), self.client_address) 
                        else:
                                logger("Unknown message: ",data)

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
        logger('Starting Up Serial Monitor')
        try:
                ser.open()
        except serial.SerialException:
                logger("Serial {} port not available".format(SERIALPORT))
                exit()



def sendUARTMessage(msg):
    ser.write((msg+"\n").encode())
    logger("Message <" + msg + "> sent to micro-controller." )

def send_back_to_microbit_ordrer(id):
        if id in ORDER_DISPLAY.keys():
                sendUARTMessage(ORDER_DISPLAY[id])
        else:
               sendUARTMessage("")



# Main program logic follows:
if __name__ == '__main__':
        initUART()
        loadFromFileMeasurement()
        loadFromFileOrder()
        print ('Press Ctrl-C to quit.')

        server = ThreadedUDPServer((HOST, UDP_PORT), ThreadedUDPRequestHandler)

        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True

        try:
                server_thread.start()
                logger("Server started at {} port {}".format(HOST, UDP_PORT))
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
                                                logger("Invalid data received", splited)
                                                continue

                                        DATA_MEASUREMENT[splited[0]] = json.loads(splited[1])
                                        writeToFileMeasurement()
                                        send_back_to_microbit_ordrer(splited[0])
        except (KeyboardInterrupt, SystemExit):
                server.shutdown()
                server.server_close()
                ser.close()
                exit()
