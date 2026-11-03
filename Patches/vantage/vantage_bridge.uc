// SPDX-License-Identifier: GPL-3.0-or-later
// Read the software FDB without invoking the RTL9303 hardware table dump.
'use strict';
import { lsdir, readfile } from 'fs';

const MAC_BYTES = 6;
const PORT_LOW = 6, LOCAL = 7, AGE = 8, PORT_HIGH = 12;
const BYTE_BASE = 256, AGE_BYTES = 4;
const NUD_REACHABLE = 2, NUD_NOARP = 64;

function device(name) {
	return type(name) == 'string' && match(name, /^[A-Za-z0-9_.-]{1,15}$/);
}

function port_names(path) {
	let names = lsdir(path + '/brif');
	if (names == null)
		die('Vantage: cannot list bridge ports: ' + path);
	let ports = {};
	for (let name in filter(names, device)) {
		let number = trim(readfile(path + '/brif/' + name + '/port_no') ?? '');
		if (!match(number, /^0x[0-9a-fA-F]{1,4}$/))
			die('Vantage: invalid bridge port number: ' + path + '/brif/' + name);
		ports[hex(substr(number, 2))] = name;
	}
	return ports;
}

function byte_order() {
	let elf = readfile('/proc/self/exe', 6);
	if (substr(elf, 0, 4) != '\x7fELF' || !(ord(elf, 5) in [1, 2]))
		die('Vantage: cannot determine native FDB byte order');
	return ord(elf, 5);
}

function neighbor(bytes, offset, context) {
	let port = ord(bytes, offset + PORT_LOW) + BYTE_BASE * ord(bytes, offset + PORT_HIGH);
	if (ord(bytes, offset + LOCAL) || (ord(bytes, offset) & 1) || !context.ports[port])
		return null;
	let mac_bytes = [];
	for (let i = 0; i < MAC_BYTES; i++)
		push(mac_bytes, sprintf('%02x', ord(bytes, offset + i)));
	let mac = join(':', mac_bytes);
	let age = 0;
	for (let i = 0; i < AGE_BYTES; i++) {
		let index = context.order == 1 ? AGE_BYTES - 1 - i : i;
		age = age * BYTE_BASE + ord(bytes, offset + AGE + index);
	}
	// brforward has no VLAN ID or static bit. Zero age is ambiguous.
	return { lladdr: mac, dev: context.ports[port], master: context.bridge,
		vlan: null, flags: 0, state: age ? NUD_REACHABLE : NUD_NOARP,
		cacheinfo: { updated: age } };
}

function read_bridge_fdb(net, limit, entry_size) {
	let names = lsdir(net);
	if (names == null)
		die('Vantage: cannot list network devices: ' + net);
	let out = [], left = limit * entry_size, order = byte_order();
	for (let bridge in filter(names, device)) {
		let path = net + '/' + bridge;
		if (lsdir(path + '/bridge') == null)
			continue;
		let bytes = readfile(path + '/brforward', left);
		if (type(bytes) != 'string' || length(bytes) % entry_size)
			die('Vantage: unreadable or truncated software FDB: ' + path);
		left -= length(bytes);
		if (left <= 0)
			return null; // Preserve the upstream flooded-bridge response.
		let context = { bridge, order, ports: port_names(path) };
		for (let offset = 0; offset < length(bytes); offset += entry_size) {
			let entry = neighbor(bytes, offset, context);
			if (entry)
				push(out, entry);
		}
	}
	return out;
}

export { read_bridge_fdb };
