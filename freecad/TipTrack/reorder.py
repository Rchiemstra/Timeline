# SPDX-License-Identifier: LGPL-3.0-or-later
# SPDX-FileNotice: Dependency-aware feature reordering for TipTrack.

"""Dependency checks and Body.Group move helpers for TipTrack."""


def _features(body) -> list:
    return list(getattr(body, "Group", []) or [])


def _label(obj) -> str:
    return str(getattr(obj, "Label", getattr(obj, "Name", "feature")))


def _clamp_index(index: int, count: int) -> int:
    if count <= 0:
        return 0
    return max(0, min(index, count - 1))


def _contains_identity(items: list, target) -> bool:
    return any(item is target for item in items)


def _index_identity(items: list, target) -> int:
    for index, item in enumerate(items):
        if item is target:
            return index
    raise ValueError(f"{_label(target)} is not in the active Body.")


def _reordered(features: list, feature, new_index: int) -> list:
    order = [item for item in features if item is not feature]
    order.insert(_clamp_index(new_index, len(features)), feature)
    return order


def can_move(body, feature, new_index: int) -> tuple[bool, str]:
    """Return whether feature can occupy new_index without breaking dependencies."""
    features = _features(body)
    if not _contains_identity(features, feature):
        return False, f"{_label(feature)} is not in the active Body."

    if len(features) <= 1:
        return True, ""

    order = _reordered(features, feature, new_index)
    positions = {id(item): index for index, item in enumerate(order)}
    feature_index = positions[id(feature)]

    body_feature_ids = {id(item) for item in features}

    for dependency in getattr(feature, "OutList", []) or []:
        if id(dependency) not in body_feature_ids:
            continue
        if feature_index < positions[id(dependency)]:
            return (
                False,
                f"{_label(feature)} depends on {_label(dependency)} "
                "and cannot move before it.",
            )

    for dependent in getattr(feature, "InList", []) or []:
        if id(dependent) not in body_feature_ids:
            continue
        if feature_index > positions[id(dependent)]:
            return (
                False,
                f"{_label(dependent)} depends on {_label(feature)} "
                "and cannot move after it.",
            )

    return True, ""


def move_feature(body, feature, new_index: int) -> None:
    """Move feature to new_index using Body.removeObject/insertObject."""
    ok, reason = can_move(body, feature, new_index)
    if not ok:
        raise ValueError(reason)

    features = _features(body)
    if not _contains_identity(features, feature):
        raise ValueError(f"{_label(feature)} is not in the active Body.")

    old_index = _index_identity(features, feature)
    final_index = _clamp_index(new_index, len(features))
    if old_index == final_index:
        return

    remaining = [item for item in features if item is not feature]
    target = remaining[final_index] if final_index < len(remaining) else None

    body.removeObject(feature)
    body.insertObject(feature, target, False)

    document = getattr(body, "Document", None)
    if document is not None:
        document.recompute()
