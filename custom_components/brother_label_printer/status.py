"""Read the Brother 32-byte raster status over read-only SNMPv1."""
import asyncio
from pysnmp.hlapi.v1arch.asyncio import CommunityData, SnmpDispatcher, UdpTransportTarget, get_cmd

# Brother raster reference p. 24. The P900W ASCII 'o' is 0x6f;
# the reference's parenthesized 69h is a typo (also verified on a P900Wc).
MODEL_NAMES = {0x71: 'PT-P900', 0x6F: 'PT-P900W', 0x70: 'PT-P950NW', 0x78: 'PT-P910BT'}

STATUS_OID = '1.3.6.1.4.1.2435.3.3.9.1.6.1.0'


def parse_status(raw: bytes) -> dict:
    if len(raw) != 32 or raw[:4] != b'\x80\x20\x42\x30':
        raise ValueError('Invalid Brother status response')
    return {'model': MODEL_NAMES.get(raw[4], 'Unknown'),
            'model_code': f'0x{raw[4]:02x}',
            'tape_width_mm': 3.5 if raw[10] == 4 else raw[10],
            'media_type': raw[11], 'error': bool(raw[7] or raw[8] or raw[9]),
            'error_bytes': raw[7:10].hex()}


async def read_status(host: str) -> dict:
    dispatcher = SnmpDispatcher()
    try:
        async with asyncio.timeout(5):
            target = await UdpTransportTarget.create((host, 161), timeout=2, retries=0)
            error, status, _, bindings = await get_cmd(
                dispatcher, CommunityData('public', mpModel=0), target,
                (STATUS_OID, None), lookupMib=False)
            if error or status or len(bindings) != 1:
                raise ValueError('Printer status unavailable over SNMP (UDP 161)')
            if str(bindings[0][0]) != STATUS_OID:
                raise ValueError('Unexpected printer status identifier')
            return parse_status(bindings[0][1].asOctets())
    finally:
        dispatcher.close()
