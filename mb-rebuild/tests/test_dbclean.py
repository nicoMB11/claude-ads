from mb_rebuild import dbclean

# A tiny synthetic dump exercising each marker category.
CLEAN_DUMP = """
INSERT INTO `wp_options` VALUES (1,'siteurl','https://example.com','yes');
INSERT INTO `wp_options` VALUES (2,'blogname','My Site','yes');
INSERT INTO `wp_users` VALUES (1,'admin','$P$hash','admin','admin@example.com','...');
"""

DIRTY_DUMP = """
INSERT INTO `wp_options` VALUES (1,'siteurl','https://example.com','yes');
INSERT INTO `wp_options` VALUES (7,'wp_cache_hook','<?php eval(base64_decode("ZXZpbA==")); ?>','yes');
INSERT INTO `wp_options` VALUES (9,'cron','a:2:{i:123;}','yes');
INSERT INTO `wp_posts` VALUES (5,'Best online casino and viagra deals','<script>document.write("x")</script>');
INSERT INTO `wp_usermeta` VALUES (1,1,'session_tokens','...'),(2,1,'_application_passwords','...');
INSERT INTO `wp_users` VALUES (1,'admin','$P$hash','admin','admin@example.com','...');
INSERT INTO `wp_users` VALUES (2,'attacker','$P$hash','attacker','evil@bad.com','...');
"""


def test_clean_dump_has_no_findings():
    f = dbclean.scan_dump(CLEAN_DUMP, admin_whitelist=["admin"])
    assert not f.any()
    assert f.autoloaded_code == []
    assert f.injected_scripts == 0
    assert f.spam_posts == 0
    assert f.rogue_admins == []


def test_dirty_dump_detects_autoloaded_code():
    f = dbclean.scan_dump(DIRTY_DUMP, admin_whitelist=["admin"])
    assert "wp_cache_hook" in f.autoloaded_code
    assert f.cron_present is True


def test_dirty_dump_detects_scripts_and_spam():
    f = dbclean.scan_dump(DIRTY_DUMP)
    assert f.injected_scripts >= 1
    assert f.spam_posts >= 2  # casino + viagra


def test_dirty_dump_detects_application_passwords():
    f = dbclean.scan_dump(DIRTY_DUMP)
    assert f.application_passwords is True


def test_rogue_admin_flagged_against_whitelist():
    f = dbclean.scan_dump(DIRTY_DUMP, admin_whitelist=["admin"])
    assert "attacker" in f.rogue_admins
    assert "admin" not in f.rogue_admins


def test_no_whitelist_means_no_rogue_flag():
    f = dbclean.scan_dump(DIRTY_DUMP)
    assert f.rogue_admins == []


def test_report_hides_nothing_sensitive_and_lists_categories():
    f = dbclean.scan_dump(DIRTY_DUMP, admin_whitelist=["admin"])
    out = dbclean.report(f, dump_path="x.sql").render()
    assert "Autoloaded options with code" in out
    assert "Cron in wp_options" in out
    assert "Application passwords" in out
    assert "attacker" in out


# --- APC playbook hardening -------------------------------------------------

import base64  # noqa: E402


def _b64(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


def test_scope_connector_family_detected():
    dump = """
INSERT INTO `wp_options` VALUES (1,'sc_payload_persistent','x','yes');
INSERT INTO `wp_options` VALUES (2,'_transient_sc_recover_check','1','yes');
INSERT INTO `wp_options` VALUES (3,'sc_last_rpc','ts','yes');
INSERT INTO `wp_options` VALUES (4,'_transient_sc_spread_interval','60','yes');
"""
    f = dbclean.scan_dump(dump)
    assert "sc_payload_persistent" in f.scope_connector_options
    assert "_transient_sc_recover_check" in f.scope_connector_options
    assert "sc_last_rpc" in f.scope_connector_options
    assert "_transient_sc_spread_interval" in f.scope_connector_options


def test_legitimate_wpsc_not_flagged():
    # wpsc_feed_list is a real plugin option — the pattern must not match it.
    dump = "INSERT INTO `wp_options` VALUES (1,'wpsc_feed_list','a:0:{}','yes');"
    f = dbclean.scan_dump(dump)
    assert f.scope_connector_options == []
    assert not f.any()


def test_md5_named_autoloaded_option_flagged():
    dump = (
        "INSERT INTO `wp_options` VALUES "
        "(1,'516d2bb2524589eb98cef7928cc655a6','payload','yes');"
    )
    f = dbclean.scan_dump(dump)
    assert "516d2bb2524589eb98cef7928cc655a6" in f.hash_named_options


def test_base64_cloaking_injector_decoded_and_flagged():
    payload = "var s=document.createElement('script');s.src='https://counter.yadro.ru/hit';bodyNode.remove();"
    dump = (
        "INSERT INTO `wp_options` VALUES "
        f"(1,'516d2bb2524589eb98cef7928cc655a6','{_b64(payload)}','yes');"
    )
    f = dbclean.scan_dump(dump)
    assert "516d2bb2524589eb98cef7928cc655a6" in f.cloaking_options
    assert "516d2bb2524589eb98cef7928cc655a6" in f.hash_named_options
    # It appears once in the consolidated delete list, de-duplicated.
    assert f.options_to_delete.count("516d2bb2524589eb98cef7928cc655a6") == 1


def test_base64_hidden_php_code_decoded():
    payload = "<?php eval(base64_decode('ZXZpbA==')); ?>"
    dump = f"INSERT INTO `wp_options` VALUES (1,'sc_initialized','{_b64(payload)}','yes');"
    f = dbclean.scan_dump(dump)
    assert "sc_initialized" in f.autoloaded_code       # decoded PHP caught
    assert "sc_initialized" in f.scope_connector_options


def test_malicious_cron_hook_detected():
    dump = "INSERT INTO `wp_options` VALUES (1,'cron','a:1:{s:13:\"sc_cron_fetch\";}','yes');"
    f = dbclean.scan_dump(dump)
    assert "sc_cron_fetch" in f.malicious_cron
    assert f.cron_present is True


def test_options_to_delete_dedupes_across_categories():
    # An sc_ option that ALSO carries literal code should appear once.
    dump = "INSERT INTO `wp_options` VALUES (1,'sc_initialized','<?php eval(1); ?>','yes');"
    f = dbclean.scan_dump(dump)
    assert f.options_to_delete.count("sc_initialized") == 1
