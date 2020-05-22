#!/usr/bin/python3

import sys
import ansible
from sh import Command
import json

def convert_mac(mac_nr):
	mac_str = ""
	for i in range(6):
		if mac_str:
			mac_str = "%X" % (mac_nr % 256) + ":"  + mac_str
		else:
			mac_str = "%X" % (mac_nr % 256)
		mac_nr = mac_nr // 256
	return mac_str

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

debug_print("before: {}\n".format(sys.argv[1]))
#we get a preceding u in the file name, so take it out:
inv_path = sys.argv[1][1:-1]
debug_print("after: {}\n".format(inv_path))

inv = get_inventory(inv_path)
debug_print("Inventory:\n {}\n".format(inv))

#get the localhost 
local_host = inv["_meta"]["hostvars"]["deploy_machine"]
debug_print("deploy machine: {}\n".format(local_host))

nr_vms = len(inv["virtual_machines"]["hosts"])
debug_print("nr of vms: {}\n".format(nr_vms))


commands = []
for switch in range(nr_vms):
	name = inv["virtual_machines"]["hosts"][switch]
	cmd = ""
	cmd += "nohup /usr/bin/kvm -m 2048 "
	cmd += "-name {} ".format(name)

	i = 0

	new_mac = local_host["starting_mac"].replace(":", "")
	mac = int(new_mac, 16)

	cmd += "-device e1000,netdev=net{},mac={} -netdev tap,id=net{},script={} ".format(i, convert_mac(mac+256*(switch-1)), i, local_host["mgmt_file"])


	for i in range(1, local_host["nr_ifs"]+1):
		cmd += "-device e1000,netdev=net{},mac={} -netdev tap,id=net{},script={} ".format(i, convert_mac(mac+256*(switch-1)+i), i, local_host["data_file"])  

	cmd += "-vnc 0.0.0.0:{} -vga std ".format(inv["_meta"]["hostvars"][name]["telnet_port"])
	cmd += "-drive file={}.img,media=disk,if=virtio,index=0 ".format(name)
	cmd += "-serial telnet:127.0.0.1:{},server &".format(inv["_meta"]["hostvars"][name]["telnet_port"])
	debug_print("Config {}: \n\n {} \n\n".format(switch, cmd))
	commands.append(cmd)
print(commands)


