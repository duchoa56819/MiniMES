"""
Industrial Protocol Gateway Router.
Manages and simulates connectors for OPC-UA, OPC-DA, Modbus TCP, MQTT, and TCP/IP Socket.
Senior MES Engineer Implementation.
"""

import random
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import get_db

router = APIRouter(prefix="/api/gateway", tags=["Protocol Gateway"])


class PingRequest(BaseModel):
    connector_id: str


class PacketSimRequest(BaseModel):
    connector_id: str
    custom_value: str = ""


@router.get("/connectors")
def list_connectors():
    """Returns all configured industrial protocol connectors."""
    with get_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute("SELECT * FROM gateway_connectors ORDER BY connector_id ASC").fetchall()
        return [dict(r) for r in rows]


@router.post("/test-ping")
def test_connector_ping(req: PingRequest):
    """Simulates/executes a ping and handshake check for an industrial connector."""
    with get_db() as conn:
        cursor = conn.cursor()
        conn_row = cursor.execute("SELECT * FROM gateway_connectors WHERE connector_id = ?", (req.connector_id,)).fetchone()
        if not conn_row:
            raise HTTPException(status_code=404, detail="Không tìm thấy cổng kết nối giao thức!")

        c = dict(conn_row)
        proto = c["protocol_type"]

        # Realistic simulated latency based on protocol type
        base_latency = {
            "OPC_UA": 8.5,
            "OPC_DA": 16.2,
            "MODBUS_TCP": 10.4,
            "MQTT": 19.8,
            "TCP_SOCKET": 3.8
        }.get(proto, 10.0)

        jitter = round(base_latency + random.uniform(-1.5, 2.5), 1)

        # Update last ping in DB
        cursor.execute("""
            UPDATE gateway_connectors
            SET last_ping_ms = ?, status = 'CONNECTED'
            WHERE connector_id = ?
        """, (jitter, req.connector_id))

        handshake_logs = []
        if proto == "OPC_UA":
            handshake_logs = [
                f"[TCP SYN] Connecting to {c['endpoint_url']}...",
                f"[OPC-UA Hello] Server acknowledged protocol version 1.04",
                f"[Security Token] None / Basic256Sha256 Channel activated (TokenID: 0x48A1)",
                f"[CreateSession] Session 'TIRE_MES_CLIENT_01' established successfully",
                f"[Handshake OK] Latency: {jitter}ms"
            ]
        elif proto == "OPC_DA":
            handshake_logs = [
                f"[DCOM RPC] Connecting via Port 135 to Windows Host...",
                f"[IOPCServer] CoCreateInstanceEx on {c['endpoint_url']} successful",
                f"[Group Add] Group 'TIRE_MES_SUBSCRIPTION' created (UpdateRate: 1000ms)",
                f"[Item Validate] Validated 24 tags on Kepware Server",
                f"[Handshake OK] Latency: {jitter}ms"
            ]
        elif proto == "MODBUS_TCP":
            handshake_logs = [
                f"[Socket Connect] TCP socket open to {c['endpoint_url']}",
                f"[Modbus Tx] [00 01 00 00 00 06 01 03 9C 41 00 03] (Read Regs 40001..40003)",
                f"[Modbus Rx] [00 01 00 00 00 09 01 03 06 06 A6 00 D2 00 97]",
                f"[Decoded] Reg 40001 = 1702 (170.2 C), Reg 40002 = 210 (21.0 bar)",
                f"[Handshake OK] Latency: {jitter}ms"
            ]
        elif proto == "MQTT":
            handshake_logs = [
                f"[MQTT Connect] Broker {c['endpoint_url']} (ClientID: TIRE_MES_EDGE_01)",
                f"[CONNACK] Connection accepted (Return code 0)",
                f"[SUBSCRIBE] Topic: 'tireplant/edge/#' (QoS 1)",
                f"[SUBACK] Granted QoS 1 for telemetry stream",
                f"[Handshake OK] Latency: {jitter}ms"
            ]
        elif proto == "TCP_SOCKET":
            handshake_logs = [
                f"[Socket Open] Direct TCP/IP socket connected to port {c['port']}",
                f"[Heartbeat Tx] <ENQ>",
                f"[Heartbeat Rx] <ACK>",
                f"[Stream Ready] Scanner listening for barcode triggers",
                f"[Handshake OK] Latency: {jitter}ms"
            ]

        return {
            "success": True,
            "connector_id": req.connector_id,
            "protocol_type": proto,
            "latency_ms": jitter,
            "status": "CONNECTED",
            "logs": handshake_logs
        }


@router.post("/simulate-packet")
def simulate_protocol_packet(req: PacketSimRequest):
    """Simulates an incoming industrial packet, decodes it, and maps it to MES data objects."""
    with get_db() as conn:
        cursor = conn.cursor()
        conn_row = cursor.execute("SELECT * FROM gateway_connectors WHERE connector_id = ?", (req.connector_id,)).fetchone()
        if not conn_row:
            raise HTTPException(status_code=404, detail="Không tìm thấy cổng kết nối!")

        c = dict(conn_row)
        proto = c["protocol_type"]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        parsed_data = {}
        if proto == "OPC_UA":
            temp_val = round(170.0 + random.uniform(-0.4, 0.4), 1)
            parsed_data = {
                "source": "Siemens S7-1500 PLC (DB10 / MonitoredItem)",
                "node_id": "ns=2;s=CP01.CavityL.MoldTemp",
                "tag_name": "Mold_Temperature_Actual",
                "engineering_value": f"{temp_val} °C",
                "quality": "Good_Quality (0x00000000)",
                "mes_mapping": "curing_press_cavities.mold_temp_c"
            }
        elif proto == "OPC_DA":
            mooney_val = round(68.0 + random.uniform(-1.0, 1.0), 1)
            parsed_data = {
                "source": "Kobe Steel Banbury BB-270 (Kepware DCOM)",
                "item_id": "Banbury01.Mixer.MooneyViscosity",
                "engineering_value": f"{mooney_val} ML(1+4) 100°C",
                "quality": "192 (Good Quality)",
                "mes_mapping": "Banbury Raw Batch Quality Verification"
            }
        elif proto == "MODBUS_TCP":
            press_val = round(21.0 + random.uniform(-0.2, 0.2), 1)
            parsed_data = {
                "source": "Yokogawa UT35A Steam Pressure Controller",
                "modbus_function": "03 (Read Multiple Holding Registers)",
                "register_address": 40002,
                "raw_register_hex": "0x00D2",
                "engineering_value": f"{press_val} bar",
                "mes_mapping": "curing_press_cavities.bladder_press_bar"
            }
        elif proto == "MQTT":
            vib_val = round(2.3 + random.uniform(-0.2, 0.3), 2)
            parsed_data = {
                "source": "IFM Electronic Wireless Vibration Sensor",
                "mqtt_topic": "tireplant/mixing/bb01/vibration",
                "payload_format": "Sparkplug B / JSON",
                "engineering_value": f"{vib_val} mm/s RMS (Khỏe mạnh)",
                "mes_mapping": "Predictive Maintenance / Machine Health Score"
            }
        elif proto == "TCP_SOCKET":
            barcode_val = req.custom_value or "GT-20261006-0019"
            parsed_data = {
                "source": "Cognex DataMan 370 Barcode Scanner (TBM Line 1)",
                "raw_stream": f"<STX>SCANNER=COG-01;BARCODE={barcode_val};SCALE=9.28KG<ETX>",
                "scanned_barcode": barcode_val,
                "weight_scale_kg": 9.28,
                "mes_mapping": "production_green_tires.gt_barcode (Poka-Yoke Inbound)"
            }

        return {
            "success": True,
            "connector_id": req.connector_id,
            "protocol_type": proto,
            "timestamp": now_str,
            "decoded_object": parsed_data,
            "message": f"Giải mã thành công gói tin công nghiệp từ {proto}!"
        }
