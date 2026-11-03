"""İnceleme durumunun saklanması ve yeni gruplara uygulanması."""

from pathlib import Path

from benzerfoto.features import ImageFeatures
from benzerfoto.grouping import GroupKind, PhotoGroup
from benzerfoto.review import ReviewStore, apply_decisions


def feat(path: str) -> ImageFeatures:
    return ImageFeatures(path=path, size=100, mtime_ns=1)


def group(*paths: str, best: str | None = None, marked=(), protected=()) -> PhotoGroup:
    g = PhotoGroup(GroupKind.SCENE, [feat(p) for p in paths], best_path=best or paths[0])
    g.marked = set(marked) if marked else {p for p in paths if p != g.best_path}
    g.protected = set(protected)
    return g


def test_roundtrip_restores_review_and_marks(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    g = group("a", "b", "c")
    g.reviewed = True
    g.best_path = "b"
    g.marked = {"c"}
    with ReviewStore(db) as store:
        store.save_group(g)

    # Ertesi gün: yeniden tarama sonrası aynı grup varsayılan işaretlerle gelir
    fresh = group("a", "b", "c")
    with ReviewStore(db) as store:
        apply_decisions([fresh], store.load(GroupKind.SCENE))
        assert store.load(GroupKind.SIMILAR) == {}  # modlar birbirinden ayrı
    assert fresh.reviewed and fresh.best_path == "b" and fresh.marked == {"c"}


def test_new_member_makes_group_unreviewed_but_keeps_known_marks(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    g = group("a", "b")
    g.reviewed = True
    g.marked = set()  # kullanıcı hiçbirini ayırmak istemedi
    with ReviewStore(db) as store:
        store.save_group(g)
    fresh = group("a", "b", "new")
    with ReviewStore(db) as store:
        apply_decisions([fresh], store.load(GroupKind.SCENE))
    assert not fresh.reviewed
    assert "b" not in fresh.marked and "new" in fresh.marked


def test_protected_wins_over_saved_mark(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    g = group("a", "b")
    g.reviewed = True
    with ReviewStore(db) as store:
        store.save_group(g)  # "b" işaretli kaydedildi
    fresh = group("a", "b", protected=["b"])
    fresh.marked.discard("b")
    with ReviewStore(db) as store:
        apply_decisions([fresh], store.load(GroupKind.SCENE))
    assert "b" not in fresh.marked


def test_unreviewed_flag_is_saved(tmp_path: Path):
    db = tmp_path / "db.sqlite"
    g = group("a", "b")
    g.reviewed = True
    with ReviewStore(db) as store:
        store.save_group(g)
        g.reviewed = False
        store.save_group(g)
        fresh = group("a", "b")
        apply_decisions([fresh], store.load(GroupKind.SCENE))
    assert not fresh.reviewed
