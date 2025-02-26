import pluto_ecm_logger
from pluto_ecm_hw_pkg import *
import socket
import struct
from getmac import get_mac_address

UDP_PAYLOAD_SIZE = DMA_TRANSFER_SIZE + 4 #includes seq num

class pluto_ecm_hw_dma_writer_udp:
  def __init__(self, logger, pluto_uri, local_ip):
    self.logger = logger

    assert (pluto_uri.startswith("ip:"))
    self.local_ip = local_ip
    self.remote_ip = pluto_uri.split(":")[1]
    self.remote_ip_port = (self.remote_ip, UDP_FILTER_PORT)

    self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.sock.bind((local_ip, 0))

    self.logger.log(self.logger.LL_INFO, "[hw_dma_writer_udp] init, socket={}".format(self.sock))

  def write(self, data):
    bytes_written = self.sock.sendto(bytearray(data), self.remote_ip_port)
    if bytes_written == 0:
      raise Exception("failed to write buffer")

    #TODO: remove data from log line
    self.logger.log(self.logger.LL_DEBUG, "[hw_dma_writer_udp] wrote {} to buffer = {} bytes".format(data, bytes_written))

    #bytes_written = self.buffer.write(bytearray(data))
    #if bytes_written == 0:
    #  raise Exception("failed to write buffer")
    #
    #num_words = (bytes_written + 3) // 4
    #self.buffer.push(num_words)
    #self.logger.log(self.logger.LL_DEBUG, "[hw_dma_writer] wrote {} to buffer ({} bytes -> {} words)".format(data, bytes_written, num_words))

  def initialize_hardware_tx(self, remote_mac):
    local_mac = get_mac_address(ip=self.local_ip)

    assert (len(remote_mac) > 0) and (":" in remote_mac) and (len(remote_mac.split(":")) == 6)
    assert (len(local_mac) > 0) and (":" in local_mac) and (len(local_mac.split(":")) == 6)

    remote_mac_b  = bytearray.fromhex("".join([b for b in remote_mac.split(":")]))
    local_mac_b   = bytearray.fromhex("".join([b for b in local_mac.split(":")]))
    local_ip_b    = bytearray.fromhex("".join(["{:02x}".format(int(b)) for b in self.local_ip.split(".")]))
    remote_ip_b   = bytearray.fromhex("".join(["{:02x}".format(int(b)) for b in self.remote_ip.split(".")]))
    udp_port_b    = bytearray.fromhex("{:04x}".format(UDP_FILTER_PORT))

    tx_setup_packet = bytearray("UDPSETUP", "ascii")
    tx_setup_packet.extend(local_mac_b)         #dest mac
    tx_setup_packet.extend(remote_mac_b)        #source mac
    tx_setup_packet.extend(b"\x08\x00")         #eth type
    tx_setup_packet.extend(b"\x45\x00\x00\x00") #IP header [0:3]
    tx_setup_packet.extend(b"\x00\x00\x40\x00") #IP header [4:7]
    tx_setup_packet.extend(b"\x40\x11\x00\x00") #IP header [8:11]
    tx_setup_packet.extend(remote_ip_b)         #IP header [12:15]  - source addr
    tx_setup_packet.extend(local_ip_b)          #IP header [16:19]  - dest addr
    tx_setup_packet.extend(udp_port_b)          #UDP source port
    tx_setup_packet.extend(udp_port_b)          #UDP dest port
    tx_setup_packet.extend(b"\x00\x00")         #UDP length
    tx_setup_packet.extend(b"\x00\x00")         #UDP checksum

    #TODO: partial IP checksum

    self.logger.log(self.logger.LL_INFO, "[hw_dma_writer_udp] initialize_hardware_tx: local_mac={} remote_mac={}".format(local_mac, remote_mac))
    self.logger.log(self.logger.LL_INFO, "[hw_dma_writer_udp] initialize_hardware_tx: tx_setup_packet={}".format(tx_setup_packet))

    self.write(tx_setup_packet)
