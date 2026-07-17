from mb_rebuild.remote import Host, Remote
from mb_rebuild.utils import load_env_file, redact, resolve_secret


def test_redact_license_flags():
    assert "SECRET" not in redact("wp plugin activate --license SECRET123")
    assert "***" in redact("--license SECRET123")


def test_redact_db_password_in_config():
    assert "hunter2" not in redact("DB_PASSWORD='hunter2'")


def test_redact_url_credentials():
    out = redact("mysql://user:hunter2@db.example.com/wp")
    assert "hunter2" not in out
    assert "user" in out


def test_registered_secret_masked_in_positional_command():
    # The dangerous case: `wp <plugin> license activate <KEY>` — KEY is a bare
    # positional arg the flag patterns cannot catch. Registering it must mask.
    from mb_rebuild.utils import register_secret

    key = "elem-pro-abc123-secret"
    register_secret(key)
    out = redact(f"wp elementor-pro license activate {key} --path=/var/www")
    assert key not in out
    assert "***" in out


def test_load_env_file(tmp_path):
    p = tmp_path / ".env"
    p.write_text('# comment\nexport ELEMENTOR_PRO_LICENSE="abc123"\nSEOPRESS=xyz\n\n')
    env = load_env_file(str(p))
    assert env["ELEMENTOR_PRO_LICENSE"] == "abc123"
    assert env["SEOPRESS"] == "xyz"


def test_load_env_file_missing_is_empty():
    assert load_env_file("/nonexistent/.env") == {}


def test_resolve_secret_prefers_env_file(monkeypatch):
    monkeypatch.setenv("KEY", "from-os")
    assert resolve_secret("KEY", {"KEY": "from-file"}) == "from-file"
    assert resolve_secret("KEY", {}) == "from-os"
    assert resolve_secret("MISSING", {}) is None


def test_host_parse_full():
    h = Host.parse("deploy@example.com:/var/www/site", port=2222)
    assert h.user == "deploy"
    assert h.host == "example.com"
    assert h.path == "/var/www/site"
    assert h.port == 2222
    assert h.target == "deploy@example.com"


def test_host_parse_no_path_defaults_home():
    h = Host.parse("example.com")
    assert h.host == "example.com"
    assert h.path == "~"
    assert h.user is None
    assert h.target == "example.com"


def test_remote_dry_run_skips_writes(capsys):
    remote = Remote(Host.parse("u@h:/p"), dry_run=True)
    result = remote.run(["wp", "plugin", "install", "elementor"], write=True)
    assert result is None
    out = capsys.readouterr().out
    assert "dry-run" in out
