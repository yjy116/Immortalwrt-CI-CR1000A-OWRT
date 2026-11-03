// Reject the slow hardware dump while testing the real plugin against sysfs fixtures.
'use strict';
const C = {
	RTM_GETNEIGH: 30, NLM_F_DUMP: 0x300, AF_BRIDGE: 7,
	NUD_REACHABLE: 2, NUD_NOARP: 64, NUD_PERMANENT: 128, NTF_SELF: 2
};
function request() { die('Regression: dashboard requested a hardware FDB dump'); }
export { request, C as 'const' };
