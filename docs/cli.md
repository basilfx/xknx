---
layout: default
title: Command Line Interface
nav_order: 5
---

# [](#header-1)Command Line Interface

**Experimental.** `xknx.cli` is a command line interface for interacting with 
devices on a KNX bus without writing any Python. It is installed alongside the
library and registered as the `xknx` console script. Its API should be
considered experimental and may change in a future release.

The command line interface will not nearly be as full-featured as the Python
API, but it can be useful for quickly interacting with KNX devices.

```bash
xknx --help
```

## [](#header-2)Connection options

How to connect to the bus is configured with flags on the top-level `xknx`
command arguments. Every flag also has a matching `XKNX_*` environment
variable, so a connection can be configured once and reused across invocations.
This can be useful for scripting purposes.

```bash
xknx --connection tunneling --gateway-ip 10.1.0.40 group-value read 1/2/3

# Is equivalent to:
XKNX_CONNECTION=tunneling XKNX_GATEWAY_IP=10.1.0.40 xknx group-value read 1/2/3
```

- `--connection {automatic,routing,tunneling,tunneling-tcp}` - how to reach
  the bus. `automatic` (the default) scans the network for a gateway.
- `--secure` - use KNX Secure. Only valid together with
  `--connection=routing` or `--connection=tunneling-tcp`.
- `--individual-address` - our own source address on the bus.
- `--gateway-ip` / `--gateway-port` - IP/hostname and port of a specific
  KNX/IP device (`tunneling`/`tunneling-tcp`).
- `--local-ip` / `--local-port` - local IP or interface, and port, to bind to.
- `--route-back` - for UDP tunneling behind NAT.
- `--multicast-group` / `--multicast-port` - for `routing`.
- `--backbone-key`, `--user-id`, `--user-password`,
  `--device-authentication-password` - KNX Secure credentials.
- `--knxkeys-file` / `--knxkeys-password` - load secure credentials (and,
  for `automatic`, the tunnel endpoint) from a `.knxkeys` file.
- `--debug` - enable debug logging.

Commands that talk to a device or scan the network (e.g. `device info`,
`gateway scan`) print a short status line ("Requesting information from
1.1.1...") to stderr before waiting on the bus, so stdout stays clean for
scripting while you still get feedback that something is happening.

## [](#header-2)Group addresses

```bash
# Send a GroupValueRead and print the (decoded) response.
xknx group-value read 5/1/20 --dpt temperature
xknx group-value read 5/1/20                    # prints the raw payload if --dpt is omitted

# Send a GroupValueWrite.
xknx group-value write 1/1/1 on --dpt switch
xknx group-value write 1/1/1 1                  # raw int/hex payload if --dpt is omitted

# Live telegram monitoring, optionally filtered - runs until Ctrl+C.
xknx monitor
xknx monitor --filter "1/2/*,1/4/[5-6]"
```

## [](#header-2)Interface object properties

Properties are addressed by interface object index (`0` is the device
object, the default) and property id - either a
`ResourceGenericPropertyId`/`ResourceDevicePropertyId` name or a raw integer.

```bash
xknx property-value read 1.1.1 PID_SERIAL_NUMBER
xknx property-value read 1.1.1 12 --object-index 0 --count 1 --start-index 1
xknx property-value write 1.1.1 PID_DEVICE_CONTROL aa    # DATA is a hex string
```

## [](#header-2)Raw memory

ADDRESS is a decimal or 0x-prefixed hex integer (0-0xffff). `memory read`
prints the result as an `xxd`-style hex dump (offset, hex bytes, ASCII):

```bash
$ xknx memory read 1.1.1 0x60 --count 20
00000060: 4142 4344 4546 4748 494a 4b4c 4d4e 4f50  ABCDEFGHIJKLMNOP
00000070: 5152 5354                                QRST

xknx memory write 1.1.1 0x60 aabbccdd    # DATA is a hex string
```

## [](#header-2)Devices

```bash
xknx device restart 1.1.1
xknx device info 1.1.1        # manufacturer id, serial number, mask version
xknx device discover          # find the device currently in programming mode

# Blink a device's programming LED for --timeout seconds, to identify it physically.
xknx device flash 1.1.1 --timeout 10

# Check whether an individual address is already occupied on the bus. Exits 0
# if it's available, 1 if occupied - usable directly in shell conditionals.
xknx device address check 1.1.5

# Load a new individual address onto the device currently in programming mode.
xknx device address load 1.1.5

# Or address a specific device directly by its 6-byte serial number - no
# programming mode needed. Accepts the same 'xx:xxxxxx' form `device info` prints.
xknx device address load 1.1.5 --serial-number aa:bbccddeeff

# Unload (reset to the factory default 15.15.255) - same targeting rules apply.
xknx device address unload
xknx device address unload --serial-number aa:bbccddeeff
```

## [](#header-2)Gateway discovery

```bash
xknx gateway scan
```

## [](#header-2)Shell completion

`xknx completion {bash,zsh,fish}` prints a completion script for the given
shell. For zsh, add this to `~/.zshrc`:

```bash
eval "$(xknx completion zsh)"
```
