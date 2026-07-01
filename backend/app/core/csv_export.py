"""CSV cell hardening shared by every CSV export path.

Spreadsheet applications (Excel, Google Sheets, LibreOffice) interpret a cell whose
text begins with ``=``, ``+``, ``-``, ``@`` or a leading tab / carriage-return / newline
as a *formula*. Because our exports carry imported annotations and user-controlled tags,
such a value can smuggle an executable formula into a downloaded CSV — the classic
"CSV / formula injection" sink (e.g. ``=HYPERLINK(...)`` or ``@SUM(...)`` exfiltrating
data on open).

``csv_safe_cell`` neutralises this by prefixing an at-risk value with a single quote,
which every mainstream spreadsheet treats as "keep the rest as literal text". It is the
one formatter that every export path must funnel its data cells through.
"""

from __future__ import annotations

# The leading characters a spreadsheet may treat as the start of a formula. Tab / CR / LF
# are included because a value can be pushed past a naive "first visible char" check.
_FORMULA_TRIGGERS = frozenset("=+-@\t\r\n")


def csv_safe_cell(value: str) -> str:
    """Return ``value`` neutralised against spreadsheet formula injection.

    A value whose first character is a formula trigger is prefixed with a single quote so
    the spreadsheet renders it as text; everything else is returned unchanged. Headers are
    developer-controlled and need not be routed through this — only data cells do.
    """

    if value and value[0] in _FORMULA_TRIGGERS:
        return "'" + value
    return value
