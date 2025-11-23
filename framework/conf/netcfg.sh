#!/usr/bin/env bash
# netcfg.sh — toggle DHCP or set static IPv4 on a Linux interface
# Usage:
#   sudo ./netcfg.sh <iface> dhcp
#   sudo ./netcfg.sh <iface> static <ip> <netmask|prefix> <gateway> [dns1] [dns2]
#
# Examples:
#   sudo ./netcfg.sh enp0s31f6 dhcp
#   sudo ./netcfg.sh enp0s31f6 static 192.168.101.50 24 192.168.101.1
#   sudo ./netcfg.sh enp0s31f6 static 192.168.101.50 255.255.255.0 192.168.101.1 8.8.8.8 1.1.1.1

set -euo pipefail

need_root() {
  if [[ $EUID -ne 0 ]]; then
    echo "Please run as root (use sudo)." >&2
    exit 1
  fi
}

usage() {
  cat <<EOF
Usage:
  sudo $0 <iface> dhcp
  sudo $0 <iface> static <ip> <netmask|prefix> <gateway> [dns1] [dns2]

Examples:
  sudo $0 enp0s31f6 dhcp
  sudo $0 enp0s31f6 static 192.168.101.50 24 192.168.101.1
  sudo $0 enp0s31f6 static 192.168.101.50 255.255.255.0 192.168.101.1 8.8.8.8 1.1.1.1
EOF
  exit 1
}

mask_to_prefix() {
  local m="$1"
  # Accept plain CIDR like "24"
  if [[ "$m" =~ ^([0-9]|[12][0-9]|3[0-2])$ ]]; then
    echo "$m"; return 0
  fi

  local IFS=.
  local o1 o2 o3 o4
  read -r o1 o2 o3 o4 <<<"$m" || { echo "Invalid netmask: $m" >&2; exit 2; }
  for o in "$o1" "$o2" "$o3" "$o4"; do
    [[ "$o" =~ ^[0-9]+$ ]] && (( o>=0 && o<=255 )) || { echo "Invalid netmask: $m" >&2; exit 2; }
  done

  # Map octet → # of 1-bits
  declare -A M=([255]=8 [254]=7 [252]=6 [248]=5 [240]=4 [224]=3 [192]=2 [128]=1 [0]=0)
  local p1=${M[$o1]} p2=${M[$o2]} p3=${M[$o3]} p4=${M[$o4]}
  [[ -n "$p1" && -n "$p2" && -n "$p3" && -n "$p4" ]] || { echo "Invalid netmask: $m" >&2; exit 2; }

  # Ensure contiguous mask
  if (( p1<8 && (p2>0 || p3>0 || p4>0) )) || \
     (( p2<8 && (p3>0 || p4>0) )) || \
     (( p3<8 && p4>0 )); then
    echo "Netmask is not contiguous: $m" >&2
    exit 2
  fi

  echo $((p1 + p2 + p3 + p4))
}

# -------- NetworkManager helpers --------

nm_find_or_create_conn() {
  local iface="$1"
  local conn=""

  # 1) active connection on iface
  conn=$(nmcli -t -f NAME,DEVICE con show --active | awk -F: -v d="$iface" '$2==d{print $1; exit}')
  # 2) any connection bound to iface
  if [[ -z "${conn:-}" ]]; then
    conn=$(nmcli -t -f NAME,DEVICE con show | awk -F: -v d="$iface" '$2==d{print $1; exit}')
  fi
  # 3) create new if none exists
  if [[ -z "${conn:-}" ]]; then
    conn="netcfg-$iface"
    nmcli con add type ethernet ifname "$iface" con-name "$conn" >/dev/null
  fi

  echo "$conn"
}

nm_set_dhcp() {
  local iface="$1"
  local conn
  conn=$(nm_find_or_create_conn "$iface")

  # Switch to DHCP first, then clear stale static config
  nmcli con mod "$conn" ipv4.method auto
  nmcli con mod "$conn" ipv4.addresses "" ipv4.gateway "" ipv4.dns "" ipv4.routes ""

  nmcli con up "$conn" >/dev/null

  # Remove any non-dynamic IPs immediately
  ip -4 addr show dev "$iface" | awk '/inet / && !/dynamic/ {print $2}' | while read -r cidr; do
    ip addr del "$cidr" dev "$iface" 2>/dev/null || true
  done

  echo "DHCP enabled on $iface via NetworkManager (connection: $conn, static addresses cleared)."
}

nm_set_static() {
  local iface="$1" ip="$2" prefix="$3" gw="$4" dns1="${5:-}" dns2="${6:-}"
  local conn
  conn=$(nm_find_or_create_conn "$iface")

  local dns_list=""
  if [[ -n "$dns1" && -n "$dns2" ]]; then
    dns_list="$dns1,$dns2"
  elif [[ -n "$dns1" ]]; then
    dns_list="$dns1"
  elif [[ -n "$dns2" ]]; then
    dns_list="$dns2"
  else
    # no DNS provided → default to gateway (typical small LAN)
    dns_list="$gw"
  fi

  nmcli con mod "$conn" \
    ipv4.addresses "$ip/$prefix" \
    ipv4.gateway "$gw" \
    ipv4.dns "$dns_list" \
    ipv4.method manual

  nmcli con up "$conn" >/dev/null

  echo "Static IPv4 set on $iface via NetworkManager:"
  echo "  IP:       $ip/$prefix"
  echo "  Gateway:  $gw"
  echo "  DNS:      $dns_list"
}

# -------- Plain iproute2 + DHCP client helpers --------

plain_stop_dhcp() {
  local iface="$1"
  if command -v dhclient >/dev/null 2>&1; then
    dhclient -r "$iface" 2>/dev/null || true
  fi
  if command -v dhcpcd >/dev/null 2>&1; then
    dhcpcd -k "$iface" 2>/dev/null || true
  fi
}

plain_set_dhcp() {
  local iface="$1"
  plain_stop_dhcp "$iface"
  if command -v dhclient >/dev/null 2>&1; then
    dhclient "$iface"
    echo "DHCP enabled on $iface using dhclient."
  elif command -v dhcpcd >/dev/null 2>&1; then
    dhcpcd "$iface"
    echo "DHCP enabled on $iface using dhcpcd."
  else
    echo "No DHCP client (dhclient/dhcpcd) found. Install one, or use NetworkManager." >&2
    exit 3
  fi
}

plain_set_static() {
  local iface="$1" ip="$2" prefix="$3" gw="$4" dns1="${5:-}" dns2="${6:-}"
  plain_stop_dhcp "$iface"
  ip link set dev "$iface" up
  ip addr flush dev "$iface"
  ip addr add "$ip/$prefix" dev "$iface"
  ip route replace default via "$gw" dev "$iface"

  echo "Static IPv4 set on $iface using iproute2:"
  echo "  IP:       $ip/$prefix"
  echo "  Gateway:  $gw"

  local dns_list=""
  if [[ -n "$dns1" && -n "$dns2" ]]; then
    dns_list="$dns1,$dns2"
  elif [[ -n "$dns1" ]]; then
    dns_list="$dns1"
  elif [[ -n "$dns2" ]]; then
    dns_list="$dns2"
  fi

  if [[ -n "$dns_list" ]]; then
    echo "  DNS:      $dns_list"
    echo
    echo "NOTE: Not updating /etc/resolv.conf automatically."
    echo "      Set DNS manually (e.g. systemd-resolved or /etc/resolv.conf)."
  else
    echo "  DNS:      (unchanged)"
  fi

  echo "Warning: This will not persist after reboot unless you configure your network stack."
}

main() {
  need_root
  [[ $# -ge 2 ]] || usage

  local iface="$1" mode="$2"
  [[ -d "/sys/class/net/$iface" ]] || { echo "Interface not found: $iface" >&2; exit 2; }

  if command -v nmcli >/dev/null 2>&1; then
    # NetworkManager branch
    case "$mode" in
      dhcp)
        nm_set_dhcp "$iface"
        ;;
      static)
        [[ $# -ge 5 ]] || usage      # iface mode ip mask gw [dns1] [dns2]
        [[ $# -le 7 ]] || usage
        local ip="$3" mask="$4" gw="$5" dns1="${6:-}" dns2="${7:-}"
        local prefix
        prefix=$(mask_to_prefix "$mask")
        nm_set_static "$iface" "$ip" "$prefix" "$gw" "$dns1" "$dns2"
        ;;
      *)
        usage
        ;;
    esac
  else
    # Plain iproute2 + DHCP client branch
    case "$mode" in
      dhcp)
        plain_set_dhcp "$iface"
        ;;
      static)
        [[ $# -ge 5 ]] || usage
        [[ $# -le 7 ]] || usage
        local ip="$3" mask="$4" gw="$5" dns1="${6:-}" dns2="${7:-}"
        local prefix
        prefix=$(mask_to_prefix "$mask")
        plain_set_static "$iface" "$ip" "$prefix" "$gw" "$dns1" "$dns2"
        ;;
      *)
        usage
        ;;
    esac
  fi
}

main "$@"

