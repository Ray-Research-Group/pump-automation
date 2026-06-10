from new_era import NewEraNetwork

network = NewEraNetwork('COM7')

for addr in range(10):
    try:
        pump = network.add_pump(addr)
        ver = pump._send('VER')
        
        # Only count it as real if firmware string actually has content
        firmware = ver.get('data', '').strip()
        status = ver.get('status', '')
        
        if firmware and len(firmware) > 3:
            print(f"✓ REAL pump at address {addr} | Firmware: {firmware} | Status: {status}")
        else:
            print(f"✗ Address {addr}: no real response (ghost)")
            
    except Exception as e:
        print(f"✗ Address {addr}: exception — {e}")

network.close()