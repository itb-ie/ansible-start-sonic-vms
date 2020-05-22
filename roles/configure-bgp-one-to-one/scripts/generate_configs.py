#!/usr/bin/python3

import sys
import ansible
from sh import Command
import json
import ipaddress


def debug_print(message):
  fp = open("output.txt", "a")
  fp.write(message)
  fp.close()


def get_inventory(inv_path):
  ansible_inventory = Command('ansible-inventory')
  json_inventory = json.loads(
    ansible_inventory('-i', inv_path, '--list').stdout)
  return json_inventory

	

fp = open("output.txt", "w")
fp.close()


if len(sys.argv) != 2:
  debug_print("This script takes 2 parameters. Try again!\n")
  exit()

debug_print("inainte: {}\n".format(sys.argv[1]))
#we get a preceding u in the file name, so take it out:
inv_path = sys.argv[1][1:-1]
debug_print("dupa: {}\n".format(inv_path))

inv = get_inventory(inv_path)
debug_print("Am inventarul:\n {}\n".format(inv))

#get the localhost 
local_host = inv["_meta"]["hostvars"]["deploy_machine"]
debug_print("Am variabilele din deploy machine: {}\n".format(local_host))

nr_vms = len(inv["virtual_machines"]["hosts"])
debug_print("Am numarul de vms de pornit: {}\n".format(nr_vms))

IP = inv["_meta"]["hostvars"]["vm1"]["data_intf_ip"]
Mask = int(inv["_meta"]["hostvars"]["vm1"]["data_intf_mask"])
BGP_peer = inv["_meta"]["hostvars"]["vm2"]["data_intf_ip"]
If =  int(inv["_meta"]["hostvars"]["deploy_machine"]["nr_ifs"])
BGP_local_as = inv["_meta"]["hostvars"]["vm1"]["local_as"]
BGP_remote_as = inv["_meta"]["hostvars"]["vm2"]["local_as"]
BGP_holdtime = int(inv["_meta"]["hostvars"]["vm1"]["holdtime"])
BGP_keepalive = int(inv["_meta"]["hostvars"]["vm1"]["keepalive"])
IP_mgmt = []
IP_mgmt.append(inv["_meta"]["hostvars"]["vm1"]["ansible_host"])
IP_mgmt.append(inv["_meta"]["hostvars"]["vm2"]["ansible_host"])
Mask_mgmt = inv["_meta"]["hostvars"]["vm2"]["mgmt_mask"]
Gateway_mgmt = inv["_meta"]["hostvars"]["vm2"]["mgmt_gw"]

setup_dir = local_host["working_directory"]

try:
  addr = int(ipaddress.IPv4Address(IP))
  peer = int(ipaddress.IPv4Address(BGP_peer))
except:
  print("Invalid IP address")
  exit()


for switch in range(2):

  config = ""

  ip_list = []
  peer_list = []
  for i in range(0,If):
    if switch == 0:
      ip_list.append(addr + i * 2**(32-Mask))
      peer_list.append(peer + i * 2**(32-Mask))
    else:
      ip_list.append(peer + i * 2**(32-Mask))
      peer_list.append(addr + i * 2**(32-Mask))

  config += '{\n' 

  #BGP part
  if True:
    config += '   "BGP_NEIGHBOR": {\n'
    for i in range(0, If):
      config += '       "{}": {}\n'.format(str(ipaddress.IPv4Address(peer_list[i])), "{")
      config += '           "rrclient": 0,\n'
      config += '           "name": "{}{}",\n'.format("peer", i)
      config += '           "local_addr": "{}",\n'.format(str(ipaddress.IPv4Address(ip_list[i])))
      config += '           "admin_status" : "up",\n'
      config += '           "nhopself": 0,\n'
      config += '           "holdtime": "{}",\n'.format(BGP_holdtime)
      if switch == 0:
        config += '           "asn": "{}",\n'.format(BGP_remote_as)
      else:
        config += '           "asn": "{}",\n'.format(BGP_local_as)
      config += '           "keepalive": "{}"\n'.format(BGP_keepalive)

      if i == If - 1:
        config += '       }\n'
      else:
        config += '       },\n'
    config += '   },\n'

  #metadata part
  config += '   "DEVICE_METADATA": {\n'
  config += '       "localhost": {\n'
  config += '           "hwsku": "Force10-S6000",\n'
  config += '           "hostname": "sonic{}",\n'.format(switch)
  config += '           "platform": "x86_64-kvm_x86_64-r0",\n'
  config += '           "mac": "52:54:00:12:34:{}",\n'.format(56+switch)
  if switch == 0:
    config += '           "bgp_asn": "{}",\n'.format(BGP_local_as)
  else:
    config += '           "bgp_asn": "{}",\n'.format(BGP_remote_as)
  config += '           "type": "LeafRouter"\n'
  config += '       }\n'
  config += '   },\n'

  config += '   "DEVICE_NEIGHBOR": {},\n'
  config += '   "LOOPBACK_INTERFACE": {\n'
  config += '       "Loopback0|20.2.0.{}/32": {{}}\n'.format(switch+1)
  config += '   },\n'

  #interface part
  config += '   "INTERFACE": {\n'
  for i in range(0, If):
    if i != If -1:
      config += '       "Ethernet{}|{}/{}": {{}},\n'.format(i*4, str(ipaddress.IPv4Address(ip_list[i])), Mask)
    else:
      config += '       "Ethernet{}|{}/{}": {{}}\n'.format(i*4, str(ipaddress.IPv4Address(ip_list[i])), Mask)
  config += '   },\n'

  config += '   "PORT": {\n'
  for i in range(0, If):
    config += '       "Ethernet{}": {{\n'.format(i*4)
    config += '           "index": "{}",\n'.format(i)
    config += '           "lanes": "{},{},{},{}",\n'.format(25+i*4, 25+i*4+1, 25+i*4+2, 25+i*4+3)
    config += '           "mtu": "9100",\n'
    config += '           "alias": "fortyGigE0/{}",\n'.format(i*4)
    config += '           "admin_status": "up",\n'
    config += '           "speed": "40000"\n'
    if i != If -1:
      config += '       },\n'
    else:
      config += '       }\n'
  config += '   },\n'

  config += '   "MGMT_INTERFACE": {\n'
  config += '     "eth0|{}/{}": {{\n'.format(IP_mgmt[switch], Mask_mgmt)
  config += '       "gwaddr": "{}"\n'.format(Gateway_mgmt)
  config += '     }\n'
  config += '   }\n'

  config += '}\n'
  
  # write to file
  fp = open("{}/{}.conf".format(setup_dir, inv["virtual_machines"]["hosts"][switch]), "w")
  fp.write(config)
  fp.close()
  debug_print("First config\n")
  debug_print(config) 



