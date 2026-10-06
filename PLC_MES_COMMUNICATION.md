# TÀI LIỆU KỸ THUẬT: ĐA GIAO THỨC TRUYỀN THÔNG PLC & MES TRONG NHÀ MÁY SẢN XUẤT LỐP XE
### *Đặc tả 5 Giao thức Công Nghiệp: OPC-UA, OPC-DA (DCOM), Modbus TCP, MQTT (Sparkplug B), và TCP/IP Raw Socket*
### *Tác giả: Kỹ sư MES với 10 năm kinh nghiệm trong ngành sản xuất lốp xe (ISA-95 Level 3 MOM)*

---

## 1. TỔNG QUAN KIẾN TRÚC ĐA GIAO THỨC (HETEROGENEOUS OT/IT NETWORKS)

Trong một nhà máy sản xuất lốp xe quy mô lớn, **không bao giờ có một giao thức duy nhất** có thể bao quát toàn bộ dây chuyền. Lý do xuất phát từ sự đa dạng của các thế hệ máy móc (Legacy vs. Modern), xuất xứ thiết bị (Đức, Nhật, Mỹ, Ý) và đặc thù xử lý thời gian thực:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                      TIRE-MES APPLICATION SERVER (ISA-95 LEVEL 3)                      │
│                           FastAPI Industrial Backend Gateway                           │
└───────────▲────────────────────▲───────────────────▲──────────────────▲────────────────▲──┘
            │                    │                   │                  │                │
     1. OPC-UA            2. OPC-DA           3. MODBUS TCP         4. MQTT       5. TCP SOCKET
     (Port 4840)          (Port 135)            (Port 502)        (Port 1883)      (Port 2001)
            │                    │                   │                  │                │
            ▼                    ▼                   ▼                  ▼                ▼
     [ Máy Đóng Lốp ]     [ Máy Luyện Kín ]   [ Nồi Hơi & Van ]   [ Cảm Biến IIoT ] [ Đầu Đọc & Cân ]
     VMI MAXX Uni-Stage   Kobe Steel Banbury  Platen Steam 15 bar Độ rung ổ bi 270L  Cognex DataMan
     Siemens S7-1500      Kepware DCOM WinCC  Omron / Yokogawa    Đồng hồ đo điện    Mettler Toledo
```

---

## 2. BẢNG SO SÁNH MA TRẬN 5 LOẠI GIAO THỨC CÔNG NGHIỆP

| Tiêu chí | 1. OPC-UA | 2. OPC-DA (Classic) | 3. Modbus TCP | 4. MQTT (Sparkplug B) | 5. TCP/IP Socket |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Mô hình kết nối** | Client / Server (Subscription) | Client / Server (COM/DCOM) | Master / Slave (Poll/Response) | Publish / Subscribe (Broker) | Peer-to-Peer Stream |
| **Cổng mặc định** | `4840` (`opc.tcp://`) | `135` (RPC Dynamic Ports) | `502` | `1883` (hoặc `8883` TLS) | Tuỳ biến (e.g. `2001`, `5000`) |
| **Bảo mật (Security)** | Rất cao (X.509 Certs, TLS) | Kém (Phụ thuộc Windows DCOM) | Không có (Bảo vệ bằng VLAN) | Rất cao (TLS, User/Pass, ACL) | Tự cấu hình |
| **Độ trễ / Chu kỳ** | 10ms - 50ms | 50ms - 200ms | 20ms - 100ms | 50ms - 500ms | Siêu nhanh (< 5ms) |
| **Cấu trúc dữ liệu** | Hướng đối tượng (Nodes/Objects) | Danh sách Tag phẳng (Items) | Địa chỉ thanh ghi (Registers) | JSON / Google Protobuf | Chuỗi ASCII / Byte thuần |
| **Ứng dụng trong xưởng lốp**| Máy đóng lốp VMI, Lò Herbert 63.5", Robot gắp lốp | Máy luyện Banbury cũ, Máy đùn Triplex, Scada WinCC | Trạm cấp hơi nóng 15 bar, Bộ điều khiển nhiệt khuôn | Cảm biến rung động ổ bi máy luyện, Đo điện năng | Đầu đọc mã vạch Cognex, Đầu cân lốp sống Mettler |

---

## 3. CHI TIẾT 5 LOẠI GIAO THỨC & MÃ NGUỒN TRIỂN KHAI THỰC TẾ

---

### GIAO THỨC 1: OPC-UA (Open Platform Communications Unified Architecture)
#### Đặc tính kỹ thuật:
* **Tiêu chuẩn**: IEC 62541, đa nền tảng (chạy trên cả Linux, Windows, RTOS).
* **Cơ chế**: Sử dụng cơ chế `MonitoredItem` và `Subscription`. PLC chỉ đẩy dữ liệu khi có sự thay đổi vượt qua ngưỡng biên chết (Deadband), giúp giảm 90% tải mạng so với Polling liên tục.
* **Mã hóa**: Hỗ trợ thuật toán mã hóa `Basic256Sha256` hoặc `Aes128_Sha256_RsaOaep`.
* **Ứng dụng nhà máy lốp**: Máy đóng lốp hiện đại VMI MAXX, Harburg-Freudenberger (HF), lò lưu hóa Herbert điều khiển bằng PLC Siemens S7-1500 / Beckhoff TwinCAT.

#### Mã nguồn Python (`asyncua`):
```python
import asyncio
from asyncua import Client, ua

class OPCUA_TireConnector:
    def __init__(self, endpoint="opc.tcp://192.168.1.50:4840"):
        self.endpoint = endpoint
        self.client = Client(url=self.endpoint)

    async def connect(self):
        # Thiết lập bảo mật X.509 nếu cần
        await self.client.connect()
        print(f"[OPC-UA] Đã kết nối thành công tới {self.endpoint}")

    async def read_curing_telemetry(self):
        """Đọc thông số nhiệt độ khuôn và áp suất bàng bọng hộc trái"""
        temp_node = self.client.get_node("ns=2;s=CuringPress01.CavityL.MoldTemp")
        press_node = self.client.get_node("ns=2;s=CuringPress01.CavityL.BladderPress")
        
        temp_val = await temp_node.read_value()
        press_val = await press_node.read_value()
        return {"mold_temp_c": round(temp_val, 1), "bladder_press_bar": round(press_val, 1)}

    async def write_poka_yoke_permit(self, permit: bool):
        """Khóa hoặc mở khóa an toàn cho phép máy đóng lốp hoạt động"""
        permit_node = self.client.get_node("ns=2;s=TBM01.Safety.PokaYokePermitStart")
        dv = ua.DataValue(ua.Variant(permit, ua.VariantType.Boolean))
        await permit_node.write_value(dv)
        print(f"[OPC-UA] Ghi Poka-Yoke Permit = {permit}")
```

---

### GIAO THỨC 2: OPC-DA (OPC Data Access Classic - DCOM)
#### Đặc tính kỹ thuật:
* **Tiêu chuẩn**: Microsoft OLE/COM/DCOM trên hệ điều hành Windows (OPC DA 2.05a, 3.0).
* **Đặc thù**: Cực kỳ phổ biến trong các nhà máy lốp xe xây dựng trước năm 2015. Các phần mềm SCADA như Wonderware InTouch, Siemens WinCC v7, GE iFIX hay Kepware KEPServerEX v5 đều sử dụng OPC-DA.
* **Khó khăn thực tế của Kỹ sư MES**: DCOM Security rất phức tạp (lỗi `0x80070005 Access Denied` do phân quyền người dùng Windows, firewall chặn các dynamic RPC port ngoài port 135).
* **Ứng dụng nhà máy lốp**: Kết nối hệ thống trộn kín Banbury 270L Kobe Steel, dây chuyền cán tráng mành Comerio Ercole cũ.

#### Mã nguồn Python (`OpenOPC-Python3` / `win32com`):
```python
import OpenOPC

class OPCDA_ClassicConnector:
    def __init__(self, server_name="Kepware.KEPServerEX.V5", host="192.168.1.10"):
        self.opc = OpenOPC.client()
        self.server_name = server_name
        self.host = host

    def connect(self):
        self.opc.connect(self.server_name, self.host)
        print(f"[OPC-DA DCOM] Kết nối thành công máy chủ {self.server_name} tại {self.host}")

    def read_banbury_mixer(self):
        """Đọc độ nhớt Mooney ML(1+4) và nhiệt độ xả mẻ cao su Banbury"""
        tags = [
            'Banbury01.Batch.MooneyViscosity',
            'Banbury01.Mixer.DumpTemperature',
            'Banbury01.HydraulicRam.Pressure'
        ]
        results = self.opc.read(tags)
        # Kết quả trả về: (value, quality, timestamp)
        return {
            "mooney": results[0][0],
            "dump_temp_c": results[1][0],
            "ram_pressure_bar": results[2][0],
            "quality": results[0][1] # 192 = Good
        }

    def disconnect(self):
        self.opc.close()
```

---

### GIAO THỨC 3: MODBUS TCP (Industrial Register Mapping)
#### Đặc tính kỹ thuật:
* **Tiêu chuẩn**: Schneider Electric Modbus Organization (Port 502).
* **Cơ chế**: Dựa trên địa chỉ thanh ghi 16-bit:
  - `Coils` (00001 - 09999): Đọc/ghi 1-bit boolean (On/Off van, còi).
  - `Discrete Inputs` (10001 - 19999): Đọc 1-bit trạng thái cảm biến.
  - `Input Registers` (30001 - 39999): Đọc 16-bit thanh ghi chỉ đọc (cảm biến analog).
  - `Holding Registers` (40001 - 49999): Đọc/ghi 16-bit (nhiệt độ setpoint, áp suất).
* **Ứng dụng nhà máy lốp**: Các cụm thiết bị phụ trợ (Utility) như nồi hơi cấp Platen Steam 15 bar, cụm làm lạnh Chiller giải nhiệt bàng bọng, bộ điều chỉnh nhiệt Omron/Yokogawa gắn trên lò lưu hóa cơ khí.

#### Bảng Ánh Xạ Thanh Ghi (Modbus Register Map) Lò Lưu Hóa:
| Địa chỉ | Tên tham số | Kiểu dữ liệu | Hệ số tỉ lệ (Scale) | Đơn vị |
| :--- | :--- | :--- | :--- | :--- |
| `40001` | Nhiệt độ khuôn thực tế | 16-bit Signed INT | $\times 0.1$ | °C ($1702 \rightarrow 170.2$ °C) |
| `40002` | Áp suất bàng bọng thực tế | 16-bit Signed INT | $\times 0.1$ | bar ($210 \rightarrow 21.0$ bar) |
| `40003` | Áp suất hơi vòm platen | 16-bit Signed INT | $\times 0.1$ | bar ($151 \rightarrow 15.1$ bar) |
| `00001` | Lệnh van xả khí bàng bọng | Coil Boolean | 1 = Open, 0 = Close | On/Off |

#### Mã nguồn Python (`pymodbus`):
```python
from pymodbus.client import ModbusTcpClient

class ModbusTCP_TireConnector:
    def __init__(self, host="192.168.1.60", port=502):
        self.client = ModbusTcpClient(host=host, port=port)

    def read_press_sensors(self, unit_id=1):
        if not self.client.connect():
            raise ConnectionError("Không thể kết nối trạm Modbus TCP")

        # Đọc 3 thanh ghi Holding từ địa chỉ 40001 (offset 0)
        response = self.client.read_holding_registers(address=0, count=3, slave=unit_id)
        if response.isError():
            return None

        # Giải mã và nhân hệ số tỉ lệ 0.1
        mold_temp = response.registers[0] * 0.1
        bladder_press = response.registers[1] * 0.1
        steam_press = response.registers[2] * 0.1

        return {
            "mold_temp_c": round(mold_temp, 1),
            "bladder_press_bar": round(bladder_press, 1),
            "steam_press_bar": round(steam_press, 1)
        }

    def write_exhaust_valve_coil(self, open_valve: bool, unit_id=1):
        """Điều khiển cuộn coil số 1 mở van xả khí bàng lưu hóa"""
        self.client.write_coil(address=0, value=open_valve, slave=unit_id)
```

---

### GIAO THỨC 4: MQTT (Message Queuing Telemetry Transport & Sparkplug B)
#### Đặc tính kỹ thuật:
* **Tiêu chuẩn**: ISO/IEC 20922, OASIS Sparkplug B cho công nghiệp.
* **Mô hình**: Publish/Subscribe qua Broker trung tâm (Mosquitto, HiveMQ, EMQX).
* **Đặc tính**: Header cực kỳ nhẹ (chỉ 2 bytes), hoạt động ổn định trên băng thông yếu hoặc mạng không dây công nghiệp (Industrial Wi-Fi, 5G Private).
* **Chuẩn Sparkplug B**: Bổ sung State Management (Birth Certificate `NBIRTH`, Death Certificate `NDEATH`) để MES biết chính xác khi nào thiết bị ngoại vi bị mất kết nối đột ngột.
* **Ứng dụng nhà máy lốp**: Giám sát bảo trì dự đoán (PdM): cảm biến độ rung không dây đo gia tốc ổ bi máy luyện Banbury, cảm biến giám sát tiêu thụ điện năng/năng lượng hơi nhiệt trên toàn phân xưởng.

#### Cấu trúc Topic Cây Nhà Máy:
`tireplant/{khu_vực}/{mã_thiết_bị}/telemetry`
Ví dụ: `tireplant/mixing/bb01/bearing_vibration`

#### Mã nguồn Python (`paho-mqtt`):
```python
import json
import paho.mqtt.client as mqtt

class MQTT_IIoTConnector:
    def __init__(self, broker="192.168.1.80", port=1883):
        self.broker = broker
        self.port = port
        self.client = mqtt.Client(client_id="TIRE_MES_SUBSCRIBER")

    def on_connect(self, client, userdata, flags, rc):
        print(f"[MQTT] Đã kết nối Broker với mã phản hồi: {rc}")
        # Đăng ký nhận toàn bộ telemetry rung động và năng lượng
        client.subscribe("tireplant/+/+/telemetry")

    def on_message(self, client, userdata, msg):
        payload_str = msg.payload.decode('utf-8')
        telemetry = json.loads(payload_str)
        print(f"[MQTT Nhận] Topic: {msg.topic} -> Data: {telemetry}")
        # MES đẩy vào CSDL phục vụ bảo trì dự đoán

    def start_listening(self):
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_start()
```

---

### GIAO THỨC 5: RAW TCP/IP SOCKET (Custom ASCII / Byte Stream)
#### Đặc tính kỹ thuật:
* **Giao thức**: Native TCP Socket (`socket.SOCK_STREAM`) hoặc Serial-over-Ethernet (RS-232/RS-485 via Moxa Device Server).
* **Cơ chế**: Gửi nhận dòng ký tự phân cách bằng mã điều khiển tiêu chuẩn ASCII:
  - `<STX>` (Start of Text - `0x02`)
  - `<ETX>` (End of Text - `0x03`)
  - `<CR><LF>` (Carriage Return & Line Feed - `\r\n`)
* **Đặc tính**: Tốc độ xử lý tức thì (< 2ms), cấu hình đơn giản, không cần cài đặt driver hay server trung gian.
* **Ứng dụng nhà máy lốp**:
  - **Đầu đọc mã vạch công nghiệp (Cognex DataMan 370 / Keyence SR-2000)** tại trạm máy đóng lốp TBM.
  - **Đầu cân điện tử (Mettler Toledo IND570 / IND780)** cân trọng lượng lốp sống.
  - **Máy soi X-Ray và Cân bằng động UF**: Gửi chuỗi kết quả đo sau khi kết thúc chu trình quay lốp.

#### Định dạng Gói Tin ASCII Mẫu:
```text
<STX>ID=COG-TBM01;BARCODE=GT-20261006-0019;WEIGHT=9.28;RESULT=PASS<ETX>
```

#### Mã nguồn Python (`asyncio` Socket Server):
```python
import asyncio

class TCPSocket_IndustrialListener:
    def __init__(self, host="0.0.0.0", port=2001):
        self.host = host
        self.port = port

    async def handle_scanner_stream(self, reader, writer):
        addr = writer.get_extra_info('peername')
        print(f"[TCP Socket] Thiết bị đã kết nối từ: {addr}")

        while True:
            # Đọc dữ liệu đến khi gặp ký tự xuống dòng \n hoặc <ETX>
            data = await reader.readuntil(b'\n')
            if not data:
                break

            raw_msg = data.decode('utf-8').strip('\r\n\x02\x03')
            print(f"[TCP Nhận Từ Đầu Đọc Mã Vạch]: {raw_msg}")

            # Phân tách gói tin dạng: BARCODE=GT-20261006-0019;WEIGHT=9.28
            tokens = dict(part.split('=') for part in raw_msg.split(';') if '=' in part)
            barcode = tokens.get('BARCODE')
            weight = float(tokens.get('WEIGHT', 0.0))

            # Trả về tín hiệu ACK cho đầu đọc
            writer.write(b"<STX>ACK;MES_STATUS=OK<ETX>\n")
            await writer.drain()

    async def start_server(self):
        server = await asyncio.start_server(self.handle_scanner_stream, self.host, self.port)
        print(f"[TCP Socket Server] Đang lắng nghe tại cổng {self.port}...")
        async with server:
            await server.serve_forever()
```

---

## 4. GIAO DIỆN QUẢN TRỊ TRÊN MINI APP TIRE-MES (TAB 8)

Để phục vụ quản trị và kiểm thử trực quan, Mini App TIRE-MES đã tích hợp **Tab 8: Cổng Giao Thức PLC & IIoT** trên Web Dashboard:

1. **5 Thẻ Giám Sát Cổng Kết Nối**:
   - `CONN-OPC-UA`: Kết nối Siemens S7-1500 / VMI MAXX (Port 4840).
   - `CONN-OPC-DA`: Kết nối Kepware DCOM Classic (Port 135).
   - `CONN-MODBUS-TCP`: Kết nối Steam Boiler & Cụm van nhiệt Platen (Port 502).
   - `CONN-MQTT`: Kết nối Broker IIoT đo rung động Banbury (Port 1883).
   - `CONN-TCP-SOCKET`: Lắng nghe đầu đọc Cognex & cân Mettler Toledo (Port 2001).
2. **Nút "⚡ Test Handshake (Ping)"**:
   - Gửi yêu cầu kiểm tra bắt tay thực tế qua API `/api/gateway/test-ping`.
   - In ra nhật ký chi tiết quá trình bắt tay (TCP SYN ➔ Hello ➔ Session Create ➔ Read Tags) và tính toán độ trễ vòng lặp (Latency tính bằng milli-giây).
3. **Nút "📡 Gửi Gói Tin Mẫu (Packet Simulation)"**:
   - Gửi gói tin công nghiệp mẫu qua API `/api/gateway/simulate-packet`.
   - Hiển thị cấu trúc giải mã của MES (Decoded Object) và chỉ rõ trường dữ liệu trong CSDL được cập nhật.

---

## 5. KẾT LUẬN & KHUYẾN NGHỊ DÀNH CHO KỸ SƯ MES

1. **Đối với máy đóng lốp & lò lưu hóa mới**: Luôn ưu tiên chuẩn **OPC-UA** vì tính bảo mật cao, khả năng truyền dữ liệu có cấu trúc và không phụ thuộc vào hệ điều hành.
2. **Đối với các máy trộn cũ & Scada thế hệ trước**: Sử dụng phần mềm trung gian như **Kepware KEPServerEX** để chuyển đổi từ **OPC-DA** sang **OPC-UA**, tránh việc MES phải giao tiếp qua DCOM tiềm ẩn rủi ro bảo mật.
3. **Đối với hệ thống phụ trợ (Hơi nước, khí nén, nhiệt độ)**: Sử dụng **Modbus TCP** vì độ tin cậy cực cao, chi phí thiết bị rẻ và dễ bảo trì.
4. **Đối với cảm biến thông minh & giám sát năng lượng**: Sử dụng **MQTT Sparkplug B** để tiết kiệm băng thông mạng công xưởng và tích hợp dễ dàng lên nền tảng Cloud.
5. **Đối với thiết bị quét mã vạch & đầu cân tại trạm**: Sử dụng **TCP/IP Socket** trực tiếp để đạt tốc độ phản hồi gần như tức thời (< 5ms), đảm bảo nhịp đóng lốp không bị gián đoạn.

---
*Tài liệu được bảo tồn vĩnh viễn trong kho mã nguồn dự án: `c:\Users\Tuan\Downloads\MES\PLC_MES_COMMUNICATION.md`.*
