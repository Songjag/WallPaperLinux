from __future__ import annotations


def load_customtkinter() -> object:
    """Return the customtkinter module bundled with the application."""
    try:
        import customtkinter  
        return customtkinter
    except ImportError as exc:
        raise SystemExit(
            "customtkinter could not be loaded. "
            "Re-build the application with --collect-all customtkinter."
        ) from exc
