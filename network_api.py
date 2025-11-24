from flask import Flask, jsonify, request
from flask_cors import CORS
import netifaces
import subprocess
import time

app = Flask(__name__)
CORS(app)

# Bản đồ tên cổng
INTERFACES_MAP = {
    "eth0": "Port 1",
    "eth1": "Port 2"
}

def get_connection_name(iface):
    """Tìm tên Connection của NetworkManager"""
    try:
        # Ưu tiên tìm connection đang active
        result = subprocess.check_output(["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"], stderr=subprocess.DEVNULL).decode()
        for line in result.splitlines():
            if ":" in line:
                name, device = line.split(":")
                if device == iface:
                    return name
        
        # Nếu không active, tìm connection bất kỳ gắn với iface
        result = subprocess.check_output(["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show"], stderr=subprocess.DEVNULL).decode()
        for line in result.splitlines():
            if ":" in line:
                name, device = line.split(":")
                if device == iface:
                    return name
    except:
        return None
    return None

def get_interface_details(iface_name):
    data = {
        "id": iface_name,
        "name": INTERFACES_MAP.get(iface_name, iface_name),
        "ipAddress": None,
        "subnetMask": None,
        "gateway": None,
        "dns": None,
        "dhcp": False
    }

    # 1. Lấy IP thực tế từ hệ thống (netifaces)
    try:
        if iface_name in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface_name)
            if netifaces.AF_INET in addrs:
                ipv4 = addrs[netifaces.AF_INET][0]
                data["ipAddress"] = ipv4.get('addr')
                data["subnetMask"] = ipv4.get('netmask')
            
            gws = netifaces.gateways()
            if 'default' in gws and netifaces.AF_INET in gws['default']:
                gw_info = gws['default'][netifaces.AF_INET]
                if gw_info[1] == iface_name:
                    data["gateway"] = gw_info[0]
    except:
        pass

    # 2. Lấy cấu hình từ NMCLI (để biết DHCP hay Static)
    try:
        method = subprocess.check_output(["nmcli", "-g", "ipv4.method", "dev", "show", iface_name], stderr=subprocess.DEVNULL).decode().strip()
        data["dhcp"] = (method == "auto")
        
        dns_output = subprocess.check_output(["nmcli", "-g", "IP4.DNS", "dev", "show", iface_name], stderr=subprocess.DEVNULL).decode().strip()
        if dns_output:
            data["dns"] = dns_output.replace(" | ", ",").replace(" ", ",")
    except:
        pass

    return data

@app.route('/', methods=['GET'])
@app.route('/api/network', methods=['GET'])
def get_all_networks():
    results = []
    for iface in INTERFACES_MAP.keys():
        results.append(get_interface_details(iface))
    return jsonify(results)

@app.route('/<iface_name>', methods=['PUT'])
@app.route('/api/network/<iface_name>', methods=['PUT'])
def update_network(iface_name):
    print(f"--- Updating Network: {iface_name} ---")
    data = request.json
    is_dhcp = data.get('dhcp', False)
    
    # Tìm tên kết nối hiện tại
    conn_name = get_connection_name(iface_name)
    
    # Nếu chưa có connection nào, tạo mới
    if not conn_name:
        conn_name = f"Wired connection {iface_name}"
        print(f"Creating new connection: {conn_name}")
        try:
            subprocess.run(["nmcli", "con", "add", "type", "ethernet", "ifname", iface_name, "con-name", conn_name], check=True)
        except subprocess.CalledProcessError as e:
            return jsonify({"error": "Failed to create connection", "details": str(e)}), 500

    try:
        # Xây dựng lệnh MODIFY
        cmds = ["nmcli", "con", "modify", conn_name]
        
        if is_dhcp:
            # Chuyển sang DHCP
            cmds.extend(["ipv4.method", "auto"])
            # Xóa các thiết lập tĩnh cũ để sạch sẽ
            cmds.extend(["ipv4.addresses", "", "ipv4.gateway", "", "ipv4.dns", ""])
        else:
            # Chuyển sang Static
            ip = data.get('ipAddress')
            mask = data.get('subnetMask')
            gateway = data.get('gateway')
            dns = data.get('dns')

            if not ip or not mask:
                 return jsonify({"error": "IP Address and Subnet Mask are required."}), 400

            # Tính CIDR (VD: 24)
            prefix = sum(bin(int(x)).count('1') for x in mask.split('.'))
            cidr = f"{ip}/{prefix}"

            cmds.extend(["ipv4.method", "manual"])
            cmds.extend(["ipv4.addresses", cidr])
            
            # Xử lý Gateway
            if gateway and gateway.strip():
                cmds.extend(["ipv4.gateway", gateway.strip()])
            else:
                cmds.extend(["ipv4.gateway", ""]) # Xóa gateway cũ

            # Xử lý DNS
            if dns and dns.strip():
                cmds.extend(["ipv4.dns", dns.strip()])
            else:
                cmds.extend(["ipv4.dns", ""])

        # Thực thi lệnh modify
        print(f"Executing: {' '.join(cmds)}")
        subprocess.run(cmds, check=True, capture_output=True, text=True)

        # Restart connection để áp dụng
        print("Restarting connection...")
        subprocess.run(["nmcli", "con", "down", conn_name], check=True)
        subprocess.run(["nmcli", "con", "up", conn_name], check=True)
        
        # Đợi 1 chút cho mạng nhận IP
        time.sleep(3)
        
        return jsonify(get_interface_details(iface_name)), 200

    except subprocess.CalledProcessError as e:
        err_msg = e.stderr if e.stderr else str(e)
        print(f"Error: {err_msg}")
        return jsonify({"error": "Failed to configure network", "details": err_msg.strip()}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Chạy cổng 5000
    app.run(host='0.0.0.0', port=5000)
