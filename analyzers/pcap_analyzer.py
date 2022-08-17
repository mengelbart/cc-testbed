from scapy.layers.l2 import Ether
from scapy.layers.inet import IP
from scapy.utils import RawPcapReader


class PCAPAnalyzer():
    def __init__(self):
        pass

    def read(self, file):
        count = 0
        interesting_packet_count = 0
        for (pkt_data, pkt_metadata,) in RawPcapReader(file):
            count += 1
            ether_pkt = Ether(pkt_data)
            if 'type' not in ether_pkt.fields:
                # disregard LLC frames
                print('disregarding llc frame')
                continue

            if ether_pkt.type != 0x0800:
                # disregard non-IPv4
                print('disregarding non-IPv4')
                continue

            ip_pkt = ether_pkt[IP]
            if ip_pkt.proto != 17:
                # disregard non-UDP
                print('disregarding non-UDP')
                continue

            interesting_packet_count += 1
        print('{} contains {} packets ({} interesting)'.
              format(file, count, interesting_packet_count))
