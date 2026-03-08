from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from mp.db.core import SessionLocal
from mp.icons import digest_icon, normalize_icon_png
from mp.schema.account import DefaultIcon, IconAsset, Organization


def _load_config() -> list[dict[str, str]]:
    config_path = (
        Path(__file__).resolve().parents[1] / "organizations" / "organizations.yml"
    )
    if not config_path.exists():
        return []
    payload = yaml.safe_load(config_path.read_text()) or {}
    return payload.get("organizations", [])


def _load_generic_config() -> list[dict[str, str]]:
    config_path = (
        Path(__file__).resolve().parents[1] / "organizations" / "generic_icons.yml"
    )
    if not config_path.exists():
        return []
    payload = yaml.safe_load(config_path.read_text()) or {}
    return payload.get("generic_icons", [])


def _ensure_default_organizations(db: Session) -> None:
    base_dir = Path(__file__).resolve().parents[1] / "organizations"
    configured_names: set[str] = set()
    for item in _load_config():
        name = (item.get("name") or "").strip()
        icon_file = (item.get("icon") or "").strip()
        url = (item.get("url") or "").strip() or None
        if not name or not icon_file:
            continue
        configured_names.add(name)
        icon_path = base_dir / icon_file
        if not icon_path.exists():
            continue

        icon_png = normalize_icon_png(icon_path.read_bytes())
        icon_hash = digest_icon(icon_png)
        icon = db.query(IconAsset).filter_by(hash=icon_hash).first()
        if icon is None:
            icon = IconAsset(hash=icon_hash, png_data=icon_png, created_by_user_id=None)
            db.add(icon)
            db.flush()

        organization = db.query(Organization).filter_by(name=name).first()
        if organization is None:
            organization = Organization(
                name=name, url=url, icon_id=icon.id, is_default=True
            )
            db.add(organization)
        else:
            organization.url = url
            organization.icon_id = icon.id
            organization.is_default = True

    if configured_names:
        (
            db.query(Organization)
            .filter(
                Organization.is_default.is_(True),
                Organization.name.notin_(configured_names),
            )
            .update({"is_default": False}, synchronize_session=False)
        )


def _ensure_default_generic_icons(db: Session) -> None:
    base_dir = Path(__file__).resolve().parents[1] / "organizations"
    configured_keys: set[str] = set()
    for item in _load_generic_config():
        key = (item.get("key") or "").strip()
        label = (item.get("label") or "").strip()
        icon_file = (item.get("icon") or "").strip()
        if not key or not label or not icon_file:
            continue
        configured_keys.add(key)
        icon_path = base_dir / icon_file
        if not icon_path.exists():
            continue
        icon_png = normalize_icon_png(icon_path.read_bytes())
        icon_hash = digest_icon(icon_png)
        icon = db.query(IconAsset).filter_by(hash=icon_hash).first()
        if icon is None:
            icon = IconAsset(hash=icon_hash, png_data=icon_png, created_by_user_id=None)
            db.add(icon)
            db.flush()

        default_icon = db.query(DefaultIcon).filter_by(key=key).first()
        if default_icon is None:
            default_icon = DefaultIcon(key=key, label=label, icon_id=icon.id)
            db.add(default_icon)
        else:
            default_icon.label = label
            default_icon.icon_id = icon.id

    if configured_keys:
        (
            db.query(DefaultIcon)
            .filter(DefaultIcon.key.notin_(configured_keys))
            .delete(synchronize_session=False)
        )
    else:
        db.query(DefaultIcon).delete(synchronize_session=False)


def ensure_default_organizations_loaded() -> None:
    db = SessionLocal()
    try:
        _ensure_default_organizations(db)
        _ensure_default_generic_icons(db)
        db.commit()
    finally:
        db.close()
