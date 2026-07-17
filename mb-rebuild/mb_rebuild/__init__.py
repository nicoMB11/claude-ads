"""mb-rebuild — rebuild clean WordPress sites from official sources.

A site is an engine (replaceable: core, plugins, theme) plus content
(worth keeping: the database and uploads/). This tool industrialises
replacing the engine while re-injecting *cleaned* content, so no backdoor
can travel from an old, possibly-compromised site into the new one.

Runs on the operator's machine and drives a target host over SSH + WP-CLI.
Nothing is written to any server unless dry-run is explicitly disabled.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
