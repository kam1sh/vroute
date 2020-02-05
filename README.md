# Overview

Vroute (VPN route) is a tool for managing networks that should be routed via VPN. Or not VPN, but I use it to pass Russian goverment blocks by routing traffic on RouterOS router and Linux server into VPN.

## How that works?

**WIP**

## Requirements

Python 3.7, RouterOS device, Linux and PostgreSQL database.

## How to use it?

1. Create user and database:
```sql
CREATE ROLE vroute WITH LOGIN PASSWORD '...';
CREATE DATABASE vroute WITH OWNER vroute

CREATE TABLE networks (
    net inet PRIMARY KEY
);
```
2. Add mangle rule and routing rule:
```
/ip firewall mangle
add action=mark-routing chain=prerouting disabled=yes dst-address-list=blocked new-routing-mark=vpn src-address=!<LINUX_IP>
/ip route
add distance=5 gateway=<LINUX_IP> routing-mark=vpn
```
3. Create config in ~/.config/vroute.yml from config-template.yml
4. Load list of subnets:
```bash
$ echo 1.1.1.1/32 > subnets.txt
$ vroute load-networks subnets.txt
```
5. Bring up your VPN connection:
`systemctl start openvpn@my_connection`
6. Execute synchronization:
`vroute sync`

## Does it support IPv6?

My ISP support IPv6, but VPN provider (NordVPN) doesn't =( so I just can't test it properly.
