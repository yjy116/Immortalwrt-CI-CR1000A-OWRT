"""Exercise the feed backport with the real upstream RPC reader and nft output."""

import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "Tests/fixtures/luci-upnp/luci.upnp"
READER = Path("root/usr/share/rpcd/ucode/luci.upnp")
BASH = os.environ.get("BASH", "bash")
COMMAND_TIMEOUT = 60
TCP_RULE = ('\t\tiif "pppoe-wan" @nh,72,8 0x6 th dport 65432 '
            'counter packets 0 bytes 0 dnat ip to 192.168.10.21:65432 # handle 1469')


def matcher(source):
    line = next(line for line in source.splitlines() if "th dport" in line)
    expression = re.search(r"match\(line, /(.+)/\);", line)
    return re.compile(expression[1])


def make_package(root):
    package = root / "luci-app-upnp"
    reader = package / READER
    reader.parent.mkdir(parents=True)
    shutil.copyfile(FIXTURE, reader)
    (package / "Makefile").write_text("# untouched upstream package\n")
    return package


def prepare(package):
    return subprocess.run(
        [BASH, (REPO / "Scripts/LuciUpnp.sh").as_posix(), package.as_posix()],
        capture_output=True, text=True, timeout=COMMAND_TIMEOUT,
    )


class LuciUpnpTests(unittest.TestCase):
    def test_upstream_fixture_reproduces_counter_regression(self):
        parser = matcher(FIXTURE.read_text())
        self.assertIsNone(parser.match(TCP_RULE))
        self.assertIsNotNone(parser.match(TCP_RULE.replace("counter packets 0 bytes 0 ", "")))

    def test_backport_reads_real_counter_and_legacy_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            package = make_package(Path(directory))
            result = prepare(package)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            parser = matcher((package / READER).read_text())
            cases = (
                (TCP_RULE, ("0x6", "65432", "192.168.10.21", "65432")),
                (TCP_RULE.replace("counter packets 0 bytes 0 ", ""),
                 ("0x6", "65432", "192.168.10.21", "65432")),
                ('  iif "pppoe-wan" @nh,72,8 0x11 th dport 12345 '
                 'counter packets 29 bytes 4000 dnat ip to 192.168.10.60:54321',
                 ("0x11", "12345", "192.168.10.60", "54321")),
            )
            for line, expected in cases:
                with self.subTest(rule=line):
                    matched = parser.match(line)
                    self.assertIsNotNone(matched)
                    self.assertEqual(matched.groups(), expected)
            self.assertIsNone(parser.match('counter packets 0 bytes 0 accept'))
            self.assertIsNone(parser.match(TCP_RULE.replace('0x6', '0x1')))

    def test_only_reader_is_changed_and_second_run_preserves_native_fix(self):
        with tempfile.TemporaryDirectory() as directory:
            package = make_package(Path(directory))
            original = (package / READER).read_text().splitlines()
            recipe = (package / "Makefile").read_bytes()
            result = prepare(package)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            fixed = (package / READER).read_bytes()
            lines = fixed.decode().splitlines()
            self.assertEqual(len(original), len(lines))
            self.assertEqual(sum(a != b for a, b in zip(original, lines)), 1)
            self.assertEqual((package / "Makefile").read_bytes(), recipe)
            first = (package / "ci-luci-upnp-source.txt").read_text()
            self.assertIn("mode=upstream-pr-backport", first)
            self.assertIn(hashlib.sha256(fixed).hexdigest(), first)
            result = prepare(package)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((package / READER).read_bytes(), fixed)
            self.assertIn("mode=native-feed", (package / "ci-luci-upnp-source.txt").read_text())
            self.assertEqual(list(package.rglob("*.rej")), [])
            self.assertEqual(list(package.rglob("*.orig")), [])

    def test_unrecognized_reader_fails_without_replacing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            package = make_package(Path(directory))
            reader = package / READER
            reader.write_text('// changed upstream implementation\n')
            original = reader.read_bytes()
            result = prepare(package)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("review", result.stderr.lower())
            self.assertEqual(reader.read_bytes(), original)
            self.assertFalse((package / "ci-luci-upnp-source.txt").exists())


if __name__ == "__main__":
    unittest.main()
