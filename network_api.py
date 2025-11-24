from flask import Flask, jsonify, request
from flask_cors import CORS
import netifaces
import subprocess
import time

app = Flask(__name__)
CORS(app)

# CẤU HÌNH TÊN CARD MẠNG (Bạn cần check 'ip addr' trên máy thật để điền đúng)
# Ví dụ máy thật là enp3s0, enp4s0 thì sửa key bên dưới cho khớp
INTERFACES_MAP = {
    "eth0": "Port 1",
    "eth1": "Port 2"
}

def get_connection_name(iface):
    """Tìm tên Connection của NetworkManager đang quản lý interface này"""
    try:
        # Tìm connection đang active
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

    # 1. Lấy IP thực tế từ hệ thống
    try:
        if iface_name in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface_name)
            if netifaces.AF_INET in addrs:
                ipv4 = addrs[netifaces.AF_INET][0]
                data["ipAddress"] = ipv4.get('addr')
                data["subnetMask"] = ipv4.get('netmask')

            # Gateway
            gws = netifaces.gateways()
            if 'default' in gws and netifaces.AF_INET in gws['default']:
                gw_info = gws['default'][netifaces.AF_INET]
                if gw_info[1] == iface_name:
                    data["gateway"] = gw_info[0]
    except:
        pass

    # 2. Lấy cấu hình từ NetworkManager
    try:
        method = subprocess.check_output(["nmcli", "-g", "ipv4.method", "dev", "show", iface_name], stderr=subprocess.DEVNULL).decode().strip()
        data["dhcp"] = (method == "auto")

        dns_output = subprocess.check_output(["nmcli", "-g", "IP4.DNS", "dev", "show", iface_name], stderr=subprocess.DEVNULL).decode().strip()
        if dns_output:
            data["dns"] = dns_output.replace(" | ", ",").replace(" ", ",")
    except:
        pass

    return data

@app.route('/api/network', methods=['GET'])
def get_all_networks():
    results = []
    # Lấy danh sách interface từ cấu hình MAP hoặc tự động quét
    # Ở đây dùng MAP để đảm bảo thứ tự và tên hiển thị
    for iface in INTERFACES_MAP.keys():
        results.append(get_interface_details(iface))
    return jsonify(results)

@app.route('/api/network/<iface_name>', methods=['GET'])
def get_network(iface_name):
    return jsonify(get_interface_details(iface_name))

@app.route('/api/network/<iface_name>', methods=['PUT'])
def update_network(iface_name):
    # Cho phép update kể cả nếu interface không nằm trong MAP (linh hoạt)

    data = request.json
    is_dhcp = data.get('dhcp', False)

    conn_name = get_connection_name(iface_name)
    if not conn_name:
        conn_name = f"Wired connection {iface_name}"
        subprocess.run(["nmcli", "con", "add", "type", "ethernet", "ifname", iface_name, "con-name", conn_name])

    try:
        cmds = ["nmcli", "con", "modify", conn_name]

        if is_dhcp:
            cmds.extend(["ipv4.method", "auto"])
            cmds.extend(["ipv4.addresses", "", "ipv4.gateway", "", "ipv4.dns", ""])
        else:
            ip = data.get('ipAddress')
            mask = data.get('subnetMask')
            gateway = data.get('gateway') # Có thể null hoặc rỗng
            dns = data.get('dns')         # Có thể null hoặc rỗng

            # --- KIỂM TRA BẮT BUỘC ---
            if not ip or not mask:
                 return jsonify({"error": "IP Address and Subnet Mask are required."}), 400

            # Tính CIDR (ví dụ: 24) từ Subnet Mask
            prefix = sum(bin(int(x)).count('1') for x in mask.split('.'))
            cidr = f"{ip}/{prefix}"

            cmds.extend(["ipv4.method", "manual"])
            cmds.extend(["ipv4.addresses", cidr])

            # --- XỬ LÝ GATEWAY (Không bắt buộc) ---
            if gateway and gateway.strip():
                cmds.extend(["ipv4.gateway", gateway.strip()])
            else:
                cmds.extend(["ipv4.gateway", ""]) # Xóa gateway cũ nếu không nhập mới

            # --- XỬ LÝ DNS (Không bắt buộc) ---
            if dns and dns.strip():
                cmds.extend(["ipv4.dns", dns.strip()])
            else:
                cmds.extend(["ipv4.dns", ""])

        # Thực thi lệnh
        print(f"Executing: {' '.join(cmds)}")
        subprocess.run(cmds, check=True)

        # Khởi động lại connection
        subprocess.run(["nmcli", "con", "down", conn_name], check=True)
        subprocess.run(["nmcli", "con", "up", conn_name], check=True)

        time.sleep(3) # Đợi lâu hơn chút để mạng ổn định

        return jsonify(get_interface_details(iface_name)), 200

    except subprocess.CalledProcessError as e:
        return jsonify({"error": "Failed to apply network settings", "details": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
