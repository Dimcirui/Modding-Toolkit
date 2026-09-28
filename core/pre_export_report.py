"""Pre-export check, report layer: turn raw findings into what the dialog shows.

No bpy and no wording here, for the same reason as ``core/pre_export_check.py``:
the grouping rules are the part worth testing offline
(``tests/test_pre_export_report.py``), and they are independent of how a line is
phrased or drawn.

Shape of the report (``docs/pre_export_check_plan.md`` §1-§2)::

    category  (tex / mat / bone / phys)       -- at most four, in that order
      group   (one per sub-problem)           -- errors before notes
        item  (one object, path or name)      -- deduplicated across parts

**What gets counted is categories and items, never vertices.**  v1 summed each
category's count, and the weight check's count was a vertex count, so a single
unnormalised mesh put "3000+ issues" in the summary line.

**Deduplication is by key.**  A texture missing for five parts is one item that
lists the five parts, not five items that differ only by prefix.
"""

ERROR = 'error'
INFO = 'info'

CATEGORY_ORDER = ('tex', 'mat', 'bone', 'phys')

_RANK = {ERROR: 0, INFO: 1}


def finding(cat, sub, text, *, severity=ERROR, key=None, part='', objects=()):
    """One raw finding, as the checks produce it.

    *key* decides what counts as "the same problem" for deduplication; it
    defaults to the text, which is right for anything not shared across parts.
    """
    return {'cat': cat, 'sub': sub, 'text': text, 'severity': severity,
            'key': text if key is None else key, 'part': part,
            'objects': list(objects)}


def build_report(findings, sub_order=()):
    """``[category]`` ready to store and draw.

    ``category = {'code', 'severity', 'count', 'groups', 'objects', 'parts'}``,
    ``group = {'sub', 'severity', 'items'}``,
    ``item = {'text', 'severity', 'parts'}``.

    *sub_order* fixes the order of groups inside a category (anything not
    listed goes last, in the order first seen); errors always precede notes.
    """
    order = {s: i for i, s in enumerate(sub_order)}
    cats = {}
    for f in findings:
        cat = cats.setdefault(f['cat'], {'groups': {}, 'objects': [], 'parts': []})
        grp = cat['groups'].setdefault(f['sub'], {'items': {}, 'severity': f['severity'],
                                                  'seen': len(cat['groups'])})
        if _RANK[f['severity']] < _RANK[grp['severity']]:
            grp['severity'] = f['severity']
        item = grp['items'].setdefault(f['key'], {'text': f['text'], 'parts': [],
                                                  'severity': f['severity']})
        if f['part'] and f['part'] not in item['parts']:
            item['parts'].append(f['part'])
        if f['part'] and f['part'] not in cat['parts']:
            cat['parts'].append(f['part'])
        for o in f['objects']:
            if o not in cat['objects']:
                cat['objects'].append(o)

    out = []
    known = [c for c in CATEGORY_ORDER if c in cats] + \
            [c for c in cats if c not in CATEGORY_ORDER]
    for code in known:
        cat = cats[code]
        groups = sorted(
            cat['groups'].items(),
            key=lambda kv: (_RANK[kv[1]['severity']],
                            order.get(kv[0], len(order)), kv[1]['seen']))
        groups = [{'sub': sub, 'severity': g['severity'],
                   'items': list(g['items'].values())} for sub, g in groups]
        severity = ERROR if any(g['severity'] == ERROR for g in groups) else INFO
        out.append({'code': code, 'severity': severity,
                    'count': sum(len(g['items']) for g in groups),
                    'groups': groups, 'objects': cat['objects'],
                    'parts': cat['parts']})
    return out


def summary(report):
    """``(categories with an error, notes)`` for the one-line summary.

    Notes are counted as items, errors as categories: "2 categories to fix,
    1 note" is what the design asks for, and a note is too soft to be worth
    its own category count.
    """
    n_err = sum(1 for c in report if c['severity'] == ERROR)
    n_info = sum(len(g['items']) for c in report for g in c['groups']
                 if g['severity'] == INFO)
    return n_err, n_info


def parts_with_errors(report):
    """Every part label that carries at least one error item -- for the batch
    dialogs that flag rows in their own part list."""
    out = set()
    for c in report:
        for g in c['groups']:
            for it in g['items']:
                if it['severity'] == ERROR:
                    out.update(it['parts'])
    return out


def item_line(item, part_sep=" · ", used_by="{parts}", joiner=", "):
    """The drawn line for one item.

    One part: ``<part> · <text>``, the part named up front like every other
    batch line.  Several parts: ``<text>`` followed by *used_by* formatted with
    the joined part names, since leading with five names would bury the text.
    *used_by* and *joiner* are wording, so the caller passes them translated.
    """
    parts = item['parts']
    if not parts:
        return item['text']
    if len(parts) == 1:
        return f"{parts[0]}{part_sep}{item['text']}"
    return item['text'] + used_by.format(parts=joiner.join(parts))
