from flask import Flask, jsonify, request
from flask_cors import CORS
import netifaces
import subprocess
import time

app = Flask(__name__)
CORS(app)

# Map đúng theo thực tế bạn mô tả
INTERFACES_MAP = {
    "eth1": "WAN 0",
    "eth0": "WAN 1"
}

def get_target_conn_name(iface):
    """Tạo tên kết nối chuẩn hóa để tránh nhầm lẫn"""
    return f"MAXiCom-{iface}"

def enforce_single_connection(iface):
    """
    Hàm này đảm bảo trên 1 cổng chỉ tồn tại DUY NHẤT 1 profile tên chuẩn.
    Xóa hết các profile rác (Wired connection 1, 2...)
    """
    target_name = get_target_conn_name(iface)
    
    try:
        # 1. Lấy danh sách tất cả connection của interface này
        output = subprocess.check_output(
            ["nmcli", "-t", "-f", "UUID,NAME,DEVICE", "connection", "show"],
            stderr=subprocess.DEVNULL
        ).decode()
        
        existing_uuids = []
        target_exists = False

        for line in output.splitlines():
            if not line.strip(): continue
            parts = line.split(":")
            if len(parts) < 3: continue
            
            uuid, name, device = parts[0], parts[1], parts[2]
            
            # Nếu connection này thuộc về interface đang xét
            if device == iface:
                if name == target_name:
                    target_exists = True
                else:
                    # Nếu không phải tên chuẩn -> Đánh dấu để xóa
                    existing_uuids.append(uuid)
            
            # Trường hợp profile không gắn device nhưng tên trùng tên rác thường gặp
            elif device == "" and (name.startswith("Wired connection") or name == "System " + iface):
                 # Cẩn thận hơn: Có thể xóa nhầm nếu không check kỹ, nhưng ở host mode thường ok
                 pass

        # 2. Xóa các kết nối rác
        for uuid in existing_uuids:
            print(f"[{iface}] Deleting duplicate/legacy profile: {uuid}")
            subprocess.run(["nmcli", "connection", "delete", uuid], check=False)

        # 3. Nếu chưa có profile chuẩn, tạo mới
        if not target_exists:
            print(f"[{iface}] Creating standard profile: {target_name}")
            subprocess.run([
                "nmcli", "con", "add",
                "type", "ethernet",
                "ifname", iface,
                "con-name", target_name
            ], check=True)
            
        return target_name

    except Exception as e:
        print(f"Error enforcing connection for {iface}: {e}")
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

    # 1. Lấy IP thực tế (Live Status)
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

    # 2. Lấy cấu hình từ Profile Chuẩn (MAXiCom-ethX)
    # Đảm bảo ta đọc đúng cái ta vừa ghi
    try:
        target_name = get_target_conn_name(iface_name)
        
        # Kiểm tra xem profile có tồn tại không
        check = subprocess.run(
            ["nmcli", "con", "show", target_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        if check.returncode == 0:
            # Lấy method
            method = subprocess.check_output(
                ["nmcli", "-g", "ipv4.method", "con", "show", target_name],
                stderr=subprocess.DEVNULL
            ).decode().strip()
            
            data["dhcp"] = (method == "auto")

            if method == "manual":
                dns_output = subprocess.check_output(
                    ["nmcli", "-g", "ipv4.dns", "con", "show", target_name],
                    stderr=subprocess.DEVNULL
                ).decode().strip()
                if dns_output:
                    data["dns"] = dns_output.replace(",", ", ")
    except Exception as e:
        print(f"Error reading config for {iface_name}: {e}")

    return data

@app.route('/', methods=['GET'])
@app.route('/api/network', methods=['GET'])
def get_all_networks():
    results = []
    # Duyệt theo map để đảm bảo thứ tự
    for iface in INTERFACES_MAP.keys():
        # Tự động dọn dẹp nhẹ khi load danh sách (để đảm bảo hiển thị đúng)
        # enforce_single_connection(iface) <--- Có thể bỏ dòng này nếu sợ chậm khi load
        results.append(get_interface_details(iface))
    return jsonify(results)

@app.route('/<iface_name>', methods=['PUT'])
@app.route('/api/network/<iface_name>', methods=['PUT'])
def update_network(iface_name):
    print(f"--- Updating {iface_name} ---")
    data = request.json
    is_dhcp = data.get('dhcp', False)
    
    # BƯỚC 1: Chuẩn hóa Connection (Xóa cũ, giữ 1 cái chuẩn tên MAXiCom-...)
    conn_name = enforce_single_connection(iface_name)
    
    if not conn_name:
        return jsonify({"error": "Failed to manage connection profile"}), 500

    try:
        cmds = ["nmcli", "con", "modify", conn_name]
        
        if is_dhcp:
            # DHCP
            cmds.extend(["ipv4.method", "auto"])
            cmds.extend(["ipv4.addresses", "", "ipv4.gateway", "", "ipv4.dns", ""])
        else:
            # Static
            ip = data.get('ipAddress')
            mask = data.get('subnetMask')
            gateway = data.get('gateway')
            dns = data.get('dns')

            if not ip or not mask:
                 return jsonify({"error": "IP and Mask required"}), 400

            prefix = sum(bin(int(x)).count('1') for x in mask.split('.'))
            cidr = f"{ip}/{prefix}"

            cmds.extend(["ipv4.method", "manual"])
            cmds.extend(["ipv4.addresses", cidr])
            
            if gateway and gateway.strip():
                cmds.extend(["ipv4.gateway", gateway.strip()])
            else:
                cmds.extend(["ipv4.gateway", ""])

            if dns and dns.strip():
                cmds.extend(["ipv4.dns", dns.strip()])
            else:
                cmds.extend(["ipv4.dns", ""])

        # BƯỚC 2: Lưu cấu hình
        print(f"Executing on {conn_name}: {' '.join(cmds)}")
        subprocess.run(cmds, check=True, capture_output=True, text=True)

        # BƯỚC 3: Kích hoạt
        # Down/Up để áp dụng
        subprocess.run(["nmcli", "con", "down", conn_name], check=True)
        subprocess.run(["nmcli", "con", "up", conn_name], check=True)
        
        time.sleep(2)
        
        return jsonify(get_interface_details(iface_name)), 200

    except subprocess.CalledProcessError as e:
        err = e.stderr if e.stderr else str(e)
        print(f"NMCLI Error: {err}")
        return jsonify({"error": "Failed", "details": err}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
