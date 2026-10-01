"""Testes do AIOS. Rodar: python -m unittest discover -s tests -v

Cada teste de checagem tem o par "estado bom passa / estado quebrado falha", para provar
que a checagem detecta a regressão em vez de passar por omissão.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import threading
import unittest
import urllib.request
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path

from aios import brain, lint, pulse, status, vault
from aios.cron import Cron, CronError
from aios.serve import make_handler

REPO = Path(__file__).resolve().parent.parent


class Workspace(unittest.TestCase):
    """Cópia descartável do repositório para cada teste."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.root = self.tmp / "ws"
        shutil.copytree(REPO, self.root, ignore=shutil.ignore_patterns(".git", "runs", "__pycache__"))
        brain.build(self.root)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


class CronTest(unittest.TestCase):
    def test_basic_fields(self):
        c = Cron.parse("30 7 * * *")
        self.assertTrue(c.matches(datetime(2026, 10, 1, 7, 30)))
        self.assertFalse(c.matches(datetime(2026, 10, 1, 7, 31)))

    def test_weekdays_ranges_steps(self):
        c = Cron.parse("*/15 9-17 * * 1-5")
        self.assertTrue(c.matches(datetime(2026, 10, 1, 9, 45)))  # quinta
        self.assertFalse(c.matches(datetime(2026, 10, 4, 9, 45)))  # domingo
        self.assertFalse(c.matches(datetime(2026, 10, 1, 18, 0)))

    def test_sunday_is_0_and_7(self):
        sunday = datetime(2026, 10, 4, 8, 0)
        self.assertTrue(Cron.parse("0 8 * * 0").matches(sunday))
        self.assertTrue(Cron.parse("0 8 * * 7").matches(sunday))

    def test_dom_or_dow_when_both_restricted(self):
        c = Cron.parse("0 8 1 * 1")  # dia 1 OU segunda
        self.assertTrue(c.matches(datetime(2026, 10, 1, 8, 0)))  # dia 1 (quinta)
        self.assertTrue(c.matches(datetime(2026, 10, 5, 8, 0)))  # segunda
        self.assertFalse(c.matches(datetime(2026, 10, 6, 8, 0)))

    def test_invalid(self):
        for bad in ("* * * *", "60 * * * *", "*/0 * * * *", "a * * * *", "5-1 * * * *"):
            with self.assertRaises(CronError, msg=bad):
                Cron.parse(bad)

    def test_due_between_catches_up_once(self):
        c = Cron.parse("30 7 * * *")
        due = c.due_between(datetime(2026, 10, 1, 6, 0), datetime(2026, 10, 1, 9, 0))
        self.assertEqual(due, datetime(2026, 10, 1, 7, 30))
        self.assertIsNone(c.due_between(datetime(2026, 10, 1, 7, 30), datetime(2026, 10, 1, 9, 0)))


class MemoryTest(Workspace):
    def test_repo_lints_clean(self):
        errors, _ = lint.check(self.root)
        self.assertEqual(errors, [])

    def test_every_note_within_two_hops(self):
        hops = vault.hops_from_root(vault.load(self.root))
        notes = vault.load(self.root)
        self.assertEqual(set(hops), set(notes))
        self.assertLessEqual(max(hops.values()), 2)

    def test_lint_catches_moved_file(self):
        (self.root / "areas/conteudo/guia-de-estilo.md").rename(self.root / "areas/conteudo/estilo.md")
        brain.build(self.root)
        errors, _ = lint.check(self.root)
        self.assertTrue(any("link quebrado" in e and "guia-de-estilo" in e for e in errors), errors)
        self.assertTrue(any("estilo.md: inalcançável" in e for e in errors), errors)

    def test_lint_catches_missing_signpost_and_three_hops(self):
        self.write("areas/nova/nota.md", "---\nsummary: x\n---\n# Nota\n")
        brain.build(self.root)
        errors, _ = lint.check(self.root)
        self.assertTrue(any("areas/nova/ tem notas mas não tem CLAUDE.md" in e for e in errors), errors)
        self.assertTrue(any("não aponta para areas/nova/CLAUDE.md" in e for e in errors), errors)

        self.write("areas/projetos/fundo.md", "---\nsummary: fundo\n---\n# Fundo\n")
        self.write("areas/projetos/ativos.md",
                   (self.root / "areas/projetos/ativos.md").read_text() + "\nVer [[areas/projetos/fundo]]\n")
        brain.build(self.root)
        errors, _ = lint.check(self.root)
        self.assertTrue(any("fundo.md: está a 3 saltos" in e for e in errors), errors)

    def test_lint_catches_stale_map(self):
        self.write("areas/pessoal/nova.md", "---\nsummary: nova\n---\n# Nova\n")
        self.write("areas/pessoal/CLAUDE.md",
                   (self.root / "areas/pessoal/CLAUDE.md").read_text() + "- nova → [[areas/pessoal/nova]]\n")
        errors, _ = lint.check(self.root)
        self.assertTrue(any("MAP.md desatualizado" in e for e in errors), errors)
        brain.build(self.root)
        self.assertEqual(lint.check(self.root)[0], [])

    def test_lint_catches_fat_root(self):
        self.write("CLAUDE.md", (self.root / "CLAUDE.md").read_text() + "fato\n" * 80)
        brain.build(self.root)
        self.assertTrue(any("CLAUDE.md raiz tem" in e for e in lint.check(self.root)[0]))

    def test_map_lists_every_note_with_summary(self):
        text = (self.root / brain.MAP_FILE).read_text()
        self.assertIn("`areas/conteudo/guia-de-estilo.md`", text)
        self.assertIn("palavras proibidas", text)

    def test_graph_connects_routines_and_skills(self):
        g = json.loads((self.root / brain.GRAPH_FILE).read_text())
        ids = {n["id"] for n in g["nodes"]}
        self.assertIn("routine:outreach-pack", ids)
        self.assertIn("skill:interview", ids)
        uses = {(l["source"], l["target"]) for l in g["links"] if l["kind"] == "uses"}
        self.assertIn(("routine:outreach-pack", "areas/trabalho/pipeline.md"), uses)


class FakeClaudeWorkspace(Workspace):
    """Workspace com um `claude` falso no lugar do binário real."""

    def setUp(self):
        super().setUp()
        fake = self.tmp / "fake-claude"
        fake.write_text("#!/bin/sh\necho \"fake claude: $2\" | head -c 80\n")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        os.environ["AIOS_CLAUDE_BIN"] = str(fake)

    def tearDown(self):
        os.environ.pop("AIOS_CLAUDE_BIN", None)
        super().tearDown()


class PulseTest(FakeClaudeWorkspace):
    def test_routines_file_is_valid(self):
        self.assertGreaterEqual(len(pulse.load_routines(self.root)), 5)

    def test_invalid_routine_fails_loudly(self):
        self.write("pulse/routines.toml", '[[routine]]\nname="x"\npurpose="p"\nschedule="99 * * * *"\n'
                   'host="mac"\nkind="claude"\nprompt="pulse/prompts/nao-existe.md"\n')
        with self.assertRaises(ValueError) as ctx:
            pulse.load_routines(self.root)
        self.assertIn("schedule", str(ctx.exception))
        self.assertIn("prompt não encontrado", str(ctx.exception))

    def test_tick_enqueues_only_due_routines_for_this_host(self):
        state = {"routines": {}, "last_tick": "2026-10-01T07:25:00"}
        (self.root / "runs").mkdir(exist_ok=True)
        (self.root / "runs/state-vps.json").write_text(json.dumps(state))
        queued = pulse.tick(self.root, "vps", datetime(2026, 10, 1, 7, 40))
        self.assertEqual(sorted(queued), ["heartbeat", "morning-digest"])  # outreach-pack é 07:00
        self.assertEqual(pulse.tick(self.root, "vps", datetime(2026, 10, 1, 7, 45)), [])
        self.assertEqual(pulse.tick(self.root, "mac", datetime(2026, 10, 1, 7, 40)), [])

    def test_drain_runs_logs_and_records_state(self):
        pulse.enqueue(self.root, kind="routine", name="weekly-review", host="mac", source="test")
        pulse.enqueue(self.root, kind="routine", name="brain-build", host="vps", source="test")
        results = pulse.drain(self.root, "mac")
        self.assertEqual([r["name"] for r in results], ["weekly-review"])
        self.assertEqual(results[0]["status"], "ok")
        self.assertIn("fake claude", results[0]["output_tail"])
        self.assertEqual(len(list((self.root / "runs/queue").glob("*.json"))), 1)  # o da vps ficou
        st = pulse.load_state(self.root, "mac")["routines"]["weekly-review"]
        self.assertEqual((st["status"], st["fails"]), ("ok", 0))

    def test_failing_routine_is_paused_after_cap(self):
        self.write("pulse/routines.toml", '[[routine]]\nname="quebra"\npurpose="p"\nschedule="* * * * *"\n'
                   'host="mac"\nkind="script"\nrun="exit 3"\n')
        for minute in range(1, 6):
            pulse.tick(self.root, "mac", datetime(2026, 10, 1, 8, minute))
            pulse.drain(self.root, "mac")
        st = pulse.load_state(self.root, "mac")["routines"]["quebra"]
        self.assertEqual(st["status"], "exit 3")
        self.assertEqual(st["fails"], 3)  # parou de tentar depois de 3
        pulse.reset(self.root, "mac", "quebra")
        self.assertEqual(pulse.tick(self.root, "mac", datetime(2026, 10, 1, 8, 6)), ["quebra"])

    def test_daily_cap_stops_drain(self):
        self.write("aios.toml", "[pulse]\nmax_runs_per_day = 2\n")
        for _ in range(4):
            pulse.enqueue(self.root, kind="routine", name="weekly-review", host="mac", source="test")
        self.assertEqual(len(pulse.drain(self.root, "mac")), 2)
        self.assertEqual(len(list((self.root / "runs/queue").glob("*.json"))), 2)


class TelegramAndMeasureTest(FakeClaudeWorkspace):
    def test_bot_ignores_strangers_and_answers_owner(self):
        from aios import telegram
        os.environ["AIOS_TELEGRAM_ALLOWED"] = "42"
        try:
            msg = lambda cid, text: {"message": {"chat": {"id": cid}, "text": text}}
            self.assertIsNone(telegram.handle(msg(7, "manda meus e-mails"), self.root))
            self.assertIn("fake claude", telegram.handle(msg(42, "o que tem hoje?"), self.root))
        finally:
            os.environ.pop("AIOS_TELEGRAM_ALLOWED")

    def test_notify_without_destination_fails_loudly(self):
        from aios import telegram
        for env in ({}, {"AIOS_TELEGRAM_TOKEN": "x"}):
            with self.subTest(env=env):
                os.environ.update(env)
                try:
                    with self.assertRaises(SystemExit):
                        telegram.send_message("oi")
                finally:
                    for k in env:
                        os.environ.pop(k)

    def test_measure_strips_map_from_baseline(self):
        from aios import measure
        copies = measure.make_copies(self.root, self.tmp / "m")
        self.assertTrue((copies["com mapa"] / "map/MAP.md").exists())
        self.assertFalse((copies["sem mapa"] / "map").exists())
        self.assertEqual(list(copies["sem mapa"].rglob("CLAUDE.md")), [])
        self.assertTrue((copies["sem mapa"] / "areas/conteudo/guia-de-estilo.md").exists())

    def test_measure_parses_claude_json(self):
        from aios import measure
        fake = self.tmp / "fake-json"
        fake.write_text('#!/bin/sh\necho \'{"result":"ver guia-de-estilo.md","duration_ms":3000,'
                        '"num_turns":2,"total_cost_usd":0.01,"usage":{"input_tokens":100,'
                        '"output_tokens":50,"cache_read_input_tokens":1000}}\'\n')
        fake.chmod(0o755)
        os.environ["AIOS_CLAUDE_BIN"] = str(fake)
        r = measure.run_once(self.root, "pergunta")
        self.assertEqual((r["tokens"], r["seconds"], r["turns"]), (1150, 3.0, 2))


class ScreenTest(Workspace):
    def setUp(self):
        super().setUp()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.root))
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        super().tearDown()

    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def post(self, body, headers):
        req = urllib.request.Request(self.base + "/api/run", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", **headers}, method="POST")
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_snapshot_reads_files(self):
        code, body = self.get("/api/snapshot")
        snap = json.loads(body)
        self.assertEqual(code, 200)
        self.assertTrue(any(n["title"] == "Preencher a memória" for n in snap["needs_you"]))
        self.assertGreater(len(snap["graph"]["nodes"]), 10)
        # muda o arquivo → o painel muda; nada guardado no servidor
        self.write("areas/sistema/precisa-de-voce.md", "- [ ] **Outra coisa** — teste\n")
        snap = json.loads(self.get("/api/snapshot")[1])
        self.assertEqual([n["title"] for n in snap["needs_you"]], ["Outra coisa"])

    def test_checked_items_are_not_needs(self):
        self.write("areas/sistema/precisa-de-voce.md", "- [x] **Feito** — ok\n- [ ] **Aberto**\n")
        self.assertEqual([n["title"] for n in status.needs_you(self.root)], ["Aberto"])

    def test_export_is_self_contained_and_escapes_script_tags(self):
        from aios import export
        self.write("areas/pessoal/saude.md", "---\nsummary: x\n---\n# Saúde\n</script><script>alert(1)</script>\n")
        full = export.render(self.root, "teste")
        frag = export.render(self.root, "teste", fragment=True)
        self.assertTrue(full.startswith("<!doctype html>"))
        self.assertNotIn("<html", frag)
        self.assertNotIn("<body", frag)
        for html in (full, frag):
            self.assertNotIn('href="style.css"', html)
            self.assertNotIn('src="app.js"', html)
            self.assertIn("window.AIOS_STATIC", html)
            self.assertEqual(html.count("</script><script>alert"), 0)  # nota não fecha a tag
            self.assertIn("areas/conteudo/guia-de-estilo.md", html)
            self.assertNotIn("aios/serve.py", html)  # só arquivos legíveis pelo painel

    def test_agenda_only_next_14_days_sorted(self):
        self.write("areas/sistema/agenda.md", "- 2026-10-20 — longe\n- 2026-10-05 09:00 — b\n"
                   "- 2026-09-30 — passado\n- 2026-10-05 08:00 — a\n- texto solto\n")
        got = status.agenda(self.root, datetime(2026, 10, 1).date())
        self.assertEqual([e["text"] for e in got], ["a", "b"])

    def test_file_endpoint_blocks_traversal_and_secrets(self):
        self.assertEqual(self.get("/api/file?path=areas/conteudo/guia-de-estilo.md")[0], 200)
        self.write(".env", "SECRET=1")
        for bad in ("../../etc/passwd", ".env", "areas/../.env", "aios/serve.py", "/etc/passwd"):
            self.assertEqual(self.get("/api/file?path=" + bad)[0], 404, bad)
        self.assertEqual(self.get("/../aios.toml")[0], 404)

    def test_run_requires_header_and_known_target(self):
        self.assertEqual(self.post({"kind": "skill", "name": "brain-build"}, {})[0], 403)
        self.assertEqual(self.post({"kind": "skill", "name": "rm-rf"}, {"X-AIOS": "1"})[0], 400)
        code, body = self.post({"kind": "routine", "name": "morning-digest", "host": "mac"}, {"X-AIOS": "1"})
        self.assertEqual((code, body["host"]), (202, "vps"))  # host da rotina vence o do pedido
        self.assertEqual(len(list((self.root / "runs/queue").glob("*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
