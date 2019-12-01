# Overview

Vroute (VPN route) is a tool for managing networks that should be routed via VPN. Or not VPN, but I use it to pass Russian goverment blocks by routing traffic on RouterOS router and Linux server into VPN.

## How that works?

Vroute stores networks and information about them in a PostgreSQL database.

## How to use it?

1. Create user and database:
```sql
CREATE ROLE vroute WITH LOGIN PASSWORD '...';
CREATE DATABASE vroute WITH OWNER vroute

CREATE TABLE networks (
    net inet PRIMARY KEY,
    updated TIMESTAMP,
    info JSON NOT NULL
);
CREATE INDEX networks_updated ON networks USING btree (updated);
```

## Does it support IPv6?

My ISP support IPv6, but VPN provider (NordVPN) doesn't =( so I just can't test it properly.
