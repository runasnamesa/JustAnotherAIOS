"""Parser mínimo de expressões cron de 5 campos (minuto hora dia mês dia-da-semana).

Suporta: `*`, números, listas (`1,5`), intervalos (`1-5`) e passos (`*/15`, `0-30/10`).
Dia-da-semana: 0-7 (0 e 7 = domingo). Segue a regra clássica do cron: se dia-do-mês
E dia-da-semana forem restritos, basta um deles casar.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

_RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]


class CronError(ValueError):
    pass


def _parse_field(text: str, lo: int, hi: int) -> frozenset[int]:
    values: set[int] = set()
    for part in text.split(","):
        step = 1
        if "/" in part:
            part, step_s = part.split("/", 1)
            if not step_s.isdigit() or int(step_s) == 0:
                raise CronError(f"passo inválido: {step_s!r}")
            step = int(step_s)
        if part == "*":
            start, end = lo, hi
        elif "-" in part:
            a, b = part.split("-", 1)
            if not (a.isdigit() and b.isdigit()):
                raise CronError(f"intervalo inválido: {part!r}")
            start, end = int(a), int(b)
        elif part.isdigit():
            start = end = int(part)
            if step != 1:
                end = hi
        else:
            raise CronError(f"campo inválido: {part!r}")
        if start < lo or end > hi or start > end:
            raise CronError(f"{part!r} fora de {lo}-{hi}")
        values.update(range(start, end + 1, step))
    return frozenset(values)


@dataclass(frozen=True)
class Cron:
    expr: str
    minutes: frozenset[int]
    hours: frozenset[int]
    days: frozenset[int]
    months: frozenset[int]
    weekdays: frozenset[int]
    day_restricted: bool
    weekday_restricted: bool

    @classmethod
    def parse(cls, expr: str) -> "Cron":
        fields = expr.split()
        if len(fields) != 5:
            raise CronError(f"esperava 5 campos, recebi {len(fields)}: {expr!r}")
        parsed = [_parse_field(f, lo, hi) for f, (lo, hi) in zip(fields, _RANGES)]
        weekdays = frozenset(0 if d == 7 else d for d in parsed[4])
        return cls(expr, parsed[0], parsed[1], parsed[2], parsed[3], weekdays,
                   fields[2] != "*", fields[4] != "*")

    def matches(self, t: datetime) -> bool:
        if t.minute not in self.minutes or t.hour not in self.hours or t.month not in self.months:
            return False
        dom = t.day in self.days
        dow = (t.isoweekday() % 7) in self.weekdays  # domingo = 0
        if self.day_restricted and self.weekday_restricted:
            return dom or dow
        return dom and dow

    def due_between(self, after: datetime, until: datetime) -> datetime | None:
        """Último instante (minuto cheio) em (after, until] que casa com a expressão.

        Usado pelo scheduler: se o computador dormiu, a rotina roda uma vez ao acordar
        (sem replay de todas as execuções perdidas). Janela limitada a 7 dias.
        """
        t = until.replace(second=0, microsecond=0)
        floor = max(after, until - timedelta(days=7))
        while t > floor:
            if self.matches(t):
                return t
            t -= timedelta(minutes=1)
        return None
