import struct
import serial
import time

class Hardware_Exeption(Exception):
    pass

class BathController( object ):

	def __init__(self, port, baud, timeout=5):

		self.temperature_request = b"\x11" # DC1
		self.set_element_request = b"\x12" # DC2
		self.success_accept      = b"\x06" # ACK
		self.ready_request       = b"\x05" # ENQ
		self.fail_deny           = b"\x15" # NAK
		self.emergency_stop      = b"\x18"#  CAN

		self.port = port
		self.baud = baud
		self.timeout = timeout
		self.comline = serial.Serial(self.port, self.baud, timeout=self.timeout)


	def get_temperatures( self ):
		"""
		PC - Ready request
		HW - ACK/NAK
		PC - temperature_request
		HW - ACK/NAK
		HW - send binary packed temperatures and checksum
		PC - Parse / check data
		PC - ACK / NAK
			TODO - currently shuts down - interlock
			HW - if NAK resend, if 3 NAKs - failsafe shutdown
			PC - Listen until failsafe
		"""
		self.comline.flushInput()
		self.comline.flushOutput()
		self.comline.write(self.ready_request)
		# Shutdown if request denied
		while self.comline.inWaiting() < 1: pass
		reply = self.comline.read(1)
		reply = struct.unpack('B', str(reply))[0]
		if reply != struct.unpack('B', self.success_accept)[0]:
			raise Hardware_Exeption("Ready request denied for temperature data")
		#Request temperature data
		self.comline.write(self.temperature_request)
		# Shutdown if request denied
		while self.comline.inWaiting() < 1: pass
		reply = self.comline.read(1)
		reply = struct.unpack('B', str(reply))[0]
		if reply != struct.unpack('B', self.success_accept)[0]:
			raise Hardware_Exeption("Request denied for temperature data")
		# Get temperature data packet
		while self.comline.inWaiting() < 64: pass
		data = self.comline.read(64)
		data = struct.unpack('B'*64, data)
		# Check packet integrity
		if not self.checksum(data): 
			print "Checksum fail...\n{0}".format(data)
			# Will ensure element turns off until we sort the issue
			# self.comline.write(self.fail_deny)
			# Get temperature data packet
			return
		# Extract and scale temperatures
		environment_temperature = ((data[0] << 8) + (data[1]))/100.0
		bath_temperature = ((data[2] << 8) + (data[3]))/100.0
		self.comline.write(self.success_accept)
		return environment_temperature, bath_temperature


	def set_element_time( self , on_time):
		"""
		PC - Ready request
		HW - ACK/NAK
		PC - element_time_request
		HW - ACK/NAK
		PC - send uint32_t millis of element ON time
		HW - ACK/NAK
		"""
		self.comline.flushInput()
		self.comline.flushOutput()
		self.comline.write(self.ready_request)
		while self.comline.inWaiting() < 1: pass
		reply = self.comline.read(1)
		# Shutdown if request denied
		reply = struct.unpack('B', str(reply))[0]
		if reply != struct.unpack('B', self.success_accept)[0]:
			raise Hardware_Exeption("Ready request denied for element time operation") 
		# Request element time
		self.comline.write(self.set_element_request)
		# Read reply
		while self.comline.inWaiting() < 1: pass
		reply = self.comline.read(1)
		# Shutdown if request denied
		reply = struct.unpack('B', str(reply))[0]
		if reply != struct.unpack('B', self.success_accept)[0]:
			raise Hardware_Exeption("Element time request failed or denied")
		#Structure and pack data into serial payload
		b1 = on_time >> (3*8) & 0xFF
		b2 = on_time >> (2*8) & 0xFF
		b3 = on_time >> 8 & 0xFF
		b4 = on_time & 0xFF
		################################## checksum 
		csum = self.checksum([b1,b2,b3,b4], check=False)
		payload = struct.pack('4B59xB', b1,b2,b3,b4,csum)		
		# Send it...
		self.comline.write(payload)
		# Read reply
		while self.comline.inWaiting() < 1: pass
		reply = self.comline.read(1)
		# Shutdown if request denied
		reply = struct.unpack('B', str(reply))[0]
		if reply != struct.unpack('B', self.success_accept)[0]:
			raise Hardware_Exeption("Element time packet failed")
		return

	def checksum(self, data, check=True):
		# check = true returns checksum validation
		#       = false returns calc'd checksum of data[:-1] 
		t = 0
		if check:
			for i in data[:-1]: t += i
			return (t % 255) == data[-1]
		else:
			for i in data: t += i
			return (t % 255)


if __name__ == '__main__':
	import random
	control = BathController("/dev/ttyUSB1", 115200)
	test_no = 0;
	time.sleep(3)
	while True:
		# res = control.get_temperatures()
		# print "Environment temperature:\t{0}\nMedium temperature:\t\t{1}".format(res[0],res[1])
		# time.sleep(0.1)
		print '\n'+('#'*10)+' Hardware control test - iteration {0} '.format(test_no)+('#'*10)
		res = control.get_temperatures()
		print "Environment temperature:\t{0}\nMedium temperature:\t\t{1}".format(res[0],res[1])
		r = random.randint(2,15)
		print "Heating element for {0}ms...".format(r*1000)
		time.sleep(0.5)
		control.set_element_time(r*1000)
		test_no += 1
		time.sleep(r-1)
		#print "Room Temperature:\t{0}'c\nBath Temperature:\t{1}'c\n".format(res[0],res[1])

"""
>>> ser.flushInput()
>>> ser.flushOutput()
>>> ser.write(b"\x05")
1
>>> ser.read(1)
'\x06'
>>> ser.write(b"\x11")
1
>>> a = ser.read(65)
>>> a
'\x16\x17\xff\xfe[...]'
>>> b = struct.unpack('B'*65, a)
>>> (b[0] << 8) + (b[1])
5655
>>> (b[2] << 8) + (b[3])
65534
"""