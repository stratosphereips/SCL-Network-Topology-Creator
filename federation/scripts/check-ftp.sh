#!/bin/bash
# check-ftp.sh - Check FTP server connectivity
# Usage: ./check-ftp.sh <host> <port>

HOST="${1:-ubuntu-1}"
PORT="${2:-21}"

# Try to connect to FTP server
curl -s --connect-timeout 5 "ftp://${HOST}:${PORT}/" > /dev/null 2>&1
exit $?
