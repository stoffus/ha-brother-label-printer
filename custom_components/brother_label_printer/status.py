"""Read the Brother 32-byte raster status over read-only SNMPv1."""
import asyncio
from .const import TAPES
from pysnmp.hlapi.v1arch.asyncio import CommunityData, SnmpDispatcher, UdpTransportTarget, get_cmd

# Brother raster reference p. 24. The P900W ASCII 'o' is 0x6f;
# the reference's parenthesized 69h is a typo (also verified on a P900Wc).
MODEL_NAMES = {0x71: 'PT-P900', 0x6F: 'PT-P900W', 0x70: 'PT-P950NW', 0x78: 'PT-P910BT'}

STATUS_OID = '1.3.6.1.4.1.2435.3.3.9.1.6.1.0'


def parse_status(raw: bytes) -> dict:
    if len(raw) != 32 or raw[:4] != b'\x80\x20\x42\x30':
        raise ValueError('Invalid Brother status response')
    errors = []
    for offset, flags in ((8, {1: 'No tape', 2: 'End of tape', 4: 'Cutter jam',
                              8: 'Weak battery', 16: 'Printer in use', 64: 'High-voltage adapter'}),
                          (9, {1: 'Wrong media', 2: 'Expansion buffer full', 4: 'Communication error',
                               8: 'Communication buffer full', 16: 'Cover open', 32: 'Overheating',
                               64: 'Black mark not detected', 128: 'System error'})):
        for mask, description in flags.items():
            if raw[offset] & mask:
                errors.append(description)
        if raw[offset] & ~sum(flags):
            errors.append(f'Unknown error flags (byte {offset}: 0x{raw[offset]:02x})')
    if raw[7]:
        errors.append({0x10: 'FLe tape end', 0x1d: 'High-resolution/draft error',
                       0x1e: 'Adapter connection error', 0x21: 'Incompatible media'}.get(
                           raw[7], f'Unknown extended error (0x{raw[7]:02x})'))
    if raw[18] == 2 and not errors:
        errors.append('Printer reported an unspecified error')
    if raw[18] == 5 and raw[22] in (1, 3):
        message = 'Cover open' if raw[22] == 1 else 'Cooling'
        if message not in errors:
            errors.append(message)
    width = 3.5 if raw[10] == 4 else raw[10]
    if raw[18] == 4:
        state = 'powered_off'
    elif errors:
        state = 'error'
    elif not width or not raw[11]:
        state = 'no_tape'
    elif raw[11] != 1 or width not in TAPES:
        state = 'unsupported_tape'
    elif raw[19] == 1 or (raw[19] == 0 and (raw[20] or raw[21])):
        state = 'busy'
    elif raw[19] != 0 or raw[18] not in (0, 1, 5, 6):
        state = 'unknown'
    else:
        state = 'ready'
    return {'model': MODEL_NAMES.get(raw[4], 'Unknown'),
            'model_code': f'0x{raw[4]:02x}', 'tape_width_mm': width,
            'media_type': raw[11], 'error': bool(errors),
            'error_bytes': raw[7:10].hex(), 'errors': errors,
            'printer_status': state, 'ready': state == 'ready',
            'status_type': raw[18], 'phase_type': raw[19]}



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
