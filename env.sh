#!/bin/bash

# Set to client-side IP address
HOST=192.168.1.101

# Set to server-side IP address
TARGET=192.168.1.102

# Set to the network interface name (eg. ens1np0).
# We assume both side use the same interface name. 
# Please change other scripts accordingly if they are different.
INTF=enp202s0f0np0

# Set to the hostname of the remote server (e.g., syslab.cs.virginia.edu)
TARGETC=clnode264.clemson.cloudlab.us

# Username of the remote server (e.g., netian)
USER=netian

# Set to the directory of the project on the remote server (e.g., /home/ame)
TARGETDIR=/users/netian
