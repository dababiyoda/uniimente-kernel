"""pytest plugin for measuring #293's tests on variant S: give greg.capabilities the two names #293's ``machine``
fixture patches and variant S does not define, so that fixture can set up. Variant S's code reads neither:
RENDER_SECONDS (S keeps the literal 45 of 8d205324) and _render_judged (the check's memory, absent from S). Names a
test body calls directly (cannot_render, _sandboxes_itself, _build, ...) are not supplied."""


def pytest_configure(config):
    from greg import capabilities
    for name, value in (("RENDER_SECONDS", 45), ("_render_judged", {})):
        if not hasattr(capabilities, name):
            setattr(capabilities, name, value)
