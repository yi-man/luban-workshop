"""NTP 时间同步工具"""

import asyncio
import socket
import struct
import time
from dataclasses import dataclass

from tools.glm_coding_bot.utils.logger import get_logger

logger = get_logger(__name__)

NTP_SERVER = "ntp.aliyun.com"
NTP_PORT = 123
NTP_PACKET_FORMAT = "!12I"
NTP_DELTA = 2208988800  # 1970-01-01 vs 1900-01-01


@dataclass
class TimeSyncResult:
    success: bool
    offset_ms: float = 0.0
    error: str = ""


class TimeSync:
    async def sync(self) -> TimeSyncResult:
        loop = asyncio.get_event_loop()
        try:
            offset = await loop.run_in_executor(None, self._get_ntp_offset)
            return TimeSyncResult(success=True, offset_ms=offset)
        except Exception as e:
            logger.warning(f"NTP sync failed: {e}")
            return TimeSyncResult(success=False, error=str(e))

    def _get_ntp_offset(self) -> float:
        msg = b"\x1b" + 47 * b"\0"
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(5)
            sock.connect((NTP_SERVER, NTP_PORT))
            t0 = time.time()
            sock.send(msg)
            data = sock.recv(48)
            t3 = time.time()

        unpacked = struct.unpack(NTP_PACKET_FORMAT, data[:48])

        transmit_secs = unpacked[10]
        transmit_frac = unpacked[11]
        if transmit_secs == 0:
            raise ValueError("NTP server returned zero transmit timestamp")

        t1 = unpacked[8] - NTP_DELTA + unpacked[9] / 1e9
        t2 = transmit_secs - NTP_DELTA + transmit_frac / 1e9
        offset = ((t1 - t0) + (t2 - t3)) / 2
        return offset * 1000


async def sync_time() -> bool:
    result = await TimeSync().sync()
    if result.success:
        logger.info(f"NTP offset: {result.offset_ms:+.2f} ms")
    return result.success
