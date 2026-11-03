// Execute the real rpcd plugin with synthetic bridge records, never real netlink.
'use strict';
import { mkdir, writefile, readfile, unlink } from 'fs';

const NET = WORK + '/net';
const FIRST_HOST = '02:00:5e:00:53:21';

function equal(actual, expected, name) {
	if (sprintf('%J', actual) != sprintf('%J', expected))
		die(sprintf('%s: expected %J, got %J', name, expected, actual));
	print('PASS ', name, '\n');
}

function record(mac, port, options) {
	let bytes = map(split(mac, ':'), b => hex(b));
	let age = options.age ?? 250;
	push(bytes, port & 255, options.local ? 1 : 0);
	for (let i = 0; i < 4; i++)
		push(bytes, (age >> (i * 8)) & 255);
	push(bytes, port >> 8, 0, 0, 0);
	return join('', map(bytes, b => chr(b)));
}

function bridge(name, ports) {
	let path = NET + '/' + name;
	mkdir(path); mkdir(path + '/bridge'); mkdir(path + '/brif');
	for (let port, number in ports) {
		mkdir(path + '/brif/' + port);
		writefile(path + '/brif/' + port + '/port_no', sprintf('0x%x\n', number));
	}
	writefile(path + '/brforward', '');
}

function hosts() {
	let source = replace(readfile(PLUGIN), "const NET = '/sys/class/net';", 'const NET = ' + sprintf('%J', NET) + ';');
	writefile(WORK + '/plugin.uc', source);
	return loadfile(WORK + '/plugin.uc', { raw_mode: true })()['luci.vantage'].wired.call();
}

mkdir(NET);
bridge('br-lan', { lan1: 1, lan2: 258 });
bridge('br-guest', { eth2: 3 });
let dynamic = record(FIRST_HOST, 258, {});
writefile(NET + '/br-lan/brforward', dynamic +
	record('02:00:5e:00:53:01', 1, { local: true }) +
	record('01:00:5e:00:53:02', 1, {}) +
	record('02:00:5e:00:53:03', 99, {}));
let reply = hosts();
equal(length(reply.hosts), 1, 'local multicast and removed ports excluded');
equal(reply.hosts[0], { mac: FIRST_HOST, port: 'lan2', bridge: 'br-lan', vlan: null, seen: 2 },
	'learned host high port number and age survive without hardware dump');
writefile(NET + '/br-guest/brforward', record('02:00:5e:00:53:22', 3, { age: 0 }));
reply = hosts();
equal(length(reply.hosts), 2, 'multiple bridges retained');
equal(filter(reply.hosts, h => h.bridge == 'br-guest')[0].seen, null,
	'zero age is unknown because sysfs cannot distinguish static from freshly learned');

let many = '';
for (let i = 0; i < 129; i++)
	many += record(sprintf('02:00:5e:00:54:%02x', i), 1, {});
writefile(NET + '/br-lan/brforward', many);
equal(length(hosts().hosts), 129, 'existing per-port cap does not hide other bridges');
writefile(NET + '/br-lan/brforward', dynamic + 'x');
let error = null;
try { hosts(); } catch (e) { error = e; }
equal(error != null, true, 'truncated FDB is an error not an empty success');

let flooded = '';
for (let i = 0; i < 4096; i++)
	flooded += dynamic;
writefile(NET + '/br-lan/brforward', flooded);
equal(hosts().crowded, true, 'existing flood protection remains active');
writefile(NET + '/br-lan/brforward', '');
writefile(NET + '/br-guest/brforward', '');
equal(length(hosts().hosts), 0, 'genuinely empty FDB returns no hosts');
unlink(NET + '/br-lan/brforward');
error = null;
try { hosts(); } catch (e) { error = e; }
equal(error != null, true, 'unreadable bridge FDB is reported');
